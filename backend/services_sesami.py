from __future__ import annotations

import importlib.util
import io
import os
import site
import sys
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable


def _add_dependency_path(candidate: Path) -> None:
    if not candidate.exists() or str(candidate) in sys.path:
        return

    numpy_core = candidate / 'numpy' / '_core'
    if numpy_core.exists():
        binaries = list(numpy_core.glob('_multiarray_umath*.pyd'))
        if binaries:
            python_tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
            if not any(python_tag in binary.name for binary in binaries):
                return

    sys.path.insert(0, str(candidate))


ROOT = Path(__file__).resolve().parents[1]
PYDEPS = ROOT / 'pydeps'
SESAMI_ROOT = ROOT / 'vendor' / 'SESAMI_web'
_add_dependency_path(PYDEPS)

USER_SITE = Path(site.getusersitepackages())
if USER_SITE.exists() and os.access(USER_SITE, os.R_OK) and str(USER_SITE) not in sys.path:
    sys.path.insert(0, str(USER_SITE))

import numpy as np
import pandas as pd
import scipy

if not hasattr(scipy, 'log'):
    scipy.log = np.log
if not hasattr(scipy, 'sqrt'):
    scipy.sqrt = np.sqrt

os.environ.setdefault('MPLBACKEND', 'Agg')

ModernBETAn = None
modern_betml = None
BETAn = None
SESAMI_PACKAGE_VERSION = None
SESAMI_MODERN_ENGINE = 'SESAMI 2.9'
SESAMI_LEGACY_ENGINE = 'SESAMI 1.0'
SESAMI_STATUS_MESSAGE = 'SESAMI engines are not available.'

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
        from SESAMI.predict import betml as modern_betml  # type: ignore
    except Exception:
        modern_betml = None

    try:
        SESAMI_PACKAGE_VERSION = version('sesami')
    except PackageNotFoundError:
        SESAMI_PACKAGE_VERSION = 'unknown'
    SESAMI_MODERN_ENGINE = f'SESAMI {SESAMI_PACKAGE_VERSION}'
except Exception:
    ModernBETAn = None
    modern_betml = None

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
    sesami_status_parts.append(f'{SESAMI_MODERN_ENGINE} BET ready')
if modern_betml is not None:
    sesami_status_parts.append(f'{SESAMI_MODERN_ENGINE} BET-ML ready')
if BETAn is not None:
    sesami_status_parts.append(f'{SESAMI_LEGACY_ENGINE} legacy BET ready')
if sesami_status_parts:
    SESAMI_STATUS_MESSAGE = '; '.join(sesami_status_parts) + '.'

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


