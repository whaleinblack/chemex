import io
import json
import unittest
from unittest.mock import patch
import server


class AdapterTests(unittest.TestCase):
    def test_safe_metadata_and_deduplication(self):
        root = server.Document('''<div class="media"><a href="/play/1234"><img alt="Test &amp; Film" data-src="https://images.example/a.jpg"></a><h5><a class="title-text" href="/play/1234">Test Film 2020</a></h5><span>Cast</span></div><a href="javascript:bad()">bad</a>''').root
        items = server.movie_items(root)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['title'],'Test & Film')
        self.assertIn('Cast',items[0]['summary'])
        self.assertEqual(server.remote_url('javascript:alert(1)'), '')
        self.assertEqual(server.remote_url('https://user:pass@example.com/a'), '')

    def test_episode_parsing_never_evaluates_script(self):
        html = '<h1 id="video_title">Original fixture</h1><input id="e_token" value="abc"><input id="mtype" value="2">'
        payload = {'data':{'list':[{'resData':json.dumps([{'url':'1$https://cdn.example/1.m3u8#2$javascript:alert(1)#3$https://cdn.example/3.m3u8?a=1'}])},{'resData':'doBadThings()'}]}}
        with patch.object(server,'fetch',side_effect=[html,json.dumps(payload)]):
            data=server.detail('1234')
        self.assertEqual(len(data['lines']),1)
        self.assertEqual([e['name'] for e in data['lines'][0]['episodes']],['1','3'])

    def test_reject_arbitrary_target_and_traversal(self):
        for path in ['https://localhost/','//localhost/','/../server.py','/search?x=1#bad']:
            with self.assertRaises(ValueError):
                server.api('list',{'path':[path]})
        state=[]
        result=server.app({'PATH_INFO':'/pachong/../server.py','REQUEST_METHOD':'GET'},lambda s,h:state.append(s))
        self.assertEqual(state[0],'404 Not Found')
        self.assertNotIn(b'import json',b''.join(result))

    def test_upstream_failure_is_explicit(self):
        state=[]
        with patch.object(server,'fetch',side_effect=TimeoutError()):
            body=b''.join(server.app({'PATH_INFO':'/pachong/api/home','REQUEST_METHOD':'GET'},lambda s,h:state.append(s)))
        self.assertEqual(state[0],'502 Bad Gateway')
        self.assertIn('error',json.loads(body))

    def test_cache_bounded_and_reused(self):
        server.CACHE.clear()
        class Response(io.BytesIO):
            pass
        with patch.object(server,'build_opener') as opener:
            opener.return_value.open.return_value=Response(b'<p>ok</p>')
            self.assertEqual(server.fetch('/fixture'),'<p>ok</p>')
            self.assertEqual(server.fetch('/fixture'),'<p>ok</p>')
            self.assertEqual(opener.return_value.open.call_count,1)

    def test_rate_limit_does_not_fetch_upstream(self):
        import time
        server.VISITS['fixture']=(time.monotonic(),80)
        state=[]
        with patch.object(server,'fetch') as upstream:
            server.app({'PATH_INFO':'/pachong/api/home','REQUEST_METHOD':'GET','REMOTE_ADDR':'fixture'},lambda s,h:state.append(s))
        self.assertEqual(state[0],'429 Too Many Requests')
        upstream.assert_not_called()


if __name__=='__main__':
    unittest.main()
