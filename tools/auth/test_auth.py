import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import tempfile
import time
import unittest
from urllib.parse import urlencode
import server


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.salt=secrets.token_hex(16)
        cls.account={'username':'fixture-owner','salt':cls.salt,'hash':server.password_hash('fixture-only-password',cls.salt),'source':'survival-mx'}

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root=Path(self.temp.name)
        (self.root/'account.json').write_text(json.dumps(self.account))
        self.auth=server.Auth(self.root)

    def tearDown(self): self.temp.cleanup()

    def call(self,path,method='GET',data=None,cookies='',origin=server.ORIGIN,ip='fixture'):
        raw=urlencode(data or {}).encode()
        state={}
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'HTTP_COOKIE':cookies,'HTTP_ORIGIN':origin,'REMOTE_ADDR':ip}
        def start(status,headers): state.update(status=status,headers=headers)
        state['body']=b''.join(self.auth(env,start)).decode()
        return state

    def login(self,password='fixture-only-password'):
        page=self.call('/auth/login')
        csrf=re.search('name="csrf" value="([^"]+)"',page['body'])[1]
        return self.call('/auth/login','POST',{'username':'fixture-owner','password':password,'csrf':csrf,'next':'/research/'},f'{server.PREAUTH}={csrf}')

    def session_cookie(self):
        result=self.login()
        return next(v.split(';')[0] for k,v in result['headers'] if k=='Set-Cookie' and v.startswith(server.COOKIE+'='))

    def test_unauthenticated_and_tampered_cookies_rejected(self):
        self.assertEqual(self.call('/auth/check')['status'],'401 Unauthorized')
        for token in ['bad','x'*43,secrets.token_urlsafe(32)]:
            self.assertEqual(self.call('/auth/check',cookies=server.COOKIE+'='+token)['status'],'401 Unauthorized')

    def test_login_persistent_secure_cookie_and_no_plaintext_storage(self):
        result=self.login()
        self.assertEqual(result['status'],'303 See Other')
        self.assertIn(('Location','/research/'),result['headers'])
        auth_cookie=next(v for k,v in result['headers'] if k=='Set-Cookie' and v.startswith(server.COOKIE+'='))
        for flag in ['Max-Age=2592000','Secure','HttpOnly','SameSite=Lax','Path=/']: self.assertIn(flag,auth_cookie)
        token=auth_cookie.split(';')[0]
        self.assertEqual(self.call('/auth/check',cookies=token)['status'],'204 No Content')
        persisted=(self.root/'sessions.sqlite').read_bytes()
        self.assertNotIn(token.split('=')[1].encode(),persisted)
        self.assertNotIn(b'fixture-only-password',persisted)

    def test_wrong_password_does_not_issue_session(self):
        result=self.login('wrong-password')
        self.assertEqual(result['status'],'400 Bad Request')
        self.assertFalse(any(k=='Set-Cookie' and server.COOKIE in v for k,v in result['headers']))

    def test_csrf_and_cross_origin_rejected(self):
        for data,origin in [({},server.ORIGIN),({'csrf':'x'*43},server.ORIGIN),({},'https://other.example')]:
            self.assertEqual(self.call('/auth/login','POST',data,origin=origin)['status'],'400 Bad Request')

    def test_login_throttling(self):
        for i in range(8): self.assertTrue(self.auth.reserve_attempt('throttle'))
        self.assertFalse(self.auth.reserve_attempt('throttle'))

    def test_remember_survives_service_restart_and_expires(self):
        cookie=self.session_cookie()
        self.auth=server.Auth(self.root)
        self.assertEqual(self.call('/auth/check',cookies=cookie)['status'],'204 No Content')
        with self.auth.db() as db: db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
        self.assertEqual(self.call('/auth/check',cookies=cookie)['status'],'401 Unauthorized')

    def test_logout_csrf_and_session_revocation(self):
        cookie=self.session_cookie()
        self.assertEqual(self.call('/auth/logout','POST',{},cookie)['status'],'400 Bad Request')
        account=self.call('/auth/account',cookies=cookie)
        csrf=re.search('name="csrf" value="([^"]+)"',account['body'])[1]
        self.assertEqual(self.call('/auth/logout','POST',{'csrf':csrf},cookie)['status'],'303 See Other')
        self.assertEqual(self.call('/auth/check',cookies=cookie)['status'],'401 Unauthorized')

    def test_logout_all_revokes_other_devices(self):
        first=self.session_cookie();second=self.session_cookie()
        csrf=self.auth.csrf(first.split('=')[1])
        self.call('/auth/logout-all','POST',{'csrf':csrf},first)
        self.assertEqual(self.call('/auth/check',cookies=second)['status'],'401 Unauthorized')

    def test_survival_bridge_requires_auth(self):
        self.assertEqual(self.call('/auth/survival-session.js')['status'],'401 Unauthorized')
        response=self.call('/auth/survival-session.js',cookies=self.session_cookie())
        self.assertEqual(response['status'],'200 OK')
        self.assertIn('mxsg-user',response['body'])
        self.assertNotIn('fixture-only-password',response['body'])

    def test_redirects_are_local_and_account_change_invalidates_session(self):
        for value in ['https://evil.example','//evil.example','/%2fexample','/\\evil','/\r\nBad: x','/auth/login']:
            self.assertEqual(server.local_next(value),'/')
        self.assertEqual(server.local_next('/pachong/?q=a'),'/pachong/?q=a')
        cookie=self.session_cookie()
        changed={**self.account,'hash':'0'*128}
        (self.root/'account.json').write_text(json.dumps(changed))
        self.assertEqual(self.call('/auth/check',cookies=cookie)['status'],'401 Unauthorized')


if __name__=='__main__': unittest.main()
