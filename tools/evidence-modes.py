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
is still a key, and evidence is published. And it refuses a file or directory
name the upload cannot carry: upload-artifact rejects the whole artifact for a
name with a double quote, colon, less-than, greater-than, vertical bar,
asterisk, question mark, carriage return or line feed. A special file (a named
pipe, a socket or a device) is refused by name and never opened: opening a
named pipe that no process writes waits for a writer forever, which once held
this check until a record's cap.
"""
import glob
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parent.parent
HEAD = 65536
UNCARRIED = set('":<>|*?\r\n')
SPECIAL = ((stat.S_ISFIFO, 'fifo'), (stat.S_ISSOCK, 'socket'), (stat.S_ISCHR, 'character device'),
           (stat.S_ISBLK, 'block device'))


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
    unreadable, keys, names, specials = [], [], [], []
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
                if UNCARRIED & set(path.name):
                    names.append(relative)
                if stat.S_ISLNK(info.st_mode):
                    continue
                if stat.S_ISDIR(info.st_mode):
                    dirs += 1
                    if info.st_mode & (stat.S_IROTH | stat.S_IXOTH) != (stat.S_IROTH | stat.S_IXOTH):
                        unreadable.append((relative + '/', info.st_mode))
                    continue
                if not stat.S_ISREG(info.st_mode):
                    kind = next((word for test, word in SPECIAL if test(info.st_mode)), 'unknown')
                    specials.append((relative, kind))
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
    for relative in names:
        print('FAIL evidence-name %r' % relative, flush=True)
    for relative, kind in specials:
        print('FAIL evidence-special %s kind=%s' % (relative, kind), flush=True)
    if unreadable or keys or names or specials:
        raise SystemExit('FAIL evidence-modes: %d unreadable, %d private keys, %d names the upload cannot carry,'
                         ' %d special files' % (len(unreadable), len(keys), len(names), len(specials)))
    print('PASS evidence-modes: %d files and %d directories under %d upload paths, all readable by others, no private keys,'
          ' every name uploadable, no special files' % (files, dirs, len(patterns)), flush=True)


if __name__ == '__main__':
    main()
