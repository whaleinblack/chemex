"""HTTP attachment checks; SESAMI is unrelated to this route and is isolated."""
import importlib
import io
import sys
import tempfile
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake = ModuleType('backend.services_sesami')
        fake.get_sesami_status = lambda: (False, 'unused')
        fake.parse_upload = lambda *args: None
        fake.run_workflow = lambda *args: None
        with patch.dict(sys.modules, {'backend.services_sesami': fake}):
            cls.web = importlib.import_module('backend.app')

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.job_id = 'a' * 32
        folder = self.root / self.job_id
        folder.mkdir()
        self.data = '@ test POAV_A^3: 42\nPONAV_A^3: 0\n'.encode()
        (folder / 'volpo.out').write_bytes(self.data)
        self.client = self.web.app.test_client()
        context = patch.object(self.web, 'ARTIFACTS_DIR', self.root)
        context.start()
        self.addCleanup(context.stop)

    def test_exact_raw_bytes_and_http_attachment_after_restart(self):
        with patch.dict(self.web.JOBS, {}, clear=True):
            response = self.client.get(f'/api/zeopp/export/{self.job_id}/volpo.txt')
            self.addCleanup(response.close)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.data)
            self.assertIn('attachment;', response.headers['Content-Disposition'])
            self.assertIn('chemex-volpo.txt', response.headers['Content-Disposition'])
            self.assertEqual(response.mimetype, 'text/plain')
            self.assertEqual(response.headers['Content-Type'], 'text/plain; charset=utf-8')

    def test_unknown_job_mode_and_missing_file_do_not_download_other_files(self):
        for path in ('../volpo', 'unknown/volpo', f'{self.job_id}/secrets', f'{self.job_id}/psd'):
            with self.subTest(path=path):
                response = self.client.get(f'/api/zeopp/export/{path}.txt')
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 404)

    def test_candidate_attachment_and_query_traversal_guard(self):
        folder = self.root / self.job_id / 'ordered-models' / 'model-1'
        folder.mkdir(parents=True)
        (folder / 'candidate.cif').write_bytes(b'data_synthetic\n')
        (folder / 'volpo.out').write_bytes(self.data)
        response = self.client.get(f'/api/zeopp/export/{self.job_id}/volpo.txt?model=model-1')
        self.addCleanup(response.close)
        self.assertEqual(response.data, self.data)
        self.assertIn('chemex-volpo-model-1.txt', response.headers['Content-Disposition'])
        cif = self.client.get(f'/api/artifacts/{self.job_id}/ordered-models/model-1/candidate.cif?download=1')
        self.addCleanup(cif.close)
        self.assertEqual(cif.data, b'data_synthetic\n')
        self.assertIn('ordered-model-1.cif', cif.headers['Content-Disposition'])
        for model in ('../model-1', 'model-5', 'model-1/../../'):
            response = self.client.get(f'/api/zeopp/export/{self.job_id}/volpo.txt', query_string={'model': model})
            self.addCleanup(response.close)
            self.assertEqual(response.status_code, 404)

    def test_psd_bin_count_preserves_all_bins_and_separates_models(self):
        raw = b'Pore size distribution histogram\r\nBin size (A): 0.1\r\n\r\nBin Count Cumulative_dist Derivative_dist\r\n0 0 1 0\r\n0.1 2 1 .2\r\n0.2 0 0 0\r\n'
        for model in (None, 'model-1', 'model-2'):
            folder = self.root / self.job_id
            if model:
                folder = folder / 'ordered-models' / model
                folder.mkdir(parents=True)
            data = raw.replace(b'0.1 2', b'0.1 7') if model == 'model-2' else raw
            (folder / 'psd.out').write_bytes(data)
            query = {'format': 'bin-count', **({'model': model} if model else {})}
            with patch.dict(self.web.JOBS, {}, clear=True):
                response = self.client.get(f'/api/zeopp/export/{self.job_id}/psd.txt', query_string=query)
            self.addCleanup(response.close)
            expected = b'Bin\tCount\n0\t0\n0.1\t7\n0.2\t0\n' if model == 'model-2' else b'Bin\tCount\n0\t0\n0.1\t2\n0.2\t0\n'
            self.assertEqual(response.data, expected)
            self.assertIn(f'chemex-psd{"-" + model if model else ""}-bin-count.txt', response.headers['Content-Disposition'])
            original = self.client.get(f'/api/zeopp/export/{self.job_id}/psd.txt', query_string={'model': model} if model else {})
            self.addCleanup(original.close)
            self.assertEqual(original.data, data)

    def test_psd_bin_count_rejects_missing_malformed_and_wrong_formats(self):
        url = f'/api/zeopp/export/{self.job_id}/psd.txt?format=bin-count'
        self.assertEqual(self.client.get(url).status_code, 404)
        for text in ('missing histogram', 'Bin Count Cumulative_dist Derivative_dist\n', 'Bin Count Cumulative_dist Derivative_dist\n0 NaN 1 0\n', 'Bin Count Cumulative_dist Derivative_dist\n0 1\n'):
            (self.root / self.job_id / 'psd.out').write_text(text)
            self.assertEqual(self.client.get(url).status_code, 422)
        self.assertEqual(self.client.get(f'/api/zeopp/export/{self.job_id}/volpo.txt?format=bin-count').status_code, 400)
        self.assertEqual(self.client.get(f'/api/zeopp/export/{self.job_id}/psd.txt?format=unknown').status_code, 400)

    def test_cif_inspection_detects_disorder_without_engine_or_job(self):
        from backend.test_disorder import ethane
        ordered = "data_test\n_cell_length_a 20\n_cell_length_b 20\n_cell_length_c 20\n_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n_space_group_name_H-M_alt 'P 1'\nloop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_occupancy\nC1 C .5 .5 .5 1\n"
        before = set(self.web.JOBS)
        with patch.object(self.web.threading, 'Thread', side_effect=AssertionError('Inspection must not launch a worker')):
            for text, expected in ((ethane(), True), (ordered, False)):
                response = self.client.post('/api/zeopp/inspect-cif', data={'file': (io.BytesIO(text.encode()), 'test.cif')})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {'disordered': expected})
        self.assertEqual(set(self.web.JOBS), before)
        self.assertEqual(self.client.post('/api/zeopp/inspect-cif').status_code, 400)
        response = self.client.post('/api/zeopp/inspect-cif', data={'file': (io.BytesIO(b'invalid'), 'test.cif')})
        self.assertEqual(response.status_code, 400)

    def test_direct_original_cif_is_restricted_to_psd(self):
        with patch.object(self.web, 'detect_zeopp_binary', return_value=(Path('engine'), 'ready')):
            for mode, filename in (('volpo', 'test.cif'), ('res', 'test.cif'), ('psd', 'test.cssr')):
                response = self.client.post(f'/api/zeopp/{mode}', data={'disorderStrategy': 'direct_cif', 'file': (io.BytesIO(b'input'), filename)})
                self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
