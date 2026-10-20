"""Publish the personal homepage and preserve the live research frontend verbatim."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit): raise ValueError('Expected full commit hash')
    base=Path('/srv/chemex/home')
    config=Path('/etc/nginx/sites-available/chemex-space.conf')
    original=config.read_text()
    begin,end='# BEGIN ChemEx Personal Home','# END ChemEx Personal Home'
    if begin not in original and any(x in original for x in ['/research','/home-assets','location = / {']):
        raise RuntimeError('Inspect conflicting homepage or research configuration')
    stanza='''    # BEGIN ChemEx Personal Home
    location = / {
        root /srv/chemex/home/current;
        try_files /index.html =404;
    }
    location ^~ /home-assets/ {
        alias /srv/chemex/home/current/assets/;
    }
    location = /favicon.ico {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/favicon.ico;
    }
    location = /apple-touch-icon.png {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/apple-touch-icon.png;
    }
    location = /apple-touch-icon-precomposed.png {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/apple-touch-icon.png;
    }
    location = /site-icon-avatar-v2.png {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/favicon.png;
    }
    location = /apple-touch-icon-avatar-v2.png {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/apple-touch-icon.png;
    }
    location = /home-assets/favicon.svg {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/favicon.svg;
    }
    location = /home-assets/favicon.png {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/favicon.png;
    }
    location = /home-assets/apple-touch-icon.png {
        # Public site identity: Safari may fetch icons without the owner cookie.
        auth_request off;
        alias /srv/chemex/home/current/assets/apple-touch-icon.png;
    }
    location = /research { return 308 /research/; }
    location ^~ /research/api/ {
        proxy_pass http://127.0.0.1:4180/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
    location ^~ /research/ {
        alias /srv/chemex/home/current/research/;
        index index.html;
    }
    # END ChemEx Personal Home

'''
    anchor='    # BEGIN ChemEx Pachong'
    if begin in original:
        replacement,count=re.subn(r'    # BEGIN ChemEx Personal Home.*?    # END ChemEx Personal Home\n\n',stanza,original,flags=re.S)
        if count!=1: raise RuntimeError('Unexpected homepage markers')
    else:
        if original.count(anchor)!=1: raise RuntimeError('Expected unique ChemEx TLS anchor')
        replacement=original.replace(anchor,stanza+anchor,1)
    release=base/'releases'/commit
    release.mkdir(parents=True,exist_ok=False)
    allowed={'index.html','style.css','favicon.svg','favicon.png','favicon.ico','apple-touch-icon.png','rajdhani-600.woff2','FONT-LICENSE','entrances/cof.png','entrances/miying.png','entrances/survival.png','entrances/epubreader.png'}
    (release/'assets').mkdir()
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            name=member.name.removeprefix('./')
            if name not in allowed or not member.isfile(): raise ValueError('Unexpected archive member')
            target=release/name if name=='index.html' else release/'assets'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.extractfile(member) as src,target.open('wb') as dest: shutil.copyfileobj(src,dest)
    for name in allowed:
        target=release/name if name=='index.html' else release/'assets'/name
        if not target.is_file(): raise RuntimeError('Incomplete homepage archive')
    # Copy only on the server. Never commit or replace independent live app changes.
    research=Path('/srv/chemex/app/dist')
    if not (research/'index.html').is_file(): raise RuntimeError('Missing live research frontend')
    if any(p.is_symlink() for p in research.rglob('*')): raise RuntimeError('Inspect symlinks before snapshot')
    shutil.copytree(research,release/'research')
    fingerprint=hashlib.sha256((research/'index.html').read_bytes()).hexdigest()
    if hashlib.sha256((release/'research/index.html').read_bytes()).hexdigest()!=fingerprint:
        raise RuntimeError('Research frontend changed during snapshot')
    for path in [release,*release.rglob('*')]: path.chmod(0o755 if path.is_dir() else 0o644)
    current=base/'current'
    if current.exists() and not current.is_symlink(): raise RuntimeError('Current is not a symlink')
    previous=os.readlink(current) if current.is_symlink() else None
    backup=base/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True)
    shutil.copy2(config,backup/'nginx.conf')
    pending=base/('current-'+commit)
    pending.symlink_to(release)
    os.replace(pending,current)
    try:
        config.write_text(replacement)
        subprocess.run(['nginx','-t'],check=True)
        subprocess.run(['systemctl','reload','nginx'],check=True)
    except Exception:
        shutil.copy2(backup/'nginx.conf',config)
        if previous:
            pending.symlink_to(previous)
            os.replace(pending,current)
        else: current.unlink()
        subprocess.run(['nginx','-t'],check=True)
        subprocess.run(['systemctl','reload','nginx'],check=True)
        raise
    print(json.dumps({'commit':commit,'previous':previous,'backup':str(backup),'research_index_sha256':fingerprint}))


if __name__=='__main__': main()
