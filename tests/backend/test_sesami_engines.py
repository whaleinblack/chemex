"""Real-engine benchmarks; require sesami==2.9 and vendored legacy dependencies."""
from pathlib import Path

import pytest

from backend import services_sesami as s

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mode,version,area', [
    ('bet', '2.9', 2430.910), ('bet-esw', '2.9', 2346.735),
    ('betml', '2.9', 2099.055), ('compare', '2.9', 2430.910),
    ('bet', '1.0', 2430.910),
])
def test_real_sesami_example(tmp_path, mode, version, area):
    if version == '1.0' and s.BETAn is None:
        pytest.skip('Legacy engine unavailable')
    if version == '2.9' and s.ModernBETAn is None:
        pytest.skip('Install sesami==2.9')
    if mode in {'betml', 'compare'} and s.modern_betml is None:
        pytest.skip('BET-ML dependencies unavailable')
    source = ROOT / 'vendor/SESAMI_web/example_input/example_loading_data.csv'
    data = s.parse_upload(source.name, source.read_bytes())
    result = s.run_workflow('test', tmp_path, data, 'Argon', version, mode, {}, lambda *args: None)
    actual = result['betMl']['area'] if mode == 'betml' else result['area']
    assert actual == pytest.approx(area, abs=0.01)
    assert result['mode'] == mode
    if mode != 'betml':
        assert result['plots']
        assert result['selectedPoints']
    if mode == 'compare':
        labels = {entry['label'] for entry in result['comparison']}
        assert {'BET', 'BET+ESW', 'BET-ML'} <= labels
        if s.BETAn is not None:
            assert 'Legacy BET' in labels
