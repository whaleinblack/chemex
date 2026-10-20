#!/usr/bin/env python3
"""Deploy a trusted livecaptions archive without replacing the shared ChemEx checkout.

Run with sudo on the ChemEx host: deploy-livecaptions.py <commit> <livecaptions.tar>
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
    base = Path('/srv/chemex/livecaptions')
    config = Path('/etc/nginx/sites-available/chemex-space.conf')
    marker = '# BEGIN ChemEx LiveCaptions'
    original = config.read_text()
    if 'auth_request /_chemex_auth;' not in original:
        raise RuntimeError('Expected existing ChemEx owner access gate')
    if '/livecaptions' in original and marker not in original:
        raise RuntimeError('Unmanaged livecaptions configuration already exists; inspect it first')
    stanza = '''    # BEGIN ChemEx LiveCaptions
    location = /livecaptions {
        return 308 /livecaptions/$is_args$args;
    }

    location ^~ /livecaptions/ {
        alias /srv/chemex/livecaptions/current/;
        index index.html;
    }
    # END ChemEx LiveCaptions

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
        for required in ['index.html', 'manifest.webmanifest', 'sw.js', 'sherpa/sherpa-onnx-wasm-main-vad-asr.wasm', 'models/silero_vad.onnx']:
            if not (release / required).is_file():
                raise RuntimeError('Incomplete livecaptions release: ' + required)
    manifest = json.loads((release / 'manifest.webmanifest').read_text())
    if manifest.get('scope') != '/livecaptions/' or manifest.get('start_url') != '/livecaptions/':
        raise RuntimeError('Incorrect LiveCaptions PWA scope')
    for path in [release, *release.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    current = base / 'current'
    previous = os.readlink(current) if current.is_symlink() else None
    if current.exists() and not current.is_symlink():
        raise RuntimeError('Current livecaptions path is not a symlink')
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
