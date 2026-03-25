from __future__ import annotations

import ctypes
import io
import importlib.util
import os
import re
import site
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

PYDEPS = Path(__file__).resolve().parents[1] / 'pydeps'
if str(PYDEPS) not in sys.path:
    sys.path.insert(0, str(PYDEPS))

USER_SITE = site.getusersitepackages()
if USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np
import pandas as pd
import scipy
from flask import Flask, jsonify, request, send_from_directory

if not hasattr(scipy, 'log'):
    scipy.log = np.log
if not hasattr(scipy, 'sqrt'):
    scipy.sqrt = np.sqrt

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / 'backend_artifacts'
ARTIFACTS_DIR.mkdir(exist_ok=True)
DIST_DIR = ROOT / 'dist'
ZEOPP_RUNTIME_DIR = ROOT / 'vendor' / 'zeopp-lsmo' / 'zeo++'
ZEOPP_TOOLCHAIN_BIN = ROOT / 'zeopp-toolchain' / 'Library' / 'mingw-w64' / 'bin'
ZEOPP_TOOLCHAIN_USR_BIN = ROOT / 'zeopp-toolchain' / 'Library' / 'usr' / 'bin'
SESAMI_ROOT = ROOT / 'vendor' / 'SESAMI_web'

os.environ.setdefault('MPLBACKEND', 'Agg')

ModernBETAn = None
BETAn = None
SESAMI_PACKAGE_VERSION = None
SESAMI_MODERN_ENGINE = 'SESAMI 2.9'
SESAMI_LEGACY_ENGINE = 'SESAMI 1.0'
SESAMI_STATUS_MESSAGE = 'SESAMI BET engines are not available.'

try:
    import matplotlib as _mpl

    _original_mpl_use = _mpl.use

    def _safe_mpl_use(backend: str, *args: Any, **kwargs: Any):
        if str(backend).lower() == 'tkagg':
            backend = 'Agg'
        return _original_mpl_use(backend, *args, **kwargs)

    _mpl.use = _safe_mpl_use
    try:
        from SESAMI.bet import BETAn as ModernBETAn  # type: ignore
    finally:
        _mpl.use = _original_mpl_use

    try:
        SESAMI_PACKAGE_VERSION = version('sesami')
    except PackageNotFoundError:
        SESAMI_PACKAGE_VERSION = 'unknown'
    SESAMI_MODERN_ENGINE = f'SESAMI {SESAMI_PACKAGE_VERSION}'
except Exception:
    ModernBETAn = None

try:
    legacy_betan_path = SESAMI_ROOT / 'SESAMI' / 'SESAMI_1' / 'betan.py'
    legacy_spec = importlib.util.spec_from_file_location('chemex_legacy_sesami_betan', legacy_betan_path)
    if legacy_spec is None or legacy_spec.loader is None:
        raise RuntimeError('Failed to load the vendored SESAMI legacy module.')
    legacy_module = importlib.util.module_from_spec(legacy_spec)
    legacy_spec.loader.exec_module(legacy_module)
    BETAn = legacy_module.BETAn
except Exception:
    BETAn = None

sesami_status_parts: list[str] = []
if ModernBETAn is not None:
    sesami_status_parts.append(f'{SESAMI_MODERN_ENGINE} fitbet ready')
if BETAn is not None:
    sesami_status_parts.append(f'{SESAMI_LEGACY_ENGINE} legacy BET ready')
if sesami_status_parts:
    SESAMI_STATUS_MESSAGE = '; '.join(sesami_status_parts) + '.'
app = Flask(__name__)

BET_DEFAULTS = {
    'font size': 12,
    'font type': 'DejaVu Sans',
    'legend': 'Yes',
    'R2 cutoff': 0.9995,
    'R2 min': 0.998,
    'dpi': 150,
    'scope': 'BET',
    'ML': 'No',
    'custom adsorbate': 'No',
}

GAS_SETTINGS = {
    'Argon': {'temperature': 87.0, 'p0': 100000.0, 'adsorbate': 'Ar', 'gas_name': 'Argon'},
    'Nitrogen': {'temperature': 77.0, 'p0': 100000.0, 'adsorbate': 'N2', 'gas_name': 'Nitrogen'},
}

