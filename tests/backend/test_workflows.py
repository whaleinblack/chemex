import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend import app as api
from backend import services_zeopp as z

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / 'vendor/zeopp-lsmo/tests'


@pytest.mark.parametrize('mode,flag,args', [
    ('psd', '-psd', ['1.2', '1.5', '2000']),
    ('res', '-res', []), ('chan', '-chan', ['1.5']),
    ('sa', '-sa', ['1.2', '1.5', '2000']),
    ('vol', '-vol', ['1.2', '1.5', '2000']),
    ('volpo', '-volpo', ['1.2', '1.5', '2000']),
])
def test_command_contract(tmp_path, mode, flag, args):
    source = tmp_path / 'sample.cif'
    command, output, extended = z.build_command(Path('network'), mode, source, {
        'chanRadius': 1.2, 'probeRadius': 1.5, 'numSamples': 2000,
    })
    assert command == ['network', '-ha', flag, *args, str(output), str(source)]
    assert not extended


def test_extended_res(tmp_path):
    command, _, extended = z.build_command(Path('network'), 'res', tmp_path / 'sample.cif', {'extended': 'true'})
    assert command[2] == '-resex'
    assert extended
    result = z.parse_output('res', 'sample 5 4 3 1 2 3 4 5 6', True)
    assert len(result['metrics']) == 9
    assert result['metrics'][-1]['value'] == 6


@pytest.mark.parametrize('mode,filename,key,value,unit', [
    ('res', 'EDI_ref.res', 'largest_included_sphere', 4.88186, 'A'),
    ('chan', 'EDI_ref.chan', 'channel_count', 1, None),
    ('sa', 'EDI_ref.sa', 'asa_m2_g', 1218.21, 'm^2/g'),
    ('vol', 'EDI_ref.vol', 'vol_cm3_g', 0.0454022, 'cm^3/g'),
])
def test_vendored_reference_parsing(mode, filename, key, value, unit):
    parsed = z.parse_output(mode, (REFERENCES / filename).read_text(), False)
    metric = next(item for item in parsed['metrics'] if item['key'] == key)
    assert metric['value'] == pytest.approx(value)
    assert metric['unit'] == unit
    if mode == 'chan':
        assert parsed['channels']['dimensionalities'] == [1]
        assert parsed['channels']['largestFreeSpheres'] == [3.03748]


def test_psd_reference():
    parsed = z.parse_output('psd', (REFERENCES / 'EDI_ref.psd_histo').read_text(), False)
    assert parsed['rows']
    assert parsed['rows'][0]['diameter'] >= 0


def test_volpo_parser():
    # Synthetic contract fixture: no VOLPO reference file is vendored.
    parsed = z.parse_output('volpo', 'Unitcell_volume: 307.484 Density: 1.62239 POAV_A^3: 22.6493 POAV_Volume_fraction: 0.07366 POAV_cm^3/g: 0.0454022 PONAV_A^3: 4 PONAV_Volume_fraction: 0.01 PONAV_cm^3/g: 0.02', False)
    metrics = {item['key']: item for item in parsed['metrics']}
    assert metrics['volpo_a3']['value'] == 22.6493
    assert metrics['nvolpo_a3']['value'] == 4
    assert metrics['volpo_cm3_g']['unit'] == 'cm^3/g'


@pytest.mark.parametrize('usable_output', [True, False])
def test_nonzero_exit_requires_usable_output(tmp_path, monkeypatch, usable_output):
    monkeypatch.setattr(z, 'detect_zeopp_binary', lambda: (Path('network'), 'ready'))
    if usable_output:
        (tmp_path / 'res.out').write_text('sample 5 4 3')
    process = MagicMock()
    process.stdout = io.StringIO('Reading input file: sample.cif\n')
    process.stderr = io.StringIO('abort\n')
    process.wait.return_value = -6
    with patch.object(z.subprocess, 'Popen', return_value=process):
        if usable_output:
            result = z.run_workflow('test', tmp_path, tmp_path / 'sample.cif', 'res', {}, lambda *args: None, lambda: 0)
            assert result['warning']
            assert result['returnCode'] == -6
            assert result['rawOutput'] == 'sample 5 4 3'
            assert result['metrics'][0]['value'] == 5
        else:
            with pytest.raises(RuntimeError, match='execution failed'):
                z.run_workflow('test', tmp_path, tmp_path / 'sample.cif', 'res', {}, lambda *args: None, lambda: 0)


