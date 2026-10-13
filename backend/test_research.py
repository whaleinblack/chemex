import copy
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PIL import Image

from backend import routes_research as routes
from backend import services_research as service


class EvidenceTests(unittest.TestCase):
    def report(self):
        url = 'https://publisher.example/paper'
        return {'papers': [{'title': 'Paper', 'url': url, 'doi': None, 'year': 2025,
                            'journal': 'Journal', 'match': 'exact', 'matchReason': 'Both monomers',
                            'access': 'SI', 'fields': {k: {'value': 'Reported value',
                                'sourceUrls': [url], 'evidence': 'SI section 2'} for k in service.FIELDS}}],
                'summary': 'Summary', 'queries': [], 'limitations': []}, [{'url': url, 'title': 'Paper'}]

    def test_unsupported_condition_removed_and_exact_match_downgraded(self):
        result, sources = self.report()
        result['papers'][0]['fields']['temperature']['sourceUrls'] = ['https://invented.example']
        result['papers'][0]['fields']['monomerCombination']['evidence'] = None
        final = service.normalize_report(result, sources, ['actual query'])
        self.assertIsNone(final['papers'][0]['fields']['temperature']['value'])
        self.assertEqual(final['papers'][0]['match'], 'candidate')
        self.assertEqual(final['conclusion'], 'not_found')

    def test_grounded_exact_match_and_independent_structure_fields(self):
        result, sources = self.report()
        result['papers'][0]['fields']['rietveld']['value'] = None
        final = service.normalize_report(result, sources, [])
        self.assertEqual(final['conclusion'], 'reported')
        self.assertIsNone(final['papers'][0]['fields']['rietveld']['value'])
        self.assertIsNotNone(final['papers'][0]['fields']['pawley']['value'])

    def test_unconsulted_paper_discarded(self):
        result, _ = self.report()
        final = service.normalize_report(result, [{'url': 'https://other.example'}], [])
        self.assertEqual(final['papers'], [])
        self.assertNotEqual(final['conclusion'], 'reported')

    @patch.dict(os.environ, {}, clear=True)
    def test_public_search_failure_is_not_a_negative_result(self):
        with patch.object(service, 'fetch_json', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                service.public_search([{'name': 'A'}, {'name': 'B'}], lambda *_: None)

    def test_metadata_search_never_claims_exact_match(self):
        data = {'message': {'items': [{'title': ['Covalent organic frameworks'], 'DOI': '10.1/test'}]}}
        with patch.object(service, 'fetch_json', return_value=data):
            result = service.public_search([{'name': 'A'}, {'name': 'B'}], lambda *_: None)
        self.assertEqual(result['conclusion'], 'inconclusive')
        self.assertEqual(result['papers'][0]['match'], 'candidate')
        self.assertTrue(all(e['value'] is None for e in result['papers'][0]['fields'].values()))

    def test_ai_requires_completed_search_with_sources(self):
        response = {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]}]}
        with patch.object(service, 'fetch_json', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'completed web search'):
                service.ai_response([], service.REPORT_SCHEMA, 'test')

    def test_image_format_size_and_content_validated(self):
        image = io.BytesIO()
        Image.new('RGB', (20, 20), 'white').save(image, format='PNG')
        self.assertTrue(service.image_data(image.getvalue()).startswith('data:image/png;base64,'))
        for raw in (b'<svg></svg>', b'x' * (service.MAX_IMAGE_BYTES + 1)):
            with self.assertRaises(ValueError):
                service.image_data(raw)

    def test_cas_not_found_among_synonyms_is_unresolved(self):
        responses = [{'PropertyTable': {'Properties': [{'CID': 1, 'Title': 'Wrong compound'}]}},
                     {'InformationList': {'Information': [{'Synonym': ['other CAS']} ]}}]
        with patch.object(service, 'fetch_json', side_effect=responses):
            result = service.pubchem_identity('108-45-2')
        self.assertEqual(result['confidence'], 'unresolved')


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs = {}
        self.app = Flask(__name__)
        routes.STARTS.clear()

        def create(workflow, filename):
            job = {'jobId': str(len(self.jobs)), '_jobDir': self.tmp.name,
                   'status': 'queued', 'workflow': workflow, 'progress': 0}
            self.jobs[job['jobId']] = job
            return job

        def advance(id_, stage, progress):
            self.jobs[id_].update(stage=stage, progress=progress)

        def finish(id_, **kwargs):
            self.jobs[id_].update(**kwargs)

        def fail(id_, error):
            self.jobs[id_].update(status='failed', error=error)

        routes.register_research_routes(self.app, create, advance, finish, fail)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_confirmation_and_input_validation(self):
        self.assertEqual(self.client.post('/api/research/search', json={}).status_code, 400)
        self.assertEqual(self.client.post('/api/research/identify', data={'monomers': 'null'}).status_code, 400)
        self.assertEqual(self.client.post('/api/research/identify', data={'monomers': '[{},{}]'}).status_code, 400)
        body = {'confirmed': True, 'monomers': [{'name': 'A'}, {'name': 'B', 'aliases': 'invalid'}]}
        self.assertEqual(self.client.post('/api/research/search', json=body).status_code, 400)

    @patch.dict(os.environ, {}, clear=True)
    def test_image_without_provider_is_explicitly_rejected(self):
        image = io.BytesIO()
        Image.new('RGB', (20, 20)).save(image, format='PNG')
        image.seek(0)
        response = self.client.post('/api/research/identify', data={'monomers': '[{"text":"A"},{"text":"B"}]',
            'image0': (image, 'image.png')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Image recognition', response.json['error'])

    def test_job_completes_and_persists_report(self):
        result = {'papers': [], 'conclusion': 'inconclusive'}
        with patch.object(routes, 'research', return_value=result):
            response = self.client.post('/api/research/search', json={'confirmed': True,
                'monomers': [{'name': 'A'}, {'name': 'B'}]})
            self.assertEqual(response.status_code, 202)
            id_ = response.json['jobId']
            for _ in range(100):
                if self.jobs[id_]['status'] != 'queued':
                    break
                time.sleep(.01)
            self.assertEqual(self.jobs[id_]['status'], 'completed')
        self.assertEqual(json.loads((Path(self.tmp.name) / 'research.json').read_text()), result)
        self.assertNotIn('_jobDir', response.json)


if __name__ == '__main__':
    unittest.main()
