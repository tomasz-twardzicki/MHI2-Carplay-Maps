#!/usr/bin/env python3
"""Apply the retained-session archive collision fix to the pinned base scripts."""
import hashlib
from pathlib import Path

TARGETS = {
    'Custom/carplay_mu1367_guidance_v3/actions.sh': 'R',
    'Custom/carplay_mu1367_map_only/actions.sh': 'R',
    'Custom/carplay_mu1367_android_auto/control.sh': 'ROOT',
}


def selector(root):
    return ''' # A PID can recur after reboot. Preserve every existing numeric archive.
 ARCHIVE_N=$$
 ARCHIVE_TRIES=0
 BACK=$%s.removed-$ARCHIVE_N
 while ! absent "$BACK";do
  ARCHIVE_TRIES=$((ARCHIVE_TRIES+1))
  [ "$ARCHIVE_TRIES" -lt 10000 ] || fail RETAINED_SESSION_NAMES_EXHAUSTED
  ARCHIVE_N=$((ARCHIVE_N+1))
  BACK=$%s.removed-$ARCHIVE_N
 done
''' % (root, root)


def apply(sd):
    sd=Path(sd);changes={};hashes={}
    for name,root in TARGETS.items():
        path=sd/name;before=path.read_bytes();text=before.decode()
        old=' BACK=$%s.removed-$$\n absent "$BACK" || fail RETAINED_SESSION_EXISTS\n' % root
        assert text.count(old)==1,name
        if root=='R':
            # The shared installer lock covers choosing and renaming the archive.
            old+=' mkdir "$LOCK" || fail INSTALLER_LOCKED\n OWN=yes\n'
            new=' mkdir "$LOCK" || fail INSTALLER_LOCKED\n OWN=yes\n'+selector(root)
        else:
            # Android Auto already holds its operation lock at this point.
            new=selector(root)
        after=text.replace(old,new).encode();path.write_bytes(after)
        hashes[hashlib.sha256(before).hexdigest()]=hashlib.sha256(after).hexdigest()
        changes[name]=dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest())
    # Refresh the exact payload checks that pin these three scripts.
    for path in sorted((sd/'Custom').rglob('payload-check.sh')):
        before=path.read_bytes();text=before.decode()
        for old,new in hashes.items():text=text.replace(old,new)
        after=text.encode()
        if after!=before:
            path.write_bytes(after)
            changes[str(path.relative_to(sd))]=dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest())
    return changes
