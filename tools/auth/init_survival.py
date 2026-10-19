"""Import only the authorized MX credential on the host; never print/transfer it."""
import json
import os
from pathlib import Path
import pwd
import re
import secrets
from server import password_hash


def main():
    state=Path('/var/lib/chemex-auth')
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    owner=pwd.getpwnam('ubuntu')
    os.chown(state,owner.pw_uid,owner.pw_gid);state.chmod(0o700)
    target=state/'account.json'
    if target.exists():
        account=json.loads(target.read_text())
        if account.get('source')!='survival-mx': raise RuntimeError('Existing unmanaged account')
        print('Existing MX account retained; no password change.')
        return
    folder=Path('/srv/mxsg/survival/current')
    index=(folder/'index.html').read_text()
    match=re.search(r'src="(/survival/)?(assets/[^" ]+\.js)"',index)
    if not match: raise RuntimeError('Missing Survival bundle')
    source=(folder/match[2]).read_text()
    records=[]
    for m in re.finditer(r'\{username:("(?:\\.|[^"\\])*"),password:("(?:\\.|[^"\\])*"),role:("(?:\\.|[^"\\])*")(?:,playerId:("(?:\\.|[^"\\])*"))?\}',source):
        if m[4] and json.loads(m[4])=='mx' and json.loads(m[3])=='player':
            records.append((json.loads(m[1]),json.loads(m[2])))
    if len(records)!=1: raise RuntimeError('Expected one MX player account; inspect without printing secrets')
    salt=secrets.token_hex(16)
    account={'username':records[0][0],'salt':salt,'hash':password_hash(records[0][1],salt),'source':'survival-mx'}
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f: json.dump(account,f)
    os.chown(target,owner.pw_uid,owner.pw_gid)
    print('MX credential imported as a password hash; no secret output.')


if __name__=='__main__': main()