@contextmanager
def pushd(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def pack_sesami_points(frame: pd.DataFrame) -> list[dict[str, float | None]]:
    packed: list[dict[str, float | None]] = []
    if frame is None or frame.empty:
        return packed

    for _, row in frame.iterrows():
        packed.append(
            {
                'P_rel': round(float(row['P_rel']), 8) if 'P_rel' in frame.columns and pd.notna(row.get('P_rel')) else None,
                'Pressure': round(float(row['Pressure']), 8) if 'Pressure' in frame.columns and pd.notna(row.get('Pressure')) else None,
                'Loading': round(float(row['Loading']), 8) if 'Loading' in frame.columns and pd.notna(row.get('Loading')) else None,
            }
        )
    return packed


def collect_sesami_plots(job_dir: Path, job_id: str) -> list[dict[str, str]]:
    plots: list[dict[str, str]] = []
    for name in PLOT_CANDIDATES:
        path = job_dir / name
        if path.exists() and path.stat().st_size > 0:
            plots.append({'name': name, 'url': f'./api/artifacts/{job_id}/{name}'})
    return plots


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
        'cmÃ‚Â³/g': 0.044615,
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


def parse_upload(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == '.csv':
        return parse_csv_upload(raw_bytes)
    if suffix == '.aif':
        return parse_aif_upload(raw_bytes)
    raise ValueError('Unsupported file type. Please upload .csv or .aif.')


def normalize_pressure_frame(data: pd.DataFrame, gas: str) -> pd.DataFrame:
    frame = data.copy()
    pressure_series = pd.to_numeric(frame['Pressure'], errors='coerce')
    max_pressure = float(pressure_series.max()) if len(pressure_series.index) else 0.0
    min_pressure = float(pressure_series.min()) if len(pressure_series.index) else 0.0

    # Many lab CSV files provide relative pressure p/p0 rather than absolute pressure in Pa.
    # BET-ML in SESAMI 2 expects absolute pressure bins, so we normalize here based on the chosen gas p0.
    if 0 <= min_pressure and max_pressure <= 1.2:
        frame['Pressure'] = pressure_series * GAS_SETTINGS[gas]['p0']

    return frame

def get_sesami_status() -> tuple[bool, str]:
    return (ModernBETAn is not None or BETAn is not None or modern_betml is not None), SESAMI_STATUS_MESSAGE


def normalize_advanced_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}

    def pick(key: str, default: Any):
        value = raw.get(key)
        return default if value in (None, '') else value

    return {
        'R2 cutoff': float(pick('r2Cutoff', BET_DEFAULTS['R2 cutoff'])),
        'R2 min': float(pick('r2Min', BET_DEFAULTS['R2 min'])),
        'dpi': int(pick('dpi', BET_DEFAULTS['dpi'])),
        'font size': int(pick('fontSize', BET_DEFAULTS['font size'])),
        'font type': str(pick('fontType', BET_DEFAULTS['font type'])),
        'legend': 'Yes' if str(pick('legend', True)).lower() not in {'false', '0', 'no'} else 'No',
    }


def _prepare_input_frame(data: pd.DataFrame) -> pd.DataFrame:
    prepared = data[['Pressure', 'Loading']].copy()
    if prepared.iloc[0]['Pressure'] == 0 and len(prepared) > 1:
        prepared.loc[0, 'Pressure'] = prepared.iloc[1]['Pressure'] / 2
    return prepared


def build_modern_sesami_analyzer(gas: str, advanced: dict[str, Any]):
    settings = GAS_SETTINGS[gas]
    plot_settings = {
        'font size': advanced['font size'],
        'R2 cutoff': advanced['R2 cutoff'],
        'R2 min': advanced['R2 min'],
        'dpi': advanced['dpi'],
        'font type': advanced['font type'],
        'save fig': True,
        'legend': advanced['legend'],
        'gas': settings['gas_name'],
        'custom saturation pressure': settings['p0'],
    }
    if gas == 'Nitrogen':
        plot_settings['custom temperature'] = settings['temperature']
    analyzer = ModernBETAn(settings['gas_name'], settings['temperature'], 4, plot_settings)
    return analyzer, plot_settings


def build_metric_payload(result_dict: dict[str, Any] | None) -> dict[str, Any] | None:
    if result_dict is None:
        return None
    return {
        'area': round(float(result_dict['A_BET']), 3),
        'qm': round(float(result_dict['qm']), 4),
        'C': round(float(result_dict['C']), 4),
        'r2': round(float(result_dict['R2_linear_region']), 6),
        'con3': result_dict.get('con3'),
        'con4': result_dict.get('con4'),
    }


def build_linear_region(result_dict: dict[str, Any] | None, prepared: pd.DataFrame) -> tuple[dict[str, Any] | None, list[dict[str, float | None]]]:
    if result_dict is None:
        return None, []

    mask = (
        (prepared['Pressure'] >= result_dict['low_P_linear_region'])
        & (prepared['Pressure'] <= result_dict['high_P_linear_region'])
    )
    points = prepared.loc[mask, [column for column in ['P_rel', 'Pressure', 'Loading'] if column in prepared.columns]]
    payload = {
        'count': int(len(points.index)),
        'lowPressurePa': float(result_dict['low_P_linear_region']),
        'highPressurePa': float(result_dict['high_P_linear_region']),
    }
    return payload, pack_sesami_points(points)


def run_modern_bundle(
    job_id: str,
    job_dir: Path,
    data: pd.DataFrame,
    gas: str,
    advanced: dict[str, Any],
    advance: Callable[[str, int], None],
) -> dict[str, Any]:
    if ModernBETAn is None:
        raise RuntimeError('SESAMI modern BET engine is not available in this environment.')

    settings = GAS_SETTINGS[gas]
    normalized_data = normalize_pressure_frame(data, gas)
    prepared_data = _prepare_input_frame(normalized_data)
    input_csv = job_dir / 'input.csv'

    advance('preparing_input', 12)
    prepared_data.to_csv(input_csv, index=False)

    advance('initializing_engine', 28)
    analyzer, plot_settings = build_modern_sesami_analyzer(gas, advanced)

    advance('preparing_isotherm', 46)
    prepared = analyzer.prepdata(
        prepared_data,
        pressure_col='Pressure',
        loading_col='Loading',
        p0=settings['p0'],
    )

    advance('running_fit', 74)
    with pushd(job_dir):
        bet_result, bet_esw_result = analyzer.generatesummary(prepared, plot_settings, 3, ['Pressure', 'Loading'])

    if isinstance(bet_result, str):
        raise ValueError(f'SESAMI BET failed: {bet_result}')
    if isinstance(bet_esw_result, str):
        bet_esw_result = None

    advance('rendering_plots', 88)
    point_columns = [column for column in ['P_rel', 'Pressure', 'Loading'] if column in prepared.columns]
    return {
        'prepared': prepared[point_columns].copy(),
        'bet': bet_result,
        'bet_esw': bet_esw_result,
        'plots': collect_sesami_plots(job_dir, job_id),
        'input_csv': input_csv,
        'advanced': advanced,
    }


def run_legacy_bet(
    job_dir: Path,
    data: pd.DataFrame,
    gas: str,
    advance: Callable[[str, int], None],
) -> dict[str, Any]:
    if BETAn is None:
        raise RuntimeError('SESAMI legacy BET engine is not available in this environment.')

    settings = GAS_SETTINGS[gas]
    options = {**BET_DEFAULTS, 'gas': gas}
    analyzer = BETAn(gas, settings['temperature'], 4, options)

    normalized_data = normalize_pressure_frame(data, gas)
    prepared_data = _prepare_input_frame(normalized_data)
    advance('preparing_legacy', 20)
    prepared = analyzer.prepdata(prepared_data, p0=settings['p0'])

    advance('running_legacy_bet', 72)
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

    return {'prepared': prepared, 'bet': bet_result}


def build_compare_entry(label: str, engine: str, result_dict: dict[str, Any] | None, warning: str | None = None) -> dict[str, Any]:
    return {
        'label': label,
        'engine': engine,
        'metrics': build_metric_payload(result_dict),
        'warning': warning,
    }


def run_workflow(
    job_id: str,
    job_dir: Path,
    data: pd.DataFrame,
    gas: str,
    version: str,
    mode: str,
    advanced_raw: dict[str, Any] | None,
    advance: Callable[[str, int], None],
) -> dict[str, Any]:
    advanced = normalize_advanced_settings(advanced_raw)
    base_result: dict[str, Any] = {
        'jobId': job_id,
        'gas': gas,
        'version': version,
        'mode': mode,
        'plots': [],
        'points': [],
        'selectedPoints': [],
        'linearRegionPoints': [],
        'metadata': {
            'r2Cutoff': advanced['R2 cutoff'],
            'r2Min': advanced['R2 min'],
            'dpi': advanced['dpi'],
            'fontSize': advanced['font size'],
            'fontType': advanced['font type'],
            'legend': advanced['legend'] == 'Yes',
        },
    }

    if mode == 'betml' and version != '2.9':
        raise ValueError('BET-ML is only available in SESAMI 2.9.')

    if mode == 'betml':
        if modern_betml is None:
            raise RuntimeError('SESAMI BET-ML is not available in this environment.')
        normalized_data = normalize_pressure_frame(data, gas)
        prepared_data = _prepare_input_frame(normalized_data)
        input_csv = job_dir / 'input.csv'
        advance('preparing_input', 12)
        prepared_data.to_csv(input_csv, index=False)
        advance('running_betml', 76)
        prediction = float(modern_betml(str(input_csv), columns=['Pressure', 'Loading']))
        advance('packaging_result', 94)
        base_result.update(
            {
                'engine': SESAMI_MODERN_ENGINE,
                'betMl': {'area': round(prediction, 3), 'warning': None},
                'points': pack_sesami_points(prepared_data),
            }
        )
        return base_result

    if mode == 'compare':
        bundle = run_modern_bundle(job_id, job_dir, data, gas, advanced, advance)
        prepared = bundle['prepared']
        bet_dict = bundle['bet']
        bet_esw_dict = bundle['bet_esw']
        comparison = [
            build_compare_entry('BET', SESAMI_MODERN_ENGINE, bet_dict),
            build_compare_entry('BET+ESW', SESAMI_MODERN_ENGINE, bet_esw_dict, None if bet_esw_dict else 'ESW minimum was not found.'),
        ]

        if BETAn is not None:
            legacy_dir = job_dir / 'legacy_compare'
            legacy_dir.mkdir(parents=True, exist_ok=True)
            legacy_bundle = run_legacy_bet(legacy_dir, data, gas, advance)
            comparison.append(build_compare_entry('Legacy BET', SESAMI_LEGACY_ENGINE, legacy_bundle['bet']))

        if modern_betml is not None:
            prediction = float(modern_betml(str(bundle['input_csv']), columns=['Pressure', 'Loading']))
            comparison.append(
                {
                    'label': 'BET-ML',
                    'engine': SESAMI_MODERN_ENGINE,
                    'metrics': {'area': round(prediction, 3)},
                    'warning': None,
                }
            )

        linear_region, selected_points = build_linear_region(bet_dict, prepared)
        advance('packaging_result', 96)
        base_result.update(
            {
                'engine': SESAMI_MODERN_ENGINE,
                'area': build_metric_payload(bet_dict)['area'],
                'qm': build_metric_payload(bet_dict)['qm'],
                'C': build_metric_payload(bet_dict)['C'],
                'r2': build_metric_payload(bet_dict)['r2'],
                'con3': build_metric_payload(bet_dict)['con3'],
                'con4': build_metric_payload(bet_dict)['con4'],
                'plotUrl': bundle['plots'][0]['url'] if bundle['plots'] else None,
                'plots': bundle['plots'],
                'points': pack_sesami_points(prepared),
                'selectedPoints': selected_points,
                'linearRegionPoints': selected_points,
                'linearRegion': linear_region,
                'betEsw': {
                    **(build_metric_payload(bet_esw_dict) or {}),
                    'linearRegion': build_linear_region(bet_esw_dict, prepared)[0],
                    'selectedPoints': build_linear_region(bet_esw_dict, prepared)[1],
                }
                if bet_esw_dict
                else None,
                'comparison': comparison,
            }
        )
        return base_result

    if mode == 'bet-esw' and version != '2.9':
        raise ValueError('BET+ESW is only available in SESAMI 2.9.')

    if version == '1.0':
        legacy_bundle = run_legacy_bet(job_dir, data, gas, advance)
        prepared = legacy_bundle['prepared']
        bet_dict = legacy_bundle['bet']
        linear_region, selected_points = build_linear_region(bet_dict, prepared)
        advance('packaging_result', 96)
        base_result.update(
            {
                'engine': SESAMI_LEGACY_ENGINE,
                **(build_metric_payload(bet_dict) or {}),
                'plots': collect_sesami_plots(job_dir, job_id),
                'plotUrl': collect_sesami_plots(job_dir, job_id)[0]['url'] if collect_sesami_plots(job_dir, job_id) else None,
                'points': pack_sesami_points(prepared),
                'selectedPoints': selected_points,
                'linearRegionPoints': selected_points,
                'linearRegion': linear_region,
            }
        )
        return base_result

    bundle = run_modern_bundle(job_id, job_dir, data, gas, advanced, advance)
    prepared = bundle['prepared']
    bet_dict = bundle['bet']
    bet_esw_dict = bundle['bet_esw']

    primary = bet_dict if mode in {'bet', 'advanced'} else bet_esw_dict
    if primary is None:
        raise ValueError('BET+ESW could not be determined from this isotherm.')

    linear_region, selected_points = build_linear_region(primary, prepared)
    bet_esw_region, bet_esw_points = build_linear_region(bet_esw_dict, prepared)
    advance('packaging_result', 96)
    base_result.update(
        {
            'engine': SESAMI_MODERN_ENGINE,
            **(build_metric_payload(primary) or {}),
            'plotUrl': bundle['plots'][0]['url'] if bundle['plots'] else None,
            'plots': bundle['plots'],
            'points': pack_sesami_points(prepared),
            'selectedPoints': selected_points,
            'linearRegionPoints': selected_points,
            'linearRegion': linear_region,
        }
    )

    if bet_esw_dict is not None:
        base_result['betEsw'] = {
            **(build_metric_payload(bet_esw_dict) or {}),
            'linearRegion': bet_esw_region,
            'selectedPoints': bet_esw_points,
        }

    return base_result