PLOT_CANDIDATES = ['isotherm.png', 'BETPlot.png', 'BETPlotLinear.png', 'BETESWPlot.png', 'ESWPlot.png', 'multiplot_0.png']
ACTIVE_JOB_STATUSES = {'queued', 'running'}
UNSET = object()
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002
SEM_NOOPENFILEERRORBOX = 0x8000


def parse_csv_upload(raw_bytes: bytes) -> pd.DataFrame:
    text = raw_bytes.decode('utf-8-sig', errors='replace')
    df = pd.read_csv(io.StringIO(text), sep=None, engine='python')
    if df.shape[1] < 2:
        raise ValueError('CSV file must contain at least two columns.')

    df = df.iloc[:, :2].copy()
    df.columns = ['Pressure', 'Loading']
    df['Pressure'] = pd.to_numeric(df['Pressure'], errors='coerce')
    df['Loading'] = pd.to_numeric(df['Loading'], errors='coerce')
    df = df.dropna().sort_values('Pressure').reset_index(drop=True)

    if len(df) < 4:
        raise ValueError('BET analysis needs at least 4 valid rows.')
    if (df['Pressure'] <= 0).all():
        raise ValueError('Pressure values must include positive entries.')
    if (df['Loading'] < 0).any():
        raise ValueError('Loading values must be non-negative.')

    return df


def parse_aif_upload(raw_bytes: bytes) -> pd.DataFrame:
    text = raw_bytes.decode('utf-8-sig', errors='replace')
    content = text.splitlines()

    start_idx = None
    for idx, line in enumerate(content):
        if (
            line[:5] == 'loop_'
            and idx + 3 < len(content)
            and content[idx + 1][:16] == '_adsorp_pressure'
            and content[idx + 2][:10] == '_adsorp_p0'
            and content[idx + 3][:14] == '_adsorp_amount'
        ):
            start_idx = idx
            break

    if start_idx is None:
        raise ValueError('AIF file is missing the adsorption loop block.')

    adsorption_rows: list[str] = []
    cursor = start_idx + 4
    while cursor < len(content):
        line = content[cursor]
        if not line.strip() or line.startswith('_') or line.startswith('loop_'):
            break
        adsorption_rows.append(line)
        cursor += 1

    if not adsorption_rows:
        raise ValueError('AIF file does not contain adsorption rows.')

    units_loading = None
    units_pressure = None
    for line in content:
        if '_units_loading' in line:
            units_loading = line.replace("'", '').split()[1]
        if '_units_pressure' in line:
            units_pressure = line.replace("'", '').split()[1]

    if units_loading is None or units_pressure is None:
        raise ValueError('AIF file must declare both loading and pressure units.')

    pressure_scale = {
        'Pa': 1.0,
        'pascal': 1.0,
        'bar': 100000.0,
        'torr': 133.322,
        'mbar': 100.0,
        'mb': 100.0,
    }.get(units_pressure)
    if pressure_scale is None:
        raise ValueError(f'Unsupported AIF pressure unit: {units_pressure}')

    loading_scale = {
        'mol/kg': 1.0,
        'mmol/g': 1.0,
        'cm³/g': 0.044615,
        'cmÂ³/g': 0.044615,
    }.get(units_loading)
    if loading_scale is None:
        raise ValueError(f'Unsupported AIF loading unit: {units_loading}')

    rows = []
    for line in adsorption_rows:
        parts = line.split()
        if len(parts) < 3:
            continue
        pressure = float(parts[0]) * pressure_scale
        loading = float(parts[2]) * loading_scale
        rows.append({'Pressure': pressure, 'Loading': loading})

    df = pd.DataFrame(rows)
    if len(df) < 4:
        raise ValueError('AIF adsorption block has too few usable rows for BET analysis.')

    return df.sort_values('Pressure').reset_index(drop=True)


