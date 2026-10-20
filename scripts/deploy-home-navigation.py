"""Versioned homepage layout and isolated Survival home-link injection."""
import datetime,hashlib,json,os,re,shutil,subprocess,sys,tarfile
from pathlib import Path

BRIDGE='<script src="/auth/survival-session.js"></script>'
SHORTCUT='<script defer src="/home-assets/return-home.js?v=20261020"></script>'

def update_nginx(original):
    pattern=r'(    location \^~ /survival/ \{\n)(.*?)(    }\n)'
    def patch(match):
        body=match[2]
        if body.count(BRIDGE)!=1 or SHORTCUT in body:raise RuntimeError('Inspect Survival bridge')
        return match[1]+body.replace(BRIDGE,BRIDGE+SHORTCUT,1)+match[3]
    updated,count=re.subn(pattern,patch,original,flags=re.S)
    if count!=1:raise RuntimeError('Expected unique Survival location')
    return updated

def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Expected full commit')
    base=Path('/srv/chemex/home');current=base/'current';source=current.resolve(strict=True)
    if not current.is_symlink() or source.parent!=base/'releases':raise RuntimeError('Unmanaged home')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Inspect nested symlinks')
    config=Path('/etc/nginx/sites-available/chemex-space.conf');original=config.read_text();updated=update_nginx(original)
    with tarfile.open(archive_path) as archive:
        members=archive.getmembers()
        if sorted(m.name for m in members)!=['index.html','return-home.js','return-home.png','style.css']:raise RuntimeError('Unexpected archive entries')
        changes={}
        for member in members:
            if not member.isfile() or member.size>2000000:raise RuntimeError('Unexpected file')
            changes['index.html' if member.name=='index.html' else 'assets/'+member.name]=archive.extractfile(member).read()
    release=base/'releases'/commit;shutil.copytree(source,release)
    for name,data in changes.items():(release/name).write_bytes(data);(release/name).chmod(0o644)
    for p in source.rglob('*'):
        rel=str(p.relative_to(source))
        if p.is_file() and rel not in changes:
            if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((release/rel).read_bytes()).digest():raise RuntimeError('Unexpected resource change')
    backup=base/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup.mkdir(parents=True);shutil.copy2(config,backup/'nginx.conf')
    pending=base/('current-'+commit);pending.symlink_to(release);os.replace(pending,current)
    try:
        config.write_text(updated);subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
    except Exception:
        shutil.copy2(backup/'nginx.conf',config);pending.symlink_to(source);os.replace(pending,current)
        subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True);raise
    print(json.dumps({'commit':commit,'previous':str(source),'release':str(release),'backup':str(backup),'changes':list(changes)}))

if __name__=='__main__':main()
