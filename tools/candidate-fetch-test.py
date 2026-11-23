"""Candidate artifacts must be present and digest checked, never optional."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
fetch = ROOT / 'tools/fetch-candidate-wolf'
if not fetch.is_file():
    print('FAIL candidate-wolf-stage-present', flush=True)
    sys.exit(1)
with tempfile.TemporaryDirectory(prefix='candidate-fetch-test-', dir=ROOT / 'target') as scratch:
    work = Path(scratch)
    archive = work / 'wrong.tar.gz'
    archive.write_bytes(b'not the pinned archive')
    home = work / 'home'
    home.mkdir()
    env = dict(os.environ, HOME=str(home), SHELL='/bin/sh', DEN_CANDIDATE_ARCHIVE=str(archive),
               DEN_CANDIDATE_STAGE=str(work / 'stage'))
    q = subprocess.run([str(fetch)], cwd=ROOT, env=env, capture_output=True, text=True)
    ok = q.returncode != 0 and 'FAIL candidate-wolf-archive' in q.stdout and not (work / 'stage').exists()
    print(('PASS ' if ok else 'FAIL ') + 'candidate-wolf-stage-rejects-wrong-digest', flush=True)
    if not ok:
        print(q.stdout, q.stderr)
        sys.exit(1)
    env['DEN_CANDIDATE_ARCHIVE'] = str(work / 'absent')
    q = subprocess.run([str(fetch)], cwd=ROOT, env=env, capture_output=True, text=True)
    ok = q.returncode != 0 and 'FAIL candidate-wolf-archive' in q.stdout
    print(('PASS ' if ok else 'FAIL ') + 'candidate-wolf-stage-rejects-missing-archive', flush=True)
    sys.exit(not ok)
