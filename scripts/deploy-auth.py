"""Install the owner gate only on chemex.space, retaining all shared services."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen


def run(*args): subprocess.run(args,check=True)


def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit): raise ValueError('Expected full commit hash')
    base=Path('/srv/chemex/auth')
    config=Path('/etc/nginx/sites-available/chemex-space.conf')
    service=Path('/etc/systemd/system/chemex-auth.service')
    original=config.read_text()
    begin,end='# BEGIN ChemEx Owner Auth','# END ChemEx Owner Auth'
    if begin not in original and any(x in original for x in ['auth_request','/_chemex_auth','/auth/']):
        raise RuntimeError('Inspect existing authentication before changing it')
    stanza='''    # BEGIN ChemEx Owner Auth
    auth_request /_chemex_auth;
    error_page 401 = @chemex_login;
    location = /_chemex_auth {
        internal;
        auth_request off;
        proxy_pass http://127.0.0.1:4197/auth/check;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header Cookie $http_cookie;
    }
    location ^~ /auth/ {
        auth_request off;
        client_max_body_size 8k;
        proxy_pass http://127.0.0.1:4197;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Cookie $http_cookie;
        proxy_intercept_errors off;
    }
    location @chemex_login {
        auth_request off;
        return 302 /auth/login?next=$uri;
    }
    # END ChemEx Owner Auth

'''
    anchor='    # BEGIN ChemEx Personal Home'
    if begin in original:
        replacement,count=re.subn(r'    # BEGIN ChemEx Owner Auth.*?    # END ChemEx Owner Auth\n\n',stanza,original,flags=re.S)
        if count!=1: raise RuntimeError('Unexpected auth markers')
    else:
        if original.count(anchor)!=1: raise RuntimeError('Expected unique canonical TLS anchor')
        replacement=original.replace(anchor,stanza+anchor,1)
    survival='    location ^~ /survival/ {\n'
    bridge='''        # ChemEx authenticated MX bridge
        sub_filter_once on;
        sub_filter '</head>' '<script src="/auth/survival-session.js"></script></head>';
'''
    if '# ChemEx authenticated MX bridge' not in replacement:
        if replacement.count(survival)!=1: raise RuntimeError('Expected unique Survival UI location')
        replacement=replacement.replace(survival,survival+bridge,1)
    previous_service=service.read_text() if service.exists() else None
    if previous_service and 'Description=ChemEx Owner Authentication' not in previous_service:
        raise RuntimeError('Unmanaged service')
    if not previous_service:
        with socket.socket() as probe: probe.bind(('127.0.0.1',4197))
    release=base/'releases'/commit
    release.mkdir(parents=True,exist_ok=False)
    required={'server.py','init_survival.py'}
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            name=member.name.removeprefix('./')
            if name not in required or not member.isfile(): raise ValueError('Unexpected archive member')
            with archive.extractfile(member) as src,(release/name).open('wb') as dest: shutil.copyfileobj(src,dest)
    if not all((release/name).is_file() for name in required): raise RuntimeError('Incomplete auth release')
    for path in [release,*release.iterdir()]: path.chmod(0o755 if path.is_dir() else 0o644)
    # Credentials remain on the host; the only allowed imported identity is MX.
    run('/srv/chemex/venv/bin/python',str(release/'init_survival.py'))
    current=base/'current'
    if current.exists() and not current.is_symlink(): raise RuntimeError('Current is not a symlink')
    previous=os.readlink(current) if current.is_symlink() else None
    backup=base/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True)
    shutil.copy2(config,backup/'nginx.conf')
    if service.exists(): shutil.copy2(service,backup/'service.conf')
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    try:
        service.write_text('''[Unit]
Description=ChemEx Owner Authentication
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/srv/chemex/auth/current
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=CHEMEX_AUTH_STATE=/var/lib/chemex-auth
ExecStart=/srv/chemex/venv/bin/gunicorn --bind 127.0.0.1:4197 --workers 1 --threads 4 --timeout 30 server:app
StateDirectory=chemex-auth
StateDirectoryMode=0700
UMask=0077
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
''')
        run('systemctl','daemon-reload');run('systemctl','restart','chemex-auth.service')
        for attempt in range(15):
            try:
                with urlopen('http://127.0.0.1:4197/auth/health',timeout=2) as response:
                    if json.load(response).get('status')=='ok': break
            except Exception:
                if attempt==14: raise
                time.sleep(.5)
        config.write_text(replacement)
        run('nginx','-t');run('systemctl','reload','nginx');run('systemctl','enable','chemex-auth.service')
    except Exception:
        shutil.copy2(backup/'nginx.conf',config)
        if previous: pending.symlink_to(previous);os.replace(pending,current)
        else: current.unlink()
        if previous_service: service.write_text(previous_service)
        else:
            run('systemctl','stop','chemex-auth.service');service.unlink(missing_ok=True)
        run('systemctl','daemon-reload')
        if previous_service: run('systemctl','restart','chemex-auth.service')
        run('nginx','-t');run('systemctl','reload','nginx')
        raise
    print(json.dumps({'commit':commit,'previous':previous,'backup':str(backup),'identity':'survival-mx','remember_days':30}))


if __name__=='__main__': main()
