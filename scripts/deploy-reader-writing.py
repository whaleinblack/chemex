"""Install the checked writing-mode feature without touching other reader resources."""
import hashlib,json,os,re,shutil,sys,tarfile
from pathlib import Path

EXPECTED = {'reader.js': '03d1a2c1ce5081eee6c52a45e62300c94d54228c8ca4f86c09c09e4f9cd7da1e', 'reader-preferences.js': 'ce53c5911dd32a9bd6484806bd62145a51d7b7cc083298ec3a4d7a06179221fc'}

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
    if b'changeWritingMode' not in changes['reader.js'] or b"writing:'original'" not in changes['reader-preferences.js']:raise RuntimeError('Unexpected feature bundle')
    html=(source/'index.html').read_bytes()
    for name in EXPECTED:
        old=('./'+name+'"').encode();new=('./'+name+'?v=writing-20261021"').encode()
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
