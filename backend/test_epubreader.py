"""Reader routes are isolated from scientific workflows and canonicalize assets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as module


class ReaderRoutesTest(unittest.TestCase):
    def test_canonical_path_assets_and_existing_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('ChemEx home', encoding='utf-8')
            reader = root / 'epubreader'
            reader.mkdir()
            (reader / 'index.html').write_text('EPUB Reader', encoding='utf-8')
            (reader / 'reader.js').write_text('// local reader', encoding='utf-8')
            with patch.object(module, 'DIST_DIR', root):
                client = module.app.test_client()
                response = client.get('/epubreader')
                self.assertEqual(response.status_code, 308)
                self.assertEqual(response.headers['Location'], '/epubreader/')
                for path, expected in [('/', b'ChemEx home'), ('/epubreader/', b'EPUB Reader'), ('/epubreader/reader.js', b'// local reader')]:
                    with client.get(path) as result:
                        self.assertEqual(result.status_code, 200)
                        self.assertEqual(result.data, expected)
                with client.get('/epubreader/missing.js') as result:
                    self.assertEqual(result.status_code, 404)


if __name__ == '__main__':
    unittest.main()
