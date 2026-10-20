"""Publish the shared home shortcut without replacing live application sources."""
import datetime,hashlib,json,os,re,shutil,subprocess,sys,tarfile
from pathlib import Path

OLD='<script defer src="/home-assets/return-home.js?v=mobile-up4-20261020"></script>'
SCRIPT='<script defer src="/home-assets/return-home.js?v=mobile-gap-20261020"></script>'

def update_nginx(original):
    if original.count(OLD)!=4:raise RuntimeError('Expected four existing shortcut tags')
    return original.replace(OLD,SCRIPT)

def main():
    commit,archive_path=sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Expected full commit')
    base=Path('/srv/chemex/home');current=base/'current';source=current.resolve(strict=True)
    if not current.is_symlink() or source.parent!=base/'releases':raise RuntimeError('Unmanaged home')
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Inspect nested symlinks')
    config=Path('/etc/nginx/sites-available/chemex-space.conf');original=config.read_text();updated=update_nginx(original)
    with tarfile.open(archive_path) as archive:
        members=archive.getmembers()
        if sorted(m.name for m in members)!=['return-home.js']:raise RuntimeError('Unexpected archive entries')
        changes={}
        for member in members:
            if not member.isfile() or member.size>2000000:raise RuntimeError('Unexpected file')
            changes['assets/return-home.js']=archive.extractfile(member).read()
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