@contextmanager
def pushd(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


@contextmanager
def suppress_windows_error_dialogs():
    if os.name != 'nt':
        yield
        return

    previous_mode = ctypes.windll.kernel32.SetErrorMode(
        SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
    )
    try:
        yield
    finally:
        ctypes.windll.kernel32.SetErrorMode(previous_mode)


def collect_sesami_plots(job_dir: Path) -> list[dict[str, str]]:
    plots: list[dict[str, str]] = []
    for filename in PLOT_CANDIDATES:
        candidate = job_dir / filename
        if candidate.exists():
            plots.append({'name': filename, 'url': f'/api/artifacts/{job_dir.name}/{filename}'})
    return plots


def pack_sesami_points(frame: pd.DataFrame) -> list[dict[str, float | None]]:
    if frame.empty:
        return []

    packed: list[dict[str, float | None]] = []
    for _, row in frame.iterrows():
        packed.append(
            {
                'P_rel': round(float(row['P_rel']), 8) if 'P_rel' in frame.columns and pd.notna(row.get('P_rel')) else None,
                'Pressure': round(float(row['Pressure']), 8) if 'Pressure' in frame.columns and pd.notna(row.get('Pressure')) else None,
                'Loading': round(float(row['Loading']), 8) if 'Loading' in frame.columns and pd.notna(row.get('Loading')) else None,
            }
        )
    return packed


def create_job(workflow: str, filename: str) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job_dir = ARTIFACTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        'jobId': job_id,
        'workflow': workflow,
        'filename': filename,
        'status': 'queued',
        'progress': 0,
        'stage': 'queued',
        'result': None,
        'error': None,
        'warning': None,
        'createdAt': time.time(),
        'updatedAt': time.time(),
        '_jobDir': str(job_dir),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    return job


def serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if not key.startswith('_')}


def get_job(job_id: str) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        return serialize_job(job)


def advance_job(job_id: str, stage: str, progress: int) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        current_progress = int(job.get('progress', 0))
        next_progress = max(current_progress, int(progress))
        if next_progress != current_progress or job.get('stage') != stage:
            job['progress'] = next_progress
            job['stage'] = stage
            if job.get('status') == 'queued':
                job['status'] = 'running'
            job['updatedAt'] = time.time()


def finish_job(
    job_id: str,
    *,
    status: str,
    result: Any = UNSET,
    error: Any = UNSET,
    warning: Any = UNSET,
) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job['status'] = status
        job['stage'] = status
        job['progress'] = 100
        if result is not UNSET:
            job['result'] = result
        if error is not UNSET:
            job['error'] = error
        if warning is not UNSET:
            job['warning'] = warning
        job['updatedAt'] = time.time()


def fail_job(job_id: str, error: str, warning: str | None = None) -> None:
    finish_job(job_id, status='failed', error=error, warning=warning)


def build_modern_sesami_analyzer(gas: str):
    settings = GAS_SETTINGS[gas]
    plot_settings = {
        'font size': 12,
        'R2 cutoff': 0.9995,
        'R2 min': 0.998,
        'dpi': 150,
        'font type': 'DejaVu Sans',
        'save fig': True,
        'legend': 'Yes',
        'gas': settings['gas_name'],
        'custom saturation pressure': settings['p0'],
    }
    if gas == 'Nitrogen':
        plot_settings['custom temperature'] = settings['temperature']
    analyzer = ModernBETAn(settings['gas_name'], settings['temperature'], 4, plot_settings)
    return analyzer, plot_settings


def build_sesami_result(
    job_id: str,
    gas: str,
    engine: str,
    bet_result: dict[str, Any],
    points: pd.DataFrame,
    linear_region: pd.DataFrame,
    plots: list[dict[str, str]],
) -> dict[str, Any]:
    plots = list(plots)
    linear_points = pack_sesami_points(linear_region)
    return {
        'jobId': job_id,
        'gas': gas,
        'engine': engine,
        'area': round(float(bet_result['A_BET']), 3),
        'qm': round(float(bet_result['qm']), 4),
        'C': round(float(bet_result['C']), 4),
        'r2': round(float(bet_result['R2_linear_region']), 6),
        'con3': bet_result['con3'],
        'con4': bet_result['con4'],
        'linearRegion': {
            'count': int(len(linear_region.index)),
            'lowPressurePa': float(bet_result['low_P_linear_region']),
            'highPressurePa': float(bet_result['high_P_linear_region']),
        },
        'plotUrl': plots[0]['url'] if plots else None,
        'plots': plots,
        'points': pack_sesami_points(points),
        'selectedPoints': linear_points,
        'linearRegionPoints': linear_points,
    }

