"""Install the checked removal of highlights and notes without touching other reader resources."""
import hashlib,json,os,re,shutil,sys,tarfile
from pathlib import Path

EXPECTED = {'reader.js': '41d04299a3fbdc07584bc9a7d1dbf32b14c32f6b3b87df503e59085ced13866d'}
HTML_REPLACEMENTS = [('目录搜索和阅读笔记', '目录搜索和书签', 1), ('书籍、进度和笔记', '书籍、进度和书签', 1), ('书签与笔记', '书签', 3), ('<div id="selection-tools" class="selection-tools" hidden><button id="highlight">荧光标记</button><button id="add-note">添加笔记</button></div>', '', 1), ('<dialog id="note-dialog"><form method="dialog"><h2>添加笔记</h2><blockquote id="note-quote"></blockquote><textarea id="note-text" placeholder="写下你的想法…" aria-label="笔记内容" rows="5"></textarea><div class="dialog-actions"><button value="cancel" class="secondary">取消</button><button id="save-note" value="save" class="primary">保存笔记</button></div></form></dialog>', '', 1)]

def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Expected full commit')
    base=Path('/srv/chemex/epubreader');current=base/'current';source=current.resolve(strict=True)
    if not current.is_symlink() or source.parent!=base/'releases':raise RuntimeError('Unmanaged reader release')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Inspect nested symlinks')
    for name,expected in EXPECTED.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Live reader changed; reconcile '+name)
    with tarfile.open(archive_path) as archive:
        members=archive.getmembers()
        if sorted(m.name for m in members)!=sorted(EXPECTED):raise RuntimeError('Unexpected archive files')
        changes={}
        for member in members:
            if not member.isfile() or member.size>200000:raise RuntimeError('Unexpected file')
            changes[member.name]=archive.extractfile(member).read()
    if b'horizontalStylesheet' not in changes['reader.js']:raise RuntimeError('Unexpected feature bundle')
    html=(source/'index.html').read_bytes()
    for old,new,count in HTML_REPLACEMENTS:
        if html.count(old.encode())!=count:raise RuntimeError('Unexpected reader UI markup')
        html=html.replace(old.encode(),new.encode())
    for name in EXPECTED:
        old=('./'+name+'?v=hidden-scrollbars-20261021"').encode();new=('./'+name+'?v=quiet-selection-20261021"').encode()
        if html.count(old)!=1:raise RuntimeError('Unexpected script URL: '+name)
        html=html.replace(old,new,1)
    changes['index.html']=html
    release=base/'releases'/commit;shutil.copytree(source,release)
    for name,data in changes.items():(release/name).write_bytes(data)
    for p in source.rglob('*'):
        relative=str(p.relative_to(source))
        if p.is_file() and relative not in changes:
            if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((release/relative).read_bytes()).digest():raise RuntimeError('Unexpected resource change')
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    print(json.dumps({'commit':commit,'previous':str(source),'release':str(release),'changes':list(changes)}))

if __name__=='__main__':main()
