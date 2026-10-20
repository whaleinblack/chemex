import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('theme_deploy',Path(__file__).with_name('deploy-theme.py'))
theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
SURVIVAL='''    location ^~ /survival/ {
        # ChemEx authenticated MX bridge
        sub_filter_once on;
        sub_filter '</head>' '<script src="/auth/survival-session.js"></script></head>';
        alias /srv/mxsg/survival/current/;
    }
'''
RESEARCH='''    location ^~ /research/ {
        alias /srv/chemex/home/current/research/;
    }
'''
class ThemeTests(unittest.TestCase):
    def fixture(self):
        return '''server { server_name unrelated.example; }
server {
    auth_request /_chemex_auth;
    # BEGIN ChemEx Personal Home
    location = / {
        root /srv/chemex/home/current;
    }
    # END ChemEx Personal Home
    location ^~ /miying/ {
        proxy_pass http://127.0.0.1:4198/pachong/;
    }
    location ^~ /epubreader/ {
        alias /srv/chemex/epubreader/current/;
    }
    location ^~ /auth/ {
        auth_request off;
        proxy_pass http://127.0.0.1:4197;
    }
'''+RESEARCH+SURVIVAL+'}\n'
    def test_scoped_filters_keep_cof_survival_and_authentication(self):
        result=theme.update_nginx(self.fixture())
        self.assertEqual(result,theme.update_nginx(result))
        self.assertIn('server { server_name unrelated.example; }',result)
        self.assertIn('auth_request /_chemex_auth;',result)
        self.assertIn(RESEARCH,result);self.assertIn(SURVIVAL,result)
        self.assertEqual(result.count('data-chemex-page="$uri"'),4)
        self.assertEqual(result.count('/auth/survival-session.js'),1)
        self.assertEqual(result.count('location = /site-theme.css'),1)
        self.assertEqual(result.count('auth_request off;'),2)
    def test_missing_gate_or_unmanaged_route_rejected(self):
        with self.assertRaises(RuntimeError):theme.update_nginx(self.fixture().replace('auth_request /_chemex_auth;',''))
        with self.assertRaises(RuntimeError):theme.update_nginx(self.fixture()+'location = /site-theme.css {}')
    def test_unexpected_existing_filter_rejected(self):
        with self.assertRaises(RuntimeError):theme.update_nginx(self.fixture().replace('root /srv/chemex/home/current;',"sub_filter 'x' 'y';"))
if __name__=='__main__':unittest.main()