def run_sesami_modern(job_id: str, data: pd.DataFrame, gas: str) -> dict[str, Any]:
    if ModernBETAn is None:
        raise RuntimeError('SESAMI 2.9 BET engine is not available in this environment.')

    job_dir = ARTIFACTS_DIR / job_id
    settings = GAS_SETTINGS[gas]
    prepared_data = data[['Pressure', 'Loading']].copy()
    if prepared_data.iloc[0]['Pressure'] == 0 and len(prepared_data) > 1:
        prepared_data.loc[0, 'Pressure'] = prepared_data.iloc[1]['Pressure'] / 2

    advance_job(job_id, 'preparing_input', 12)
    prepared_data.to_csv(job_dir / 'input.csv', index=False)

    advance_job(job_id, 'initializing_engine', 28)
    analyzer, plot_settings = build_modern_sesami_analyzer(gas)

    advance_job(job_id, 'preparing_isotherm', 48)
    prepared = analyzer.prepdata(
        prepared_data,
        pressure_col='Pressure',
        loading_col='Loading',
        p0=settings['p0'],
    )

    advance_job(job_id, 'running_bet', 72)
    with pushd(job_dir):
        bet_result, _ = analyzer.generatesummary(prepared, plot_settings, 3, ['Pressure', 'Loading'])

    advance_job(job_id, 'rendering_plots', 90)
    point_columns = [column for column in ['P_rel', 'Pressure', 'Loading'] if column in prepared.columns]
    linear_mask = (
        (prepared['Pressure'] >= bet_result['low_P_linear_region'])
        & (prepared['Pressure'] <= bet_result['high_P_linear_region'])
    )
    linear_region = prepared.loc[linear_mask, point_columns]

    advance_job(job_id, 'packaging_result', 96)
    return build_sesami_result(job_id, gas, SESAMI_MODERN_ENGINE, bet_result, prepared[point_columns], linear_region, collect_sesami_plots(job_dir))


def run_sesami_legacy(job_id: str, data: pd.DataFrame, gas: str) -> dict[str, Any]:
    if BETAn is None:
        raise RuntimeError('SESAMI legacy BET engine is not available in this environment.')

    job_dir = ARTIFACTS_DIR / job_id
    settings = GAS_SETTINGS[gas]
    options = {**BET_DEFAULTS, 'gas': gas}

    advance_job(job_id, 'preparing_input', 12)
    analyzer = BETAn(gas, settings['temperature'], 4, options)

    prepared_data = data.copy()
    if prepared_data.iloc[0]['Pressure'] == 0 and len(prepared_data) > 1:
        prepared_data.loc[0, 'Pressure'] = prepared_data.iloc[1]['Pressure'] / 2

    advance_job(job_id, 'preparing_isotherm', 48)
    prepared = analyzer.prepdata(prepared_data, p0=settings['p0'])

    advance_job(job_id, 'running_bet', 72)
    bet_result, _ = analyzer.generatesummary(
        prepared,
        options,
        f'{SESAMI_ROOT}{os.sep}',
        0,
        sumpath=str(job_dir),
        saveindividual='Yes',
    )

    if isinstance(bet_result, str):
        raise ValueError(f'SESAMI BET failed: {bet_result}')

    advance_job(job_id, 'rendering_plots', 90)
    point_columns = [column for column in ['P_rel', 'Pressure', 'Loading'] if column in prepared.columns]
    linear_mask = (
        (prepared['Pressure'] >= bet_result['low_P_linear_region'])
        & (prepared['Pressure'] <= bet_result['high_P_linear_region'])
    )
    linear_region = prepared.loc[linear_mask, point_columns]

    advance_job(job_id, 'packaging_result', 96)
    return build_sesami_result(
        job_id,
        gas,
        SESAMI_LEGACY_ENGINE,
        bet_result,
        prepared[point_columns],
        linear_region,
        collect_sesami_plots(job_dir),
    )


def sesami_bet_worker(job_id: str, data: pd.DataFrame, gas: str, sesami_version: str) -> None:
    try:
        if sesami_version == '1.0':
            result = run_sesami_legacy(job_id, data, gas)
        elif sesami_version == '2.9':
            result = run_sesami_modern(job_id, data, gas)
        else:
            raise ValueError(f'Unsupported SESAMI version: {sesami_version}')
        finish_job(job_id, status='completed', result=result)
    except Exception as exc:
        fail_job(job_id, str(exc))

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


