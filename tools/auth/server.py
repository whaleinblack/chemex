"""Single-owner server-side sessions using the selected existing Survival credential."""
import hashlib
from contextlib import contextmanager
import hmac
from html import escape
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import parse_qs, unquote

COOKIE='__Host-chemex_session'
PREAUTH='__Host-chemex_login'
MONTH=30*24*3600
ORIGIN='https://chemex.space'
STYLE='''*{box-sizing:border-box}body{margin:0;background:#f7f8f2;color:#29382d;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px}main{width:100%;max-width:370px}h1{font-size:28px;letter-spacing:-1px;margin:0 0 6px}p{color:#788074;font-size:12px}form{margin-top:25px}label{display:block;font-size:12px;margin:17px 0 6px}input{display:block;width:100%;padding:11px 12px;border:1px solid #dce1d4;border-radius:5px;font:inherit;background:#fffefa;color:inherit}input:focus{outline:2px solid #9baf88;outline-offset:1px}button{width:100%;border:0;border-radius:5px;background:#587445;color:white;font:inherit;padding:11px;margin-top:23px;cursor:pointer}button:hover{background:#465e36}.muted{font-size:11px;color:#788074;margin-top:15px}.error{padding:10px 12px;color:#974a35;background:#f3e6de;border-radius:5px}.secondary{background:transparent;color:#587445;border:1px solid #cdd7c3}a{color:#587445;text-underline-offset:4px}.account-info{padding:15px;border:1px solid #dce1d4;border-radius:6px;margin-top:22px}.account-info p{margin:4px 0}footer{margin-top:30px;border-top:1px solid #dce1d4;padding-top:15px;font-size:10px;color:#788074}'''


def password_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=32768,r=8,p=1,maxmem=64*1024*1024).hex()


def local_next(value):
    value=value or '/'
    decoded=unquote(value)
    if not decoded.startswith('/') or decoded.startswith('//') or '\\' in decoded or any(ord(c)<32 for c in decoded) or decoded.startswith('/auth'):
        return '/'
    return value


def cookie(name,value,age):
    return ('Set-Cookie',f'{name}={value}; Path=/; Max-Age={age}; Secure; HttpOnly; SameSite=Lax')


def page(title,inner):
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · ChemEx</title><style>{STYLE}</style></head><body><main>{inner}<footer>ChemEx · 私人空间</footer></main></body></html>'


