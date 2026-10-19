"""ChemEx film discovery: bounded public metadata adapter and WSGI app."""
import json
import mimetypes
import re
import threading
import time
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parent
ORIGIN = 'https://www1.ikanbot.com'
CACHE = OrderedDict()
LOCK = threading.RLock()
FETCH_LOCK = threading.Lock()
VISITS = OrderedDict()
POSTER_CACHE = OrderedDict()
TAGS = ['热门','最新','经典','豆瓣高分','冷门佳片','华语','欧美','韩国','日本','动作','喜剧','爱情','科幻','悬疑','恐怖','动画','豆瓣top250']


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def find(self, tag=None, cls=None, ident=None):
        return [n for n in self.walk() if (not tag or n.tag == tag) and
                (not cls or cls in n.attrs.get('class','').split()) and
                (not ident or n.attrs.get('id') == ident)]

    def walk(self):
        for n in self.children:
            if isinstance(n, Node):
                yield n
                yield from n.walk()

    def text(self):
        return ' '.join(' '.join(x.text() if isinstance(x, Node) else x for x in self.children).split())


class Document(HTMLParser):
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in self.VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        n = self.cur
        while n.parent:
            if n.tag == tag:
                self.cur = n.parent
                return
            n = n.parent

    def handle_data(self, data):
        if self.cur.tag not in ('script','style'):
            self.cur.children.append(data)


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).netloc != urlsplit(ORIGIN).netloc or urlsplit(newurl).scheme != 'https':
            raise ValueError('Unexpected upstream redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(path):
    if not path.startswith('/') or path.startswith('//'):
        raise ValueError('Invalid upstream path')
    with LOCK:
        hit = CACHE.get(path)
        if hit and time.time() - hit[0] < 180:
            return hit[1]
    # One upstream request at a time; duplicate concurrent requests share the cache.
    with FETCH_LOCK:
        with LOCK:
            hit = CACHE.get(path)
            if hit and time.time() - hit[0] < 180:
                return hit[1]
        req = Request(ORIGIN + path, headers={'User-Agent':'ChemEx-Pachong/1.0', 'Accept':'text/html,application/json', 'Referer':ORIGIN+'/'})
        with build_opener(SameOriginRedirect()).open(req, timeout=15) as response:
            raw = response.read(3*1024*1024+1)
            if len(raw)>3*1024*1024:
                raise ValueError('Upstream response too large')
            result = raw.decode('utf-8')
        with LOCK:
            CACHE[path] = (time.time(), result)
            while len(CACHE)>128:
                CACHE.popitem(last=False)
        return result


def remote_url(value):
    try:
        u = urlsplit(value or '')
        if u.scheme == 'https' and u.hostname and not u.username and not u.password:
            return value
    except ValueError:
        pass
    return ''


def poster_bytes(url):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or not re.fullmatch(r'img[1-9]\.doubanio\.com',parsed.netloc)
            or not re.fullmatch(r'/(?:view/photo/[\w/-]+|lpic)/[\w.-]+\.(?:jpg|png|webp)',parsed.path,re.I)
            or parsed.query or parsed.fragment):
        raise ValueError('Unsupported poster URL')
    with LOCK:
        hit=POSTER_CACHE.get(url)
        if hit and time.time()-hit[0]<3600: return hit[1],hit[2]
    # No redirects: the validated image host is the only request destination.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ChemEx-Pachong/1.0)', 'Referer':'https://movie.douban.com/'})
    with build_opener(NoRedirect()).open(req,timeout=8) as response:
        mime=response.headers.get_content_type()
        raw=response.read(512*1024+1)
        if len(raw)>512*1024 or mime not in ('image/jpeg','image/png','image/webp'):
            raise ValueError('Unsupported poster response')
    with LOCK:
        POSTER_CACHE[url]=(time.time(),raw,mime)
        while len(POSTER_CACHE)>64: POSTER_CACHE.popitem(last=False)
    return raw,mime


def movie_items(root):
    result = OrderedDict()
    for a in root.find('a'):
        match = re.fullmatch(r'/play/(\d+)', a.attrs.get('href',''))
        if not match:
            continue
        ident = match[1]
        item = result.setdefault(ident, {'id':ident,'title':'','poster':'','summary':''})
        images = a.find('img')
        if images:
            item['poster'] = remote_url(images[0].attrs.get('data-src') or images[0].attrs.get('src'))
            item['title'] = images[0].attrs.get('alt','').strip()
        title = a.text()
        if title and not item['title']:
            item['title'] = title
        if 'title-text' in a.attrs.get('class',''):
            item['summary'] = a.parent.parent.text()[:350]
    return [x for x in result.values() if x['title']]


def listing(path):
    root = Document(fetch(path)).root
    pages = []
    for a in root.find('a'):
        href = a.attrs.get('href','')
        if a.text() in ('下一页','上一页') and href.startswith(('/search?','/hot/')):
            pages.append({'label':a.text(),'path':href})
    return {'items':movie_items(root),'pages':pages}


