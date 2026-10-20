"""Add optional cream paper without replacing independent live reader changes."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

REPLACEMENTS={
 'reader.js':[
  (b"sepia:['#e9eef5','#1e293b'],dark:",b"sepia:['#e9eef5','#1e293b'],cream:['#f2e8d5','#4d402d'],dark:"),
  ("['sepia','浅灰'],['dark','深夜']".encode(),"['sepia','浅灰'],['cream','米黄'],['dark','深夜']".encode())],
 'reader-preferences.js':[(b"['paper','sepia','dark']",b"['paper','sepia','cream','dark']")]
}

def patch_file(name,data):
    for old,new in REPLACEMENTS[name]:
        if data.count(old)!=1:raise RuntimeError('Unexpected live reader settings in '+name)
        data=data.replace(old,new,1)
    return data


def main():
    commit=sys.argv[1]
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Expected full commit hash')
    base=Path('/srv/chemex/epubreader');current=base/'current';source=current.resolve(strict=True)
    if not current.is_symlink() or source.parent!=base/'releases':raise RuntimeError('Unmanaged reader release')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Inspect reader symlinks')
    changes={name:patch_file(name,(source/name).read_bytes()) for name in REPLACEMENTS}
    release=base/'releases'/commit
    shutil.copytree(source,release)
    for name,data in changes.items():(release/name).write_bytes(data)
    for p in source.rglob('*'):
        if p.is_file() and str(p.relative_to(source)) not in changes:
            if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((release/p.relative_to(source)).read_bytes()).digest():
                raise RuntimeError('Unexpected change to reader resource')
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    print(json.dumps({'commit':commit,'release':str(release),'previous':str(source),'changes':'optional cream paper and preference compatibility only'}))

if __name__=='__main__':main()
