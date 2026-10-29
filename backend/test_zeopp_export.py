"""HTTP attachment checks; SESAMI is unrelated to this route and is isolated."""
import importlib
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
        (folder / 'volpo.out').write_bytes(self.data)
        response = self.client.get(f'/api/zeopp/export/{self.job_id}/volpo.txt?model=model-1')
        self.addCleanup(response.close)
        self.assertEqual(response.data, self.data)
        self.assertIn('chemex-volpo-model-1.txt', response.headers['Content-Disposition'])
        for model in ('../model-1', 'model-5', 'model-1/../../'):
            response = self.client.get(f'/api/zeopp/export/{self.job_id}/volpo.txt', query_string={'model': model})
            self.addCleanup(response.close)
            self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