def detail(ident):
    html = fetch('/play/'+ident)
    root = Document(html).root
    title_nodes = root.find(ident='video_title')
    if not title_nodes:
        raise ValueError('影片不存在或原站结构已变化')
    inputs = {n.attrs.get('id'):n.attrs.get('value','') for n in root.find('input')}
    metadata = root.find(cls='detail')
    info = [n.text() for n in metadata[0].find('h3')] if metadata else []
    images = [n for n in root.find('img') if n.attrs.get('id')==ident]
    token = inputs.get('e_token','')
    parts = []
    for digit in ident[-4:]:
        offset = int(digit)%3+1
        parts.append(token[offset:offset+8])
        token = token[offset+8:]
    data = json.loads(fetch('/api/getResN?'+urlencode({'videoId':ident,'mtype':inputs.get('mtype','1'),'token':''.join(parts)})))
    lines = []
    for i, entry in enumerate(data.get('data',{}).get('list',[])[:60]):
        episodes = []
        try:
            resources = json.loads(entry.get('resData','[]'))
        except (ValueError, TypeError):
            continue
        for group in resources[:20]:
            for item in str(group.get('url','')).split('#')[:1000]:
                name, sep, url = item.partition('$')
                url = remote_url(url)
                if sep and url and re.search(r'\.(m3u8|mp4)(?:\?|$)',url,re.I):
                    episodes.append({'name':name[:100], 'url':url})
        if episodes:
            lines.append({'name':f'线路 {i+1}', 'episodes':episodes[:1000]})
    return {'id':ident,'title':title_nodes[0].text(),'info':info,
            'poster':remote_url(images[0].attrs.get('data-src','')) if images else '',
            'lines':lines,'source':ORIGIN+'/play/'+ident,
            'notice':'' if lines else '原站暂未返回可播放线路，请稍后重试。'}


def api(route, params):
    arg = lambda name, default='':params.get(name,[default])[0]
    if route=='health':
        return {'status':'ok'}
    if route=='home':
        root = Document(fetch('/')).root
        sections = []
        for block in root.find(cls='v-list'):
            items = movie_items(block)
            if items:
                heads = block.find('h4')
                sections.append({'title':heads[0].text().replace('更多»','') if heads else '热门影片','items':items})
        if not sections:
            items = movie_items(root)
            if not items:
                raise ValueError('原站暂未返回影片列表')
            sections = [{'title':'近期热门','items':items}]
        return {'sections':sections}
    if route=='search':
        query = arg('q').strip()
        if not query or len(query)>100:
            raise ValueError('请输入 1–100 字的关键词')
        return listing('/search?'+urlencode({'q':query}))
    if route=='list':
        path = arg('path')
        if len(path)>1500 or not re.fullmatch(r'/(?:hot/[\w%\-\.]+|search\?[^\s#]+|billboard\.html)',path):
            raise ValueError('Invalid listing path')
        return listing(quote(path,safe='/%?=&-._~+'))
    if route=='catalog':
        kind, tag = arg('kind','movie'), arg('tag','热门')
        if kind not in ('movie','tv') or tag not in TAGS:
            raise ValueError('Invalid category')
        return listing('/hot/index-'+kind+'-'+quote(tag)+'.html')
    if route=='detail':
        ident = arg('id')
        if not re.fullmatch(r'\d{1,12}',ident):
            raise ValueError('Invalid film id')
        return detail(ident)
    raise FileNotFoundError()


def app(environ, start_response):
    status, headers = '200 OK', [('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Cache-Control','no-store')]
    try:
        path = environ.get('PATH_INFO','')
        if environ.get('REQUEST_METHOD')!='GET':
            start_response('405 Method Not Allowed',headers)
            return [b'Method not allowed']
        if path=='/pachong/poster':
            params=parse_qs(environ.get('QUERY_STRING',''),max_num_fields=1)
            body,mime=poster_bytes(params.get('url',[''])[0])
            headers=[h for h in headers if h[0]!='Cache-Control']
            headers.extend([('Content-Type',mime),('Cache-Control','public, max-age=3600')])
        elif path.startswith('/pachong/api/'):
            if not path.endswith('/health'):
                ip = environ.get('HTTP_X_REAL_IP') or environ.get('REMOTE_ADDR','local')
                now = time.monotonic()
                with LOCK:
                    window,count = VISITS.get(ip,(now,0))
                    if now-window>60: window,count=now,0
                    VISITS[ip]=(window,count+1)
                    while len(VISITS)>1024: VISITS.popitem(last=False)
                if count>=80:
                    body=json.dumps({'error':'请求较频繁，请稍后再试。'},ensure_ascii=False).encode()
                    start_response('429 Too Many Requests',headers+[('Content-Type','application/json; charset=utf-8'),('Retry-After','60')])
                    return [body]
            data = api(path.rsplit('/',1)[-1],parse_qs(environ.get('QUERY_STRING',''),max_num_fields=10))
            body = json.dumps(data,ensure_ascii=False).encode()
            headers.append(('Content-Type','application/json; charset=utf-8'))
        else:
            name = path.removeprefix('/pachong/').strip('/') or 'index.html'
            allowed = {'index.html','app.js','style.css','player-shortcuts.js','vendor/hls.min.js','vendor/LICENSE'}
            if not path.startswith('/pachong/') or name not in allowed:
                raise FileNotFoundError()
            body = (ROOT/name).read_bytes()
            headers.append(('Content-Type',(mimetypes.guess_type(name)[0] or 'text/plain')+'; charset=utf-8'))
    except FileNotFoundError:
        status, body = '404 Not Found', b'Not found'
    except ValueError as e:
        status = '400 Bad Request'
        body = json.dumps({'error':str(e)},ensure_ascii=False).encode()
        headers.append(('Content-Type','application/json; charset=utf-8'))
    except Exception:
        status = '502 Bad Gateway'
        body = json.dumps({'error':'暂时无法获取原站数据，请稍后重试。'},ensure_ascii=False).encode()
        headers.append(('Content-Type','application/json; charset=utf-8'))
    headers.append(('Content-Length',str(len(body))))
    start_response(status,headers)
    return [body]


if __name__=='__main__':
    from wsgiref.simple_server import make_server
    make_server('127.0.0.1',4198,app).serve_forever()

