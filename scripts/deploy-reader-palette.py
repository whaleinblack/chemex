"""Change only EPUB paper colors, preserving live reader repairs byte-for-byte."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

OLD=b"paper:['#fcfbf8','#282720'],sepia:['#f2e8d5','#4d402d'],dark:['#222321','#dddcd5']"
NEW=b"paper:['#f4f6fa','#1e293b'],sepia:['#e9eef5','#1e293b'],dark:['#111827','#e7edf7']"


def main():
    commit=sys.argv[1]
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Expected full commit hash')
    base=Path('/srv/chemex/epubreader');current=base/'current';source=current.resolve(strict=True)
    if not current.is_symlink() or source.parent!=base/'releases':raise RuntimeError('Unmanaged reader release')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Inspect reader symlinks')
    old=(source/'reader.js').read_bytes()
    if old.count(OLD)!=1 or old.count("['sepia','暖色']".encode())!=1:raise RuntimeError('Unexpected live paper settings')
    changed=old.replace(OLD,NEW,1).replace("['sepia','暖色']".encode(),"['sepia','浅灰']".encode(),1)
    release=base/'releases'/commit
    shutil.copytree(source,release)
    (release/'reader.js').write_bytes(changed)
    for p in source.rglob('*'):
        if p.is_file() and p.name!='reader.js':
            if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((release/p.relative_to(source)).read_bytes()).digest():
                raise RuntimeError('Unexpected change to reader resource')
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    print(json.dumps({'commit':commit,'release':str(release),'previous':str(source),'changes':'paper palette and label only'}))


if __name__=='__main__':main()