class Auth:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.db_path=self.directory/'sessions.sqlite'
        with self.db() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires REAL NOT NULL, credential TEXT NOT NULL); CREATE TABLE IF NOT EXISTS attempts (ip TEXT NOT NULL, at REAL NOT NULL); CREATE INDEX IF NOT EXISTS attempts_time ON attempts(at);')

    @contextmanager
    def db(self):
        connection=sqlite3.connect(self.db_path,timeout=10)
        try:
            with connection: yield connection
        finally: connection.close()

    def account(self):
        return json.loads((self.directory/'account.json').read_text())

    @staticmethod
    def credential_tag(account):
        return hashlib.sha256((account['username']+account['hash']).encode()).hexdigest()

    def session(self,environ):
        cookies=SimpleCookie()
        try: cookies.load(environ.get('HTTP_COOKIE',''))
        except Exception: return None
        token=cookies.get(COOKIE)
        if not token or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token.value): return None
        digest=hashlib.sha256(token.value.encode()).hexdigest()
        with self.db() as db:
            row=db.execute('SELECT expires,credential FROM sessions WHERE token=?',(digest,)).fetchone()
        if not row or row[0]<time.time() or not hmac.compare_digest(row[1],self.credential_tag(self.account())): return None
        return token.value

    def create_session(self):
        token=secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),time.time()+MONTH,self.credential_tag(self.account())))
        return token

    @staticmethod
    def csrf(token):
        return hashlib.sha256(('csrf:'+token).encode()).hexdigest()

    def reserve_attempt(self,ip):
        digest=hashlib.sha256(ip.encode()).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE at<?',(time.time()-900,))
            total=db.execute('SELECT count(*) FROM attempts').fetchone()[0]
            own=db.execute('SELECT count(*) FROM attempts WHERE ip=?',(digest,)).fetchone()[0]
            if own>=8 or total>=40: return False
            db.execute('INSERT INTO attempts VALUES (?,?)',(digest,time.time()))
        return True

    @staticmethod
    def form(environ):
        length=int(environ.get('CONTENT_LENGTH') or 0)
        if length<0 or length>8192: raise ValueError('Request too large')
        if environ.get('HTTP_ORIGIN')!=ORIGIN: raise ValueError('Invalid origin')
        return {k:v[0] for k,v in parse_qs(environ['wsgi.input'].read(length).decode(),max_num_fields=8).items()}

    def login_page(self,next_path,nonce,error=''):
        return page('登录',f'''<h1>ChemEx</h1><p>使用 survival 的 MX 账号登录</p>{f'<p class="error" role="alert">{escape(error)}</p>' if error else ''}<form method="post" action="/auth/login"><input type="hidden" name="csrf" value="{escape(nonce)}"><input type="hidden" name="next" value="{escape(next_path)}"><label for="username">用户名</label><input id="username" name="username" autocomplete="username" maxlength="100" required autofocus><label for="password">密码</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="256" required><button type="submit">登录</button><p class="muted">此浏览器登录后保留 30 天。共用设备使用后请退出。</p></form>''')

    def __call__(self,environ,start):
        status='200 OK'
        headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin')]
        mime='text/html; charset=utf-8'
        body=''
        try:
            path=environ.get('PATH_INFO','')
            method=environ.get('REQUEST_METHOD','GET')
            token=self.session(environ)
            if path=='/auth/check':
                status='204 No Content' if token else '401 Unauthorized'
            elif path=='/auth/health':
                mime='application/json';body='{"status":"ok"}'
            elif path=='/auth/login' and method=='GET':
                next_path=local_next(parse_qs(environ.get('QUERY_STRING','')).get('next',['/'])[0])
                if token: status='303 See Other';headers.append(('Location',next_path))
                else:
                    nonce=secrets.token_urlsafe(32)
                    headers.append(cookie(PREAUTH,nonce,600))
                    body=self.login_page(next_path,nonce)
            elif path=='/auth/login' and method=='POST':
                data=self.form(environ)
                cookies=SimpleCookie();cookies.load(environ.get('HTTP_COOKIE',''))
                nonce=cookies.get(PREAUTH)
                if not nonce or not re.fullmatch('[A-Za-z0-9_-]{43}',nonce.value) or not hmac.compare_digest(data.get('csrf',''),nonce.value): raise ValueError('Invalid form token')
                next_path=local_next(data.get('next'))
                if not self.reserve_attempt(environ.get('HTTP_X_REAL_IP') or environ.get('REMOTE_ADDR','local')):
                    status='429 Too Many Requests';headers.append(('Retry-After','900'));body=self.login_page(next_path,nonce.value,'尝试次数较多，请 15 分钟后再试。')
                else:
                    account=self.account()
                    valid=hmac.compare_digest(password_hash(data.get('password',''),account['salt']),account['hash'])
                    valid=hmac.compare_digest(data.get('username','').encode(),account['username'].encode()) and valid
                    if valid:
                        with self.db() as db: db.execute('DELETE FROM attempts WHERE ip=?',(hashlib.sha256((environ.get('HTTP_X_REAL_IP') or environ.get('REMOTE_ADDR','local')).encode()).hexdigest(),))
                        headers.extend([cookie(COOKIE,self.create_session(),MONTH),cookie(PREAUTH,'',0),('Location',next_path)])
                        status='303 See Other'
                    else:
                        status='400 Bad Request';body=self.login_page(next_path,nonce.value,'用户名或密码不正确。')
            elif path=='/auth/survival-session.js' and method=='GET':
                mime='application/javascript; charset=utf-8'
                if not token: status='401 Unauthorized'
                else: body='try{localStorage.setItem("mxsg-role","player");localStorage.setItem("mxsg-user","mx");}catch{}'
            elif path=='/auth/account' and method=='GET':
                if not token: status='303 See Other';headers.append(('Location','/auth/login'))
                else:
                    csrf=self.csrf(token)
                    body=page('账号',f'''<h1>账号</h1><div class="account-info"><p>当前账号：{escape(self.account()['username'])} · MX</p><p>本设备登录保留 30 天。</p></div><form method="post" action="/auth/logout"><input type="hidden" name="csrf" value="{csrf}"><button>退出此设备</button></form><form method="post" action="/auth/logout-all"><input type="hidden" name="csrf" value="{csrf}"><button class="secondary">退出所有设备</button></form><p><a href="/">返回主页</a></p>''')
            elif path in ('/auth/logout','/auth/logout-all') and method=='POST':
                if not token: raise ValueError('请先登录。')
                data=self.form(environ)
                if not hmac.compare_digest(data.get('csrf',''),self.csrf(token)): raise ValueError('Invalid form token')
                with self.db() as db:
                    if path.endswith('-all'): db.execute('DELETE FROM sessions')
                    else: db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
                headers.extend([cookie(COOKIE,'',0),('Location','/auth/login')]);status='303 See Other'
            else: status='404 Not Found';body='Not found'
        except (ValueError,UnicodeError):
            status='400 Bad Request';body=page('请重试','<h1>请重新打开登录页面</h1><p>页面已过期或请求无效。</p><p><a href="/auth/login">返回登录</a></p>')
        except Exception:
            status='503 Service Unavailable';body='Authentication temporarily unavailable'
        if mime.startswith('text/html'):
            headers.append(('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"))
        raw=body.encode()
        headers.extend([('Content-Type',mime),('Content-Length',str(len(raw)))])
        start(status,headers)
        return [raw]


_app=None
_lock=threading.Lock()
def app(environ,start):
    global _app
    if _app is None:
        with _lock:
            if _app is None: _app=Auth(os.environ.get('CHEMEX_AUTH_STATE','/var/lib/chemex-auth'))
    return _app(environ,start)
