"""Install an isolated trusted Pachong release, preserving the shared server."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
from urllib.request import urlopen


def run(*args):
    subprocess.run(args,check=True)


def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('Expected complete commit hash')
    base=Path('/srv/chemex/pachong')
    config=Path('/etc/nginx/sites-available/chemex-space.conf')
    service=Path('/etc/systemd/system/chemex-pachong.service')
    marker='# BEGIN ChemEx Pachong'
    original=config.read_text()
    if '/pachong' in original and marker not in original:
        raise RuntimeError('Unmanaged /pachong config; inspect before deploying')
    if service.exists() and 'Description=ChemEx Pachong' not in service.read_text():
        raise RuntimeError('Unmanaged service')
    stanza='''    # BEGIN ChemEx Pachong
    location = /pachong { return 308 /pachong/; }
    location ^~ /pachong/ {
        proxy_pass http://127.0.0.1:4198;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 40;
    }
    # END ChemEx Pachong

'''
    anchor='    # BEGIN ChemEx EPUB Reader'
    if marker not in original and original.count(anchor)!=1:
        raise RuntimeError('Expected a unique ChemEx TLS anchor')
    replacement=original if marker in original else original.replace(anchor,stanza+anchor,1)
    release=base/'releases'/commit
    release.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            name=Path(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isdir() or member.isfile()):
                raise ValueError('Unsafe archive')
            target=release/name
            if member.isdir(): target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as src,target.open('wb') as dest: shutil.copyfileobj(src,dest)
    for name in ['server.py','index.html','app.js','style.css','vendor/hls.min.js','vendor/LICENSE']:
        if not (release/name).is_file(): raise RuntimeError('Incomplete release')
    for path in [release,*release.rglob('*')]: path.chmod(0o755 if path.is_dir() else 0o644)
    current=base/'current'
    if current.exists() and not current.is_symlink(): raise RuntimeError('Current is not a symlink')
    previous=os.readlink(current) if current.is_symlink() else None
    previous_service=service.read_text() if service.exists() else None
    if previous_service is None:
        import socket
        with socket.socket() as probe: probe.bind(('127.0.0.1',4198))
    backup=base/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True)
    shutil.copy2(config,backup/'nginx.conf')
    if service.exists(): shutil.copy2(service,backup/'service.conf')
    pending=base/('current-'+commit)
    pending.symlink_to(release)
    os.replace(pending,current)
    try:
        service.write_text('''[Unit]
Description=ChemEx Pachong
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/srv/chemex/pachong/current
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/srv/chemex/venv/bin/gunicorn --bind 127.0.0.1:4198 --workers 1 --threads 6 --timeout 45 server:app
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
''')
        run('systemctl','daemon-reload')
        run('systemctl','restart','chemex-pachong.service')
        import time
        for attempt in range(15):
            try:
                with urlopen('http://127.0.0.1:4198/pachong/api/health',timeout=2) as response:
                    if json.load(response).get('status')=='ok': break
            except Exception:
                if attempt==14: raise
                time.sleep(.5)
        config.write_text(replacement)
        run('nginx','-t')
        run('systemctl','reload','nginx')
        run('systemctl','enable','chemex-pachong.service')
    except Exception:
        shutil.copy2(backup/'nginx.conf',config)
        if previous:
            pending.symlink_to(previous)
            os.replace(pending,current)
        else: current.unlink()
        if previous_service: service.write_text(previous_service)
        else:
            run('systemctl','stop','chemex-pachong.service')
            service.unlink(missing_ok=True)
        run('systemctl','daemon-reload')
        if previous_service: run('systemctl','restart','chemex-pachong.service')
        run('nginx','-t')
        run('systemctl','reload','nginx')
        raise
    print(json.dumps({'commit':commit,'previous':previous,'backup':str(backup)}))


if __name__=='__main__': main()