class ImmediateThread:
    def __init__(self, target, args, **kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'ARTIFACTS_DIR', tmp_path)
    monkeypatch.setattr(api.threading, 'Thread', ImmediateThread)
    api.JOBS.clear()
    yield api.app.test_client()
    api.JOBS.clear()


@pytest.mark.parametrize('mode', ['psd', 'res', 'chan', 'sa', 'vol', 'volpo'])
def test_zeopp_api_dispatch_and_poll(client, monkeypatch, mode):
    monkeypatch.setattr(api, 'detect_zeopp_binary', lambda: (Path('network'), 'ready'))
    with patch.object(api, 'run_zeopp_workflow', return_value={'mode': mode, 'warning': 'usable output with non-zero exit'}) as run:
        response = client.post(f'/api/zeopp/{mode}', data={
            'file': (io.BytesIO(b'structure'), 'sample.cif'),
            'probeRadius': '1.5', 'chanRadius': '1.2', 'numSamples': '2000', 'extended': 'true',
        })
        assert response.status_code == 202
        job = client.get(f"/api/jobs/{response.json['jobId']}").json
        assert job['status'] == 'completed'
        assert job['result']['mode'] == mode
        assert job['warning'] == 'usable output with non-zero exit'
        assert run.call_args.args[3] == mode
        assert run.call_args.args[4]['probeRadius'] == '1.5'


@pytest.mark.parametrize('mode', ['bet', 'bet-esw', 'betml', 'compare'])
def test_sesami_api_dispatch(client, monkeypatch, mode):
    monkeypatch.setattr(api, 'parse_sesami_upload', lambda *args: 'parsed')
    with patch.object(api, 'run_sesami_workflow', return_value={'mode': mode}) as run:
        response = client.post(f'/api/sesami/{mode}', data={
            'file': (io.BytesIO(b'isotherm'), 'sample.csv'), 'gas': 'Argon', 'version': '2.9', 'r2Cutoff': '0.995',
        })
        assert response.status_code == 202
        job = client.get(f"/api/jobs/{response.json['jobId']}").json
        assert job['status'] == 'completed'
        assert job['result']['mode'] == mode
        assert run.call_args.args[5] == mode
        assert run.call_args.args[6]['r2Cutoff'] == '0.995'


@pytest.mark.parametrize('mode', ['bet-esw', 'betml'])
def test_modern_only_modes_reject_legacy(client, mode):
    response = client.post(f'/api/sesami/{mode}', data={'version': '1.0'})
    assert response.status_code == 400
    assert 'only available' in response.json['error']


def test_worker_failure_is_pollable(client, monkeypatch):
    monkeypatch.setattr(api, 'parse_sesami_upload', lambda *args: 'parsed')
    with patch.object(api, 'run_sesami_workflow', side_effect=ValueError('ESW minimum unavailable')):
        response = client.post('/api/sesami/bet-esw', data={'file': (io.BytesIO(b'x'), 'x.csv')})
    job = client.get(f"/api/jobs/{response.json['jobId']}").json
    assert job['status'] == 'failed'
    assert job['error'] == 'ESW minimum unavailable'


def test_zeopp_unavailable(client, monkeypatch):
    monkeypatch.setattr(api, 'detect_zeopp_binary', lambda: (None, 'Runtime unavailable'))
    assert client.post('/api/zeopp/volpo').status_code == 503