def parse_psd_output(text: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for line in text.splitlines():
        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
        if len(values) >= 2:
            rows.append({'diameter': float(values[0]), 'value': float(values[1])})
    return rows


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


def update_zeopp_progress_from_line(job_id: str, line: str) -> None:
    text = line.strip().lower()
    if not text:
        return

    job = get_job(job_id)
    current_progress = int(job['progress']) if job else 0

    if 'opening file:' in text:
        advance_job(job_id, 'reading_structure', 10)
    elif 'starting voronoi decomposition' in text and current_progress < 35:
        advance_job(job_id, 'initial_voronoi', 24)
    elif 'finished voronoi decomposition' in text and current_progress < 45:
        advance_job(job_id, 'routing_network', 38)
    elif 'command 0  -psd' in text:
        advance_job(job_id, 'psd_setup', 48)
    elif 'starting voronoi decomposition' in text and current_progress >= 45:
        advance_job(job_id, 'psd_voronoi', 58)
    elif 'finding channels and pockets' in text:
        advance_job(job_id, 'finding_channels', 72)
    elif 'identified' in text and 'channels' in text:
        advance_job(job_id, 'classifying_pores', 82)
    elif 'pore size distribution calculated.' in text:
        advance_job(job_id, 'writing_output', 94)


def drain_pipe(pipe, buffer: list[str], job_id: str | None = None, parse_progress: bool = False) -> None:
    if pipe is None:
        return
    try:
        for line in iter(pipe.readline, ''):
            if not line:
                break
            buffer.append(line)
            if parse_progress and job_id is not None:
                update_zeopp_progress_from_line(job_id, line)
    finally:
        pipe.close()


def creation_flags_for_zeopp() -> int:
    flags = 0
    if os.name == 'nt' and hasattr(subprocess, 'CREATE_NO_WINDOW'):
        flags |= subprocess.CREATE_NO_WINDOW
    return flags


def build_zeopp_result(job_id: str, output_text: str, stdout_text: str, stderr_text: str, returncode: int) -> dict[str, Any]:
    result = {
        'jobId': job_id,
        'rows': parse_psd_output(output_text),
        'rawOutput': output_text,
        'stdout': stdout_text,
        'stderr': stderr_text,
        'returnCode': returncode,
    }
    if returncode != 0:
        result['warning'] = 'ZEO++ returned a non-zero exit code on Windows, but the PSD output file was written successfully.'
    return result


def zeopp_psd_worker(job_id: str, input_path: Path, chan_radius: str, probe_radius: str, num_samples: str) -> None:
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    if zeopp_binary is None:
        fail_job(job_id, zeopp_message)
        return

    job_dir = ARTIFACTS_DIR / job_id
    output_path = job_dir / 'psd.out'
    command = [
        str(zeopp_binary),
        '-psd',
        str(chan_radius),
        str(probe_radius),
        str(num_samples),
        str(output_path),
        str(input_path),
    ]

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    advance_job(job_id, 'launching', 4)

    try:
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

            stdout_thread = threading.Thread(
                target=drain_pipe,
                args=(process.stdout, stdout_lines, job_id, True),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=drain_pipe,
                args=(process.stderr, stderr_lines, None, False),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()

            try:
                returncode = process.wait(timeout=300)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
                raise TimeoutError('ZEO++ PSD timed out after 300 seconds.')

            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
    except Exception as exc:
        fail_job(job_id, str(exc))
        return

    stdout_text = ''.join(stdout_lines)
    stderr_text = ''.join(stderr_lines)
    output_exists = output_path.exists() and output_path.stat().st_size > 0
    if returncode != 0 and not output_exists:
        fail_job(job_id, 'ZEO++ PSD execution failed.')
        with JOBS_LOCK:
            JOBS[job_id]['result'] = {
                'stdout': stdout_text,
                'stderr': stderr_text,
                'command': command,
            }
        return

    advance_job(job_id, 'parsing_output', 97)
    output_text = output_path.read_text(encoding='utf-8', errors='replace')
    result = build_zeopp_result(job_id, output_text, stdout_text, stderr_text, returncode)
    finish_job(job_id, status='completed', result=result, warning=result.get('warning'))


@app.get('/')
def index() -> Any:
    if DIST_DIR.exists():
        return send_from_directory(DIST_DIR, 'index.html')
    return jsonify({'error': 'Frontend build not found. Run npm run build first.'}), 503


@app.get('/assets/<path:filename>')
def frontend_assets(filename: str) -> Any:
    return send_from_directory(DIST_DIR / 'assets', filename)


@app.get('/<path:filename>')
def frontend_root_assets(filename: str) -> Any:
    target = DIST_DIR / filename
    if target.is_file():
        return send_from_directory(DIST_DIR, filename)
    return jsonify({'error': 'Not found'}), 404


@app.get('/api/health')
def health() -> Any:
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    return jsonify(
        {
            'status': 'ok',
            'sesamiReady': ModernBETAn is not None or BETAn is not None,
            'sesamiMessage': SESAMI_STATUS_MESSAGE,
            'zeoppReady': zeopp_binary is not None,
            'zeoppMessage': zeopp_message,
        }
    )


@app.get('/api/zeopp/status')
def zeopp_status() -> Any:
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    return jsonify(
        {
            'available': zeopp_binary is not None,
            'binaryPath': str(zeopp_binary) if zeopp_binary else None,
            'message': zeopp_message,
        }
    )


@app.get('/api/jobs/<job_id>')
def job_status(job_id: str) -> Any:
    job = get_job(job_id)
    if job is None:
        return jsonify({'error': 'Job not found.'}), 404
    return jsonify(job)


@app.post('/api/sesami/bet')
def sesami_bet() -> Any:
    upload = request.files.get('file')
    gas = request.form.get('gas', 'Argon')
    sesami_version = request.form.get('version', '2.9')

    if sesami_version not in {'2.9', '1.0'}:
        return jsonify({'error': 'Unsupported SESAMI version. Choose 2.9 or 1.0.'}), 400

    if upload is None or not upload.filename:
        return jsonify({'error': 'Please upload a CSV or AIF file.'}), 400

    raw_bytes = upload.read()
    suffix = Path(upload.filename).suffix.lower()

    try:
        if suffix == '.csv':
            data = parse_csv_upload(raw_bytes)
        elif suffix == '.aif':
            data = parse_aif_upload(raw_bytes)
        else:
            return jsonify({'error': 'Unsupported file type. Please upload .csv or .aif.'}), 400
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

    job = create_job('sesami', upload.filename)
    job_dir = ARTIFACTS_DIR / job['jobId']
    (job_dir / upload.filename).write_bytes(raw_bytes)

    response_job = serialize_job(job)
    worker = threading.Thread(target=sesami_bet_worker, args=(job['jobId'], data, gas, sesami_version), daemon=True)
    worker.start()
    return jsonify(response_job), 202

@app.post('/api/zeopp/psd')
def zeopp_psd() -> Any:
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    if zeopp_binary is None:
        return (
            jsonify(
                {
                    'error': zeopp_message,
                    'hint': 'Compile ZEO++ and point CHEMEX_ZEOPP_BIN to the compiled network binary, or keep the bundled Windows runtime in vendor/zeopp-lsmo/zeo++.',
                }
            ),
            503,
        )

    upload = request.files.get('file')
    if upload is None or not upload.filename:
        return jsonify({'error': 'Please upload a structure file.'}), 400

    chan_radius = request.form.get('chanRadius', '1.86')
    probe_radius = request.form.get('probeRadius', '1.86')
    num_samples = request.form.get('numSamples', '10000')

    raw_bytes = upload.read()
    job = create_job('zeopp', upload.filename)
    job_dir = ARTIFACTS_DIR / job['jobId']
    input_path = job_dir / upload.filename
    input_path.write_bytes(raw_bytes)

    response_job = serialize_job(job)
    worker = threading.Thread(
        target=zeopp_psd_worker,
        args=(job['jobId'], input_path, str(chan_radius), str(probe_radius), str(num_samples)),
        daemon=True,
    )
    worker.start()
    return jsonify(response_job), 202


@app.get('/api/artifacts/<job_id>/<path:filename>')
def artifacts(job_id: str, filename: str) -> Any:
    return send_from_directory(ARTIFACTS_DIR / job_id, filename)


if __name__ == '__main__':
    port = int(os.getenv('CHEMEX_PORT', '8000'))
    app.run(host='127.0.0.1', port=port, debug=False)
