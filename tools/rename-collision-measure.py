"""Independent oracle tests for information lost after a 64-bit fingerprint.

All fixtures and queries are retained. Equal-sized chunk sets are prefixed by
N-1 shared chunks: without another collision the score is just below 50%; a
single cross-set collision crosses 50%. Recursively partitioning both sets
isolates colliding chunks without seeing the oracle's hash or implementation.
"""
import argparse
import hashlib
import json
import os
import pathlib
import random
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--pairs', type=int, default=24)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    repo = args.output / 'repo'
    repo.mkdir()
    gitpath = os.environ['DEN_GIT']
    rng = random.Random(0x76633034)
    alphabet = [i for i in range(256) if i not in (10,13)]
    anchor = bytes(rng.choice(alphabet) for _ in range(63)) + b'\n'
    queries, collisions = [], []
    started = time.monotonic()

    def git(*args, data=None):
        p = subprocess.run([gitpath,*args],cwd=repo,input=data,capture_output=True,timeout=30)
        assert p.returncode == 0, (args,p.returncode,p.stdout,p.stderr)
        return p.stdout

    git('init','-q')
    def tree(data, path):
        oid = git('hash-object','-w','--stdin',data=data).strip()
        return git('mktree',data=b'100644 blob '+oid+b'\t'+path+b'\n').strip().decode()

    def test(a,b):
        assert len(a)==len(b)
        n=len(a)
        prefix=anchor*(n-1)
        old,new=prefix+b''.join(a),prefix+b''.join(b)
        ta,tb=tree(old,b'source'),tree(new,b'moved')
        result=git('diff','--raw','-z','--find-renames=50%',ta,tb)
        rename=any(part.startswith(b':') and part.split()[-1].startswith(b'R') for part in result.split(b'\0'))
        queries.append({'n':n,'old_tree':ta,'new_tree':tb,'raw_hex':result.hex(),'rename':rename})
        return rename

    def search(a,b):
        if len(collisions)>=args.pairs or not test(a,b):
            return
        if len(a)==1:
            assert a[0]!=b[0]
            collisions.append({'old_hex':a[0].hex(),'new_hex':b[0].hex()})
            print('isolated',len(collisions),'queries',len(queries),flush=True)
            return
        half=len(a)//2
        for aa in (a[:half],a[half:]):
            for bb in (b[:half],b[half:]):
                search(aa,bb)

    try:
        for round in range(16):
            if len(collisions)>=args.pairs:
                break
            if time.monotonic()-started>600:
                raise TimeoutError('ten-minute bound')
            a=[bytes(rng.choice(alphabet) for _ in range(64)) for _ in range(1024)]
            b=[bytes(rng.choice(alphabet) for _ in range(64)) for _ in range(1024)]
            (args.output/f'round-{round}.json').write_text(json.dumps({'a':[x.hex() for x in a],'b':[x.hex() for x in b]}))
            search(a,b)
            print('round',round,'collisions',len(collisions),'queries',len(queries),flush=True)
    finally:
        (args.output/'report.json').write_text(json.dumps({'oracle_sha256':hashlib.sha256(pathlib.Path(gitpath).read_bytes()).hexdigest(),
            'source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'anchor_hex':anchor.hex(),
            'queries':queries,'collisions':collisions,'elapsed_s':time.monotonic()-started},indent=2)+'\n')
    assert len(collisions)==args.pairs

if __name__=='__main__':
    main()
