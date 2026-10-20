"""Publish a shared visual stylesheet without replacing any application sources."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

LINK='<link rel="stylesheet" href="/site-theme.css?v=blue-gray-20261020">'
BEGIN='    # BEGIN ChemEx Shared Theme'
END='    # END ChemEx Shared Theme'


def update_nginx(original):
    if 'auth_request /_chemex_auth;' not in original:
        raise RuntimeError('Expected existing owner gate')
    if BEGIN not in original and 'location = /site-theme.css' in original:
        raise RuntimeError('Unmanaged theme route')
    block=f'''{BEGIN}
    location = /site-theme.css {{
        # Public presentation only; no app content or user data.
        auth_request off;
        alias /srv/chemex/theme/current/site-theme.css;
    }}
{END}

'''
    if BEGIN in original:
        updated,count=re.subn(re.escape(BEGIN)+r'.*?'+re.escape(END)+r'\n\n',lambda _:block,original,flags=re.S)
        if count!=1: raise RuntimeError('Unexpected theme markers')
    else:
        anchor='    # BEGIN ChemEx Personal Home'
        if original.count(anchor)!=1: raise RuntimeError('Expected unique canonical TLS anchor')
        updated=original.replace(anchor,block+anchor,1)
    # Per-location filters deliberately exclude COF/research and Survival.
    targets=['location = / {','location ^~ /miying/ {','location ^~ /epubreader/ {','location ^~ /auth/ {']
    for target in targets:
        pattern=r'(    '+re.escape(target)+r'\n)(.*?)(    }\n)'
        def add_filter(match):
            body=match[2]
            if '# ChemEx shared theme filter' in body:return match[0]
            if 'sub_filter' in body:raise RuntimeError('Inspect existing filter in '+target)
            injection=f'''        # ChemEx shared theme filter
        sub_filter_once on;
        sub_filter '</head>' '{LINK}</head>';
        sub_filter '<body' '<body data-chemex-page="$uri"';
'''
            return match[1]+injection+body+match[3]
        updated,count=re.subn(pattern,add_filter,updated,flags=re.S)
        if count!=1:raise RuntimeError('Expected unique theme target: '+target)
    return updated


def main():
    commit,asset=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit): raise ValueError('Expected full commit hash')
    css=Path(asset).read_bytes()
    if b'--cx-bg' not in css or b'data-chemex-page' not in css: raise ValueError('Unexpected theme asset')
    base=Path('/srv/chemex/theme')
    config=Path('/etc/nginx/sites-available/chemex-space.conf')
    original=config.read_text();replacement=update_nginx(original)
    release=base/'releases'/commit
    release.mkdir(parents=True,exist_ok=False)
    (release/'site-theme.css').write_bytes(css)
    release.chmod(0o755);(release/'site-theme.css').chmod(0o644)
    current=base/'current'
    if current.exists() and not current.is_symlink(): raise RuntimeError('Unexpected current directory')
    previous=os.readlink(current) if current.is_symlink() else None
    backup=base/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True);shutil.copy2(config,backup/'nginx.conf')
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    try:
        config.write_text(replacement)
        subprocess.run(['nginx','-t'],check=True)
        subprocess.run(['systemctl','reload','nginx'],check=True)
    except Exception:
        shutil.copy2(backup/'nginx.conf',config)
        if previous:pending.symlink_to(previous);os.replace(pending,current)
        else:current.unlink()
        subprocess.run(['nginx','-t'],check=True)
        subprocess.run(['systemctl','reload','nginx'],check=True)
        raise
    print(json.dumps({'commit':commit,'previous':previous,'backup':str(backup),'release':str(release)}))


if __name__=='__main__':main()
