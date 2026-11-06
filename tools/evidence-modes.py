#!/usr/bin/env python3
"""Every file CI's evidence step uploads must be readable by another user.

The linux job runs tools/gate in a container as root, then uploads the paths
listed under `name: linux-evidence` in .github/workflows/ci.yml as the runner
user, who is neither the files' owner nor in their group. A collected file
without the others-read bit, or a directory without others-read and
others-search, fails that upload with EACCES. This check reads the upload's
own path list from the workflow and refuses such entries by name before the
upload runs, so the mode bits decide, not the uid that runs the check. It also
refuses private key material anywhere in the collected tree: a test CA's key
is still a key, and evidence is published.
"""
import glob
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parent.parent
HEAD = 65536


def upload_paths():
    lines = (ROOT / '.github/workflows/ci.yml').read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip() == 'name: linux-evidence':
            break
    else:
        raise SystemExit('FAIL evidence-modes: no linux-evidence upload step in ci.yml')
    j = i + 1
    while j < len(lines) and lines[j].strip() != 'path: |':
        j += 1
    if j == len(lines):
        raise SystemExit('FAIL evidence-modes: the linux-evidence step lists no path block')
    indent = len(lines[j]) - len(lines[j].lstrip())
    paths = []
    for line in lines[j + 1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        paths.append(line.strip())
    if not paths:
        raise SystemExit('FAIL evidence-modes: the linux-evidence path block is empty')
    return paths


def main():
    patterns = upload_paths()
    unreadable, keys = [], []
    files = dirs = 0
    seen = set()
    for pattern in patterns:
        for match in sorted(glob.glob(str(ROOT / pattern))):
            walk = [Path(match)]
            if Path(match).is_dir() and not Path(match).is_symlink():
                walk += sorted(Path(match).rglob('*'))
            for path in walk:
                if path in seen:
                    continue
                seen.add(path)
                info = path.lstat()
                relative = path.relative_to(ROOT).as_posix()
                if stat.S_ISLNK(info.st_mode):
                    continue
                if stat.S_ISDIR(info.st_mode):
                    dirs += 1
                    if info.st_mode & (stat.S_IROTH | stat.S_IXOTH) != (stat.S_IROTH | stat.S_IXOTH):
                        unreadable.append((relative + '/', info.st_mode))
                    continue
                files += 1
                if not info.st_mode & stat.S_IROTH:
                    unreadable.append((relative, info.st_mode))
                try:
                    with open(path, 'rb') as handle:
                        head = handle.read(HEAD)
                except OSError:
                    head = b''
                if b'-----BEGIN' in head and b'PRIVATE KEY-----' in head:
                    keys.append(relative)
    for relative, mode in unreadable:
        print('FAIL evidence-unreadable %s mode=%04o' % (relative, stat.S_IMODE(mode)), flush=True)
    for relative in keys:
        print('FAIL evidence-private-key %s' % relative, flush=True)
    if unreadable or keys:
        raise SystemExit('FAIL evidence-modes: %d unreadable, %d private keys in the upload' % (len(unreadable), len(keys)))
    print('PASS evidence-modes: %d files and %d directories under %d upload paths, all readable by others, no private keys'
          % (files, dirs, len(patterns)), flush=True)


if __name__ == '__main__':
    main()
