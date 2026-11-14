#!/usr/bin/env python3
"""A pull must not read unrelated untracked or ignored file bodies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--den')
    parser.add_argument('--filter',default='')
    parser.add_argument('--include-count',action='store_true')
    parser.add_argument('--merge',action='store_true')
    a=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=root/'target/runs/pull-scan'
    out.mkdir(parents=True,exist_ok=True)
    git=os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den=a.den or str(root/'target/native/den')
    def run(args,cwd):
        p=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True)
        assert p.returncode==0,(args,p.stdout,p.stderr)
        return p.stdout
    seed=out/'seed';origin=out/'origin';remote=out/'remote.git'
    for p in (seed,origin,remote):
        if p.exists():shutil.rmtree(p)
    run([git,'init','-q',origin],root)
    (origin/'a').write_text('before\n');(origin/'.gitignore').write_text('')
    run([git,'add','.'],origin);run([git,'commit','-qm','base'],origin)
    run([git,'clone','-q','--bare',origin,remote],root)
    run([git,'clone','-q',remote.as_uri(),seed],root)
    run([git,'config','gc.auto','0'],seed)
    if a.merge:
        (seed/'b').write_text('local independent change\n')
        run([git,'add','b'],seed);run([git,'commit','-qm','local'],seed)
        run([git,'config','pull.rebase','false'],seed)
    (origin/'a').write_text('after\n')
    run([git,'commit','-qam','next'],origin)
    run([git,'push','-q',remote.as_uri(),'HEAD:refs/heads/main'],origin)
    expected_head=run([git,'rev-parse','HEAD'],origin).strip().decode()
    cases=['untracked-large','ignored-large','ignored-directory']
    if a.include_count:cases.append('untracked-count')
    rows=[]
    for case in cases:
        if a.filter not in case:continue
        results=[]
        for tool in (git,den):
            work=out/'work'
            if work.exists():shutil.rmtree(work)
            shutil.copytree(seed,work)
            large=work/'build-output'
            if case=='ignored-directory':
                large=work/'build-tree'/'nested'/'output'
                large.parent.mkdir(parents=True)
                (work/'.gitignore').write_text('build-tree/\n')
            elif case=='ignored-large':(work/'.gitignore').write_text('build-output\n')
            if case=='untracked-count':
                directory=work/'untracked-tree';directory.mkdir()
                for i in range(1000001):
                    (directory/f'{i:07}').touch()
                    if i%100000==0:print(f'PREP count {i}',flush=True)
            else:
                with large.open('wb') as f:f.truncate(1500000000)
            start=time.monotonic()
            p=subprocess.run([tool,'pull','origin','main'],cwd=work,capture_output=True)
            head=run([git,'rev-parse','HEAD'],work).strip().decode()
            untouched=large.stat().st_size==1500000000 if case!='untracked-count' else len(list(directory.iterdir()))==1000001
            result=dict(status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex(),head=head,untouched=untouched,wall=time.monotonic()-start)
            results.append(result)
            print(json.dumps(dict(case=case,tool=Path(tool).name,**result)),flush=True)
        same=all(results[0][k]==results[1][k] for k in ('status','stdout','stderr','head','untouched')) and (a.merge or results[1]['head']==expected_head) and results[1]['untouched']
        print(('PASS ' if same else 'FAIL ')+'pull-scan-'+('merge-' if a.merge else 'ff-')+case,flush=True)
        rows.append(dict(case=case,pass_=same,results=results))
    assert rows,'empty selection'
    (out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    return int(any(not row['pass_'] for row in rows))

if __name__=='__main__':raise SystemExit(main())
