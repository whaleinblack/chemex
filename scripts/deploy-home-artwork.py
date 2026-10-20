"""Publish only the revised COF entrance PNG, retaining all other live home files."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile


def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Expected full commit')
    base=Path('/srv/chemex/home');current=base/'current';source=current.resolve(strict=True)
    if not current.is_symlink() or source.parent!=base/'releases':raise RuntimeError('Unmanaged homepage')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Inspect nested symlinks')
    changes={}
    with tarfile.open(archive_path) as archive:
        members=archive.getmembers()
        if sorted(m.name for m in members)!=['cof.png']:raise RuntimeError('Unexpected archive entries')
        for member in members:
            if not member.isfile() or member.size>2000000:raise RuntimeError('Unexpected image')
            data=archive.extractfile(member).read()
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('Expected PNG')
            changes['assets/entrances/'+member.name]=data
    html=(source/'index.html').read_bytes()
    for name in ['cof']:
        old=('/home-assets/entrances/'+name+'.png"').encode()
        new=('/home-assets/entrances/'+name+'.png?v=jail-20261020"').encode()
        if html.count(old)!=1:raise RuntimeError('Unexpected entrance source: '+name)
        html=html.replace(old,new,1)
    changes['index.html']=html
    release=base/'releases'/commit
    shutil.copytree(source,release)
    for name,data in changes.items():
        (release/name).write_bytes(data);(release/name).chmod(0o644)
    for p in source.rglob('*'):
        relative=str(p.relative_to(source))
        if p.is_file() and relative not in changes:
            if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((release/relative).read_bytes()).digest():
                raise RuntimeError('Unexpected homepage resource change: '+relative)
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    print(json.dumps({'commit':commit,'previous':str(source),'release':str(release),'changes':list(changes)}))


if __name__=='__main__':main()
