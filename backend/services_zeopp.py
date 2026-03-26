from __future__ import annotations

import ctypes
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
ZEOPP_RUNTIME_DIR = ROOT / 'vendor' / 'zeopp-lsmo' / 'zeo++'
ZEOPP_TOOLCHAIN_BIN = ROOT / 'zeopp-toolchain' / 'Library' / 'mingw-w64' / 'bin'
ZEOPP_TOOLCHAIN_USR_BIN = ROOT / 'zeopp-toolchain' / 'Library' / 'usr' / 'bin'

SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002
SEM_NOOPENFILEERRORBOX = 0x8000


def detect_zeopp_binary() -> tuple[Path | None, str]:
    env_path = os.getenv('CHEMEX_ZEOPP_BIN')
    candidates = [
        Path(env_path) if env_path else None,
        ROOT / 'vendor' / 'zeopp-lsmo' / 'zeo++' / 'network.exe',
        ROOT / 'vendor' / 'zeopp-lsmo' / 'zeo++' / 'network',
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            if candidate.suffix.lower() == '.exe':
                return candidate, f'ZEO++ runtime is ready at {candidate}.'
            return candidate, 'Detected ZEO++ network binary.'
    return None, (
        'ZEO++ runtime is not available on this machine yet. '
        'The source repo is vendored, but there is no compiled network binary.'
    )


def build_zeopp_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_path = env.get('PATH', '')
    path_parts = [
        str(ZEOPP_RUNTIME_DIR),
        str(ZEOPP_TOOLCHAIN_BIN),
        str(ZEOPP_TOOLCHAIN_USR_BIN),
        existing_path,
    ]
    env['PATH'] = os.pathsep.join(part for part in path_parts if part)
    return env


@contextmanager
def suppress_windows_error_dialogs():
    if os.name != 'nt' or not hasattr(ctypes, 'windll'):
        yield
        return

    flags = SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
    previous = ctypes.windll.kernel32.SetErrorMode(flags)
    try:
        yield
    finally:
        ctypes.windll.kernel32.SetErrorMode(previous)


def creation_flags_for_zeopp() -> int:
    flags = 0
    if os.name == 'nt' and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        flags |= subprocess.CREATE_NO_WINDOW
    return flags


def _extract_number(text: str, key: str, default: float | int = 0.0) -> float:
    match = re.search(rf'{re.escape(key)}:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)', text)
    if match is None:
        return float(default)
    return float(match.group(1))


def parse_psd_output(text: str) -> dict[str, Any]:
    rows: list[dict[str, float]] = []
    metrics = [
        {'key': 'bin_size', 'label': 'Bin size', 'value': _extract_number(text, 'Bin size (A)'), 'unit': 'A'},
        {'key': 'bin_count', 'label': 'Number of bins', 'value': _extract_number(text, 'Number of bins'), 'unit': None},
        {'key': 'range_from', 'label': 'From', 'value': _extract_number(text, 'From'), 'unit': 'A'},
        {'key': 'range_to', 'label': 'To', 'value': _extract_number(text, 'To'), 'unit': 'A'},
        {'key': 'total_samples', 'label': 'Total samples', 'value': _extract_number(text, 'Total samples'), 'unit': None},
        {'key': 'accessible_samples', 'label': 'Accessible samples', 'value': _extract_number(text, 'Accessible samples'), 'unit': None},
        {
            'key': 'fraction_node_spheres',
            'label': 'Fraction in node spheres',
            'value': _extract_number(text, 'Fraction of sample points in node spheres'),
            'unit': None,
        },
        {
            'key': 'fraction_outside_spheres',
            'label': 'Fraction outside node spheres',
            'value': _extract_number(text, 'Fraction of sample points outside node spheres'),
            'unit': None,
        },
    ]

    lines = [line for line in text.splitlines() if line.strip()]
    data_started = False
    for line in lines:
        if line.startswith('Bin Count'):
            data_started = True
            continue
        if not data_started:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        diameter, count, cumulative, derivative = parts[:4]
        rows.append(
            {
                'diameter': float(diameter),
                'value': float(count),
                'count': float(count),
                'cumulative': float(cumulative),
                'derivative': float(derivative),
            }
        )

    return {
        'mode': 'psd',
        'rows': rows,
        'metrics': metrics,
    }


def parse_res_output(text: str, extended: bool) -> dict[str, Any]:
    values = text.split()
    if len(values) < 4:
        raise ValueError('Unexpected ZEO++ RES output format.')

    metrics = [
        {
            'key': 'largest_included_sphere',
            'label': 'Largest included sphere',
            'value': float(values[1]),
            'unit': 'A',
        },
        {
            'key': 'largest_free_sphere',
            'label': 'Largest free sphere',
            'value': float(values[2]),
            'unit': 'A',
        },
        {
            'key': 'largest_included_free_sphere',
            'label': 'Largest included free sphere',
            'value': float(values[3]),
            'unit': 'A',
        },
    ]

    if extended and len(values) >= 10:
        axis_labels = ['a', 'b', 'c']
        free_values = values[4:7]
        included_values = values[7:10]
        for axis, value in zip(axis_labels, free_values):
            metrics.append(
                {
                    'key': f'largest_free_sphere_{axis}',
                    'label': f'Largest free sphere along {axis}',
                    'value': float(value),
                    'unit': 'A',
                }
            )
        for axis, value in zip(axis_labels, included_values):
            metrics.append(
                {
                    'key': f'largest_included_sphere_{axis}',
                    'label': f'Largest included sphere along {axis}',
                    'value': float(value),
                    'unit': 'A',
                }
            )

    return {
        'mode': 'res',
        'metrics': metrics,
        'metadata': {'extended': extended},
    }


def parse_chan_output(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError('Unexpected empty ZEO++ CHAN output.')

    match = re.search(r'(\d+) channels identified of dimensionality([\d\s]*)', lines[0])
    if not match:
        raise ValueError('Unexpected ZEO++ CHAN header format.')

    count = int(match.group(1))
    dimensionalities = list(map(int, match.group(2).split())) if count else []
    dis: list[float] = []
    dfs: list[float] = []
    difs: list[float] = []
    for line in lines[1:1 + count]:
        parts = line.split()
        if len(parts) < 5:
            continue
        dis.append(float(parts[2]))
        dfs.append(float(parts[3]))
        difs.append(float(parts[4]))

    metrics = [
        {'key': 'channel_count', 'label': 'Channel count', 'value': count, 'unit': None},
        {
            'key': 'dimensionalities',
            'label': 'Dimensionalities',
            'value': ', '.join(str(value) for value in dimensionalities) if dimensionalities else '0',
            'unit': None,
        },
    ]
    if dis:
        metrics.extend(
            [
                {
                    'key': 'max_largest_included_sphere',
                    'label': 'Max largest included sphere',
                    'value': max(dis),
                    'unit': 'A',
                },
                {
                    'key': 'max_largest_free_sphere',
                    'label': 'Max largest free sphere',
                    'value': max(dfs),
                    'unit': 'A',
                },
                {
                    'key': 'max_largest_included_free_sphere',
                    'label': 'Max largest included free sphere',
                    'value': max(difs),
                    'unit': 'A',
                },
            ]
        )

    return {
        'mode': 'chan',
        'metrics': metrics,
        'channels': {
            'count': count,
            'dimensionalities': dimensionalities,
            'largestIncludedSpheres': dis,
            'largestFreeSpheres': dfs,
            'largestIncludedFreeSpheres': difs,
        },
    }


def parse_surface_area_output(text: str) -> dict[str, Any]:
    mapping = [
        ('unitcell_volume', 'Unit cell volume', 'Unitcell_volume', 'A^3'),
        ('density', 'Density', 'Density', 'g/cm^3'),
        ('asa_a2', 'ASA', 'ASA_A^2', 'A^2'),
        ('asa_m2_cm3', 'ASA volumetric', 'ASA_m^2/cm^3', 'm^2/cm^3'),
        ('asa_m2_g', 'ASA gravimetric', 'ASA_m^2/g', 'm^2/g'),
        ('nasa_a2', 'NASA', 'NASA_A^2', 'A^2'),
        ('nasa_m2_cm3', 'NASA volumetric', 'NASA_m^2/cm^3', 'm^2/cm^3'),
        ('nasa_m2_g', 'NASA gravimetric', 'NASA_m^2/g', 'm^2/g'),
        ('number_of_channels', 'Number of channels', 'Number_of_channels', None),
        ('channel_surface_area', 'Channel surface area', 'Channel_surface_area_A^2', 'A^2'),
        ('number_of_pockets', 'Number of pockets', 'Number_of_pockets', None),
        ('pocket_surface_area', 'Pocket surface area', 'Pocket_surface_area_A^2', 'A^2'),
    ]
    metrics = [
        {'key': key, 'label': label, 'value': _extract_number(text, source), 'unit': unit}
        for key, label, source, unit in mapping
    ]
    return {'mode': 'sa', 'metrics': metrics}


def parse_volume_output(text: str, probe_occupiable: bool) -> dict[str, Any]:
    prefix = 'PO' if probe_occupiable else ''
    base_mode = 'volpo' if probe_occupiable else 'vol'
    mapping = [
        ('unitcell_volume', 'Unit cell volume', 'Unitcell_volume', 'A^3'),
        ('density', 'Density', 'Density', 'g/cm^3'),
        (f'{base_mode}_a3', 'Accessible volume', f'{prefix}AV_A^3', 'A^3'),
        (f'{base_mode}_vf', 'Accessible volume fraction', f'{prefix}AV_Volume_fraction', None),
        (f'{base_mode}_cm3_g', 'Accessible volume gravimetric', f'{prefix}AV_cm^3/g', 'cm^3/g'),
        (f'n{base_mode}_a3', 'Non-accessible volume', f'{prefix}NAV_A^3', 'A^3'),
        (f'n{base_mode}_vf', 'Non-accessible volume fraction', f'{prefix}NAV_Volume_fraction', None),
        (f'n{base_mode}_cm3_g', 'Non-accessible volume gravimetric', f'{prefix}NAV_cm^3/g', 'cm^3/g'),
        ('number_of_channels', 'Number of channels', 'Number_of_channels', None),
        ('channel_volume', 'Channel volume', 'Channel_volume_A^3', 'A^3'),
        ('number_of_pockets', 'Number of pockets', 'Number_of_pockets', None),
        ('pocket_volume', 'Pocket volume', 'Pocket_volume_A^3', 'A^3'),
    ]
    metrics = [
        {'key': key, 'label': label, 'value': _extract_number(text, source), 'unit': unit}
        for key, label, source, unit in mapping
    ]
    return {'mode': base_mode, 'metrics': metrics}


def update_zeopp_progress_from_line(mode: str, line: str, advance: Callable[[str, int], None], current_progress: Callable[[], int]) -> None:
    text = line.strip().lower()
    if not text:
        return

    progress = current_progress()

    if 'reading input file:' in text or 'opening file:' in text:
        advance('reading_structure', 10)
    elif 'starting voronoi decomposition' in text and progress < 35:
        advance('initial_voronoi', 24)
    elif 'finished voronoi decomposition' in text and progress < 48:
        advance('routing_network', 38)
    elif 'command 1  -psd' in text:
        advance('psd_setup', 50)
    elif 'command 1  -res' in text or 'command 1  -resex' in text:
        advance('pore_diameter_scan', 62)
    elif 'command 1  -chan' in text:
        advance('channel_scan', 60)
    elif 'command 1  -sa' in text:
        advance('surface_area_sampling', 60)
    elif 'command 1  -vol' in text:
        advance('volume_sampling', 60)
    elif 'command 1  -volpo' in text:
        advance('probe_occupiable_sampling', 60)
    elif 'voronoi network with' in text and progress < 72:
        advance('network_ready', 68)
    elif 'finding channels and pockets' in text:
        advance('finding_channels', 76)
    elif 'identified' in text and 'channels' in text:
        advance('classifying_pores', 84)
    elif 'probeoccupiableloopstart' in text:
        advance('probe_occupiable_sampling', 86)
    elif 'probeoccupiableloopend' in text:
        advance('writing_output', 94)
    elif 'pore size distribution calculated.' in text:
        advance('writing_output', 94)
    elif 'notice: calling abort()' in text and mode != 'psd':
        advance('writing_output', 94)


def drain_pipe(
    pipe,
    buffer: list[str],
    *,
    mode: str | None = None,
    advance: Callable[[str, int], None] | None = None,
    current_progress: Callable[[], int] | None = None,
) -> None:
    if pipe is None:
        return
    try:
        for line in iter(pipe.readline, ''):
            if not line:
                break
            buffer.append(line)
            if mode and advance and current_progress:
                update_zeopp_progress_from_line(mode, line, advance, current_progress)
    finally:
        pipe.close()


def build_command(binary: Path, mode: str, input_path: Path, params: dict[str, Any]) -> tuple[list[str], Path, bool]:
    job_dir = input_path.parent
    if mode == 'psd':
        output_path = job_dir / 'psd.out'
        command = [
            str(binary),
            '-ha',
            '-psd',
            str(params.get('chanRadius', '1.86')),
            str(params.get('probeRadius', '1.86')),
            str(params.get('numSamples', '10000')),
            str(output_path),
            str(input_path),
        ]
        return command, output_path, False
    if mode == 'res':
        extended = str(params.get('extended', 'false')).lower() in {'true', '1', 'yes', 'on'}
        output_path = job_dir / 'res.out'
        command = [
            str(binary),
            '-ha',
            '-resex' if extended else '-res',
            str(output_path),
            str(input_path),
        ]
        return command, output_path, extended
    if mode == 'chan':
        output_path = job_dir / 'chan.out'
        command = [
            str(binary),
            '-ha',
            '-chan',
            str(params.get('probeRadius', '1.86')),
            str(output_path),
            str(input_path),
        ]
        return command, output_path, False
    if mode == 'sa':
        output_path = job_dir / 'sa.out'
        command = [
            str(binary),
            '-ha',
            '-sa',
            str(params.get('chanRadius', '1.86')),
            str(params.get('probeRadius', '1.86')),
            str(params.get('numSamples', '5000')),
            str(output_path),
            str(input_path),
        ]
        return command, output_path, False
    if mode == 'vol':
        output_path = job_dir / 'vol.out'
        command = [
            str(binary),
            '-ha',
            '-vol',
            str(params.get('chanRadius', '1.86')),
            str(params.get('probeRadius', '1.86')),
            str(params.get('numSamples', '50000')),
            str(output_path),
            str(input_path),
        ]
        return command, output_path, False
    if mode == 'volpo':
        output_path = job_dir / 'volpo.out'
        command = [
            str(binary),
            '-ha',
            '-volpo',
            str(params.get('chanRadius', '1.86')),
            str(params.get('probeRadius', '1.86')),
            str(params.get('numSamples', '50000')),
            str(output_path),
            str(input_path),
        ]
        return command, output_path, False
    raise ValueError(f'Unsupported ZEO++ mode: {mode}')


def parse_output(mode: str, text: str, extended: bool) -> dict[str, Any]:
    if mode == 'psd':
        return parse_psd_output(text)
    if mode == 'res':
        return parse_res_output(text, extended)
    if mode == 'chan':
        return parse_chan_output(text)
    if mode == 'sa':
        return parse_surface_area_output(text)
    if mode == 'vol':
        return parse_volume_output(text, False)
    if mode == 'volpo':
        return parse_volume_output(text, True)
    raise ValueError(f'Unsupported ZEO++ mode: {mode}')


def run_workflow(
    job_id: str,
    job_dir: Path,
    input_path: Path,
    mode: str,
    params: dict[str, Any],
    advance: Callable[[str, int], None],
    current_progress: Callable[[], int],
) -> dict[str, Any]:
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    if zeopp_binary is None:
        raise RuntimeError(zeopp_message)

    command, output_path, extended = build_command(zeopp_binary, mode, input_path, params)
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    advance('launching', 4)

    with suppress_windows_error_dialogs():
        process = subprocess.Popen(
            command,
            cwd=str(job_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=build_zeopp_env(),
            creationflags=creation_flags_for_zeopp(),
        )

        import threading

        stdout_thread = threading.Thread(
            target=drain_pipe,
            args=(process.stdout, stdout_lines),
            kwargs={'mode': mode, 'advance': advance, 'current_progress': current_progress},
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=drain_pipe,
            args=(process.stderr, stderr_lines),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        try:
            returncode = process.wait(timeout=300)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait(timeout=10)
            raise TimeoutError(f'ZEO++ {mode.upper()} timed out after 300 seconds.') from exc

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

    stdout_text = ''.join(stdout_lines)
    stderr_text = ''.join(stderr_lines)
    output_exists = output_path.exists() and output_path.stat().st_size > 0
    if returncode != 0 and not output_exists:
        raise RuntimeError(f'ZEO++ {mode.upper()} execution failed.')

    advance('parsing_output', 97)
    output_text = output_path.read_text(encoding='utf-8', errors='replace')
    parsed = parse_output(mode, output_text, extended)
    result = {
        'jobId': job_id,
        **parsed,
        'rawOutput': output_text,
        'stdout': stdout_text,
        'stderr': stderr_text,
        'returnCode': returncode,
        'artifacts': [{'name': output_path.name, 'url': f'./api/artifacts/{job_id}/{output_path.name}'}],
    }
    if returncode != 0:
        result['warning'] = f'ZEO++ returned a non-zero exit code on Windows, but the {mode.upper()} output file was written successfully.'
    return result
