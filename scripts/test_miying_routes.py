import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('film_deploy',ROOT/'scripts/deploy-pachong.py')
deploy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class RouteTests(unittest.TestCase):
    def test_replaces_only_owned_routes_and_retains_gate(self):
        prefix='server {\n    auth_request /_chemex_auth;\n    # BEGIN ChemEx Owner Auth\n    location ^~ /auth/ { auth_request off; }\n    # END ChemEx Owner Auth\n'
        old='    # BEGIN ChemEx Pachong\n    location ^~ /pachong/ { proxy_pass http://127.0.0.1:4198; }\n    # END ChemEx Pachong\n\n'
        suffix='    # BEGIN ChemEx EPUB Reader\n    location / { proxy_pass http://127.0.0.1:4180; }\n}'
        result=deploy.update_nginx(prefix+old+suffix)
        self.assertTrue(result.startswith(prefix));self.assertTrue(result.endswith(suffix))
        self.assertIn('location ^~ /miying/',result)
        self.assertIn('proxy_pass http://127.0.0.1:4198/pachong/;',result)
        self.assertIn('rewrite ^/pachong/(.*)$ /miying/$1 permanent;',result)
        self.assertEqual(deploy.update_nginx(result),result)

    def test_unmanaged_new_route_rejected(self):
        with self.assertRaises(RuntimeError): deploy.update_nginx('location /miying/ {}')

    def test_home_canonical_link_and_relative_film_resources(self):
        home=(ROOT/'tools/home/index.html').read_text(encoding='utf-8')
        self.assertIn('href="/miying/"',home)
        self.assertNotIn('href="/pachong/"',home)
        app=(ROOT/'tools/pachong/app.js').read_text(encoding='utf-8')
        self.assertIn("fetch('./api/'",app)


if __name__=='__main__': unittest.main()
