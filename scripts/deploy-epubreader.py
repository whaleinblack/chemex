#!/usr/bin/env python3
"""Deploy a trusted reader archive without replacing the shared ChemEx checkout.

Run with sudo on the ChemEx host: deploy-epubreader.py <commit> <reader.tar>
"""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


def main():
    commit, archive_path = sys.argv[1:]
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected a complete Git commit hash')
    base = Path('/srv/chemex/epubreader')
    config = Path('/etc/nginx/sites-available/chemex-space.conf')
    marker = '# BEGIN ChemEx EPUB Reader'
    original = config.read_text()
    if '/epubreader' in original and marker not in original:
        raise RuntimeError('Unmanaged reader configuration already exists; inspect it first')
    stanza = '''    # BEGIN ChemEx EPUB Reader
    location = /epubreader {
        return 308 /epubreader/;
    }

    location ^~ /epubreader/ {
        alias /srv/chemex/epubreader/current/;
        index index.html;
    }
    # END ChemEx EPUB Reader

'''
    anchor = '    location = /survival {'
    if marker not in original and original.count(anchor) != 1:
        raise RuntimeError('Expected a unique ChemEx TLS configuration anchor')
    replacement = original if marker in original else original.replace(anchor, stanza + anchor, 1)
    release = base / 'releases' / commit
    if release.exists():
        raise RuntimeError('Release already exists; reuse it or select a new commit')
    release.mkdir(parents=True)
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            name = Path(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member')
            target = release / name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('wb') as destination:
                    shutil.copyfileobj(source, destination)
        for required in ['index.html', 'reader.js', 'reader.css', 'vendor/epub.min.js', 'vendor/jszip.min.js']:
            if not (release / required).is_file():
                raise RuntimeError('Incomplete reader release: ' + required)
    for path in [release, *release.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    current = base / 'current'
    previous = os.readlink(current) if current.is_symlink() else None
    if current.exists() and not current.is_symlink():
        raise RuntimeError('Current reader path is not a symlink')
    backups = base / 'backups'
    backups.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = backups / ('nginx-' + stamp + '.conf')
    shutil.copy2(config, backup)
    pending = base / ('current-' + commit)
    pending.symlink_to(release)
    os.replace(pending, current)
    try:
        config.write_text(replacement)
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    except Exception:
        shutil.copy2(backup, config)
        if previous is None:
            current.unlink()
        else:
            pending.symlink_to(previous)
            os.replace(pending, current)
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        raise
    result = {'commit': commit, 'release': str(release), 'previous': previous, 'nginx_backup': str(backup)}
    (backups / ('release-' + stamp + '.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
