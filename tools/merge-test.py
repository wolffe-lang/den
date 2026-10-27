"""Independent merge/revert fixtures; complete command/state comparison."""
import argparse, json, os, pathlib, runpy, shutil, subprocess
R = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument('--tier', default='native'); ap.add_argument('--measure', action='store_true'); a = ap.parse_args()
G = os.environ['DEN_GIT']; D = str(R / f'target/{a.tier}/den')
O = runpy.run_path(str(R / 'tools/oracle.py'))
base = R / f'target/merge-{a.tier}'
if base.exists(): shutil.rmtree(base)
base.mkdir(parents=True)
def run(repo, *args):
    p = subprocess.run([G, *args], cwd=repo, capture_output=True)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout.decode().strip()
def seed(kind, repo):
    repo.mkdir(); run(repo, 'init', '-q')
    (repo/'a').write_bytes(b'first\nmiddle\nlast\n'); (repo/'keep').write_bytes(b'keep\n')
    run(repo, 'add', '.'); run(repo, 'commit', '-qm', 'base')
    first = run(repo, 'rev-parse', 'HEAD'); run(repo, 'branch', 'topic')
    if kind not in ('ff', 'uptodate'):
        (repo/'a').write_bytes(b'ours\nmiddle\nlast\n')
        run(repo, 'commit', '-qam', 'ours')
    ours = run(repo, 'rev-parse', 'HEAD')
    run(repo, 'switch', '-q', 'topic')
    if kind != 'uptodate':
        (repo/'a').write_bytes(b'theirs\nmiddle\nlast\n' if kind == 'conflict' else b'first\nmiddle\ntheirs\n')
        run(repo, 'commit', '-qam', 'theirs')
    theirs = run(repo, 'rev-parse', 'HEAD'); run(repo, 'switch', '-q', 'main')
    return first, ours, theirs
cases=[]
for kind in ('uptodate','ff','clean','conflict'):
    for flags in ([], ['--no-ff'], ['--squash'], ['--no-commit'], ['--ff-only']):
        cases.append((kind, ['merge','--no-edit',*flags,'topic'], ''))
for kind in ('ff','clean','conflict'):
    for setup in ('packed','detached','dirty','dirty-keep','staged','untracked','index.lock','HEAD.lock','ORIG_HEAD.lock','AUTO_MERGE.lock','refs/heads/main.lock'):
        cases.append((kind, ['merge','--no-edit','topic'], setup))
for flags in ([], ['--no-commit'], ['--no-ff','-m','custom message']):
    cases.append(('clean',['merge','--no-edit',*flags,'topic'], ''))
for setup in ('','packed','detached','index.lock','HEAD.lock','dirty','staged'):
    cases.append(('ff', ['revert','--no-edit','topic'], setup))
for kind in ('clean','conflict'):
    cases.append((kind, ['merge','--abort'], 'abort'))
rows=[]
for n,(kind,args,setup) in enumerate(cases):
    root=base/str(n); root.mkdir(); fixture=root/'fixture'; first,ours,theirs=seed(kind,fixture)
    if setup=='packed': run(fixture,'pack-refs','--all')
    elif setup=='detached': run(fixture,'switch','--detach','-q',ours)
    elif setup in ('dirty','staged','dirty-keep'):
        (fixture/('keep' if setup=='dirty-keep' else 'a')).write_bytes(b'local\n')
        if setup=='staged': run(fixture,'add','a')
    elif setup=='untracked':
        run(fixture,'switch','-q','topic'); (fixture/'new').write_bytes(b'topic\n'); run(fixture,'add','new'); run(fixture,'commit','-qm','new'); run(fixture,'switch','-q','main'); (fixture/'new').write_bytes(b'local\n')
    elif setup=='abort': subprocess.run([G,'merge','--no-edit','--no-commit','topic'],cwd=fixture,capture_output=True)
    elif setup: (fixture/'.git'/setup).write_bytes(b'foreign lock\n')
    repo=root/'repo'
    def restore():
        if repo.exists(): shutil.rmtree(repo)
        shutil.copytree(fixture,repo,symlinks=True)
    restore(); expected=O['capture']([G,*args],repo,index_proof=True)
    if a.measure:
        row=dict(kind=kind,args=args,setup=setup,git=expected)
        print(n,kind,setup,args,expected['status'],bytes.fromhex(expected['stdout']),bytes.fromhex(expected['stderr']),flush=True)
        for key,value in expected['repository'].items():
            if key in ('MERGE_HEAD','MERGE_MSG','MERGE_MODE','ORIG_HEAD','AUTO_MERGE','SQUASH_MSG','REVERT_HEAD','COMMIT_EDITMSG') or key.startswith('logs/'):
                print(key,value,flush=True)
    else:
        restore(); actual=O['capture']([D,*args],repo,index_proof=True)
        good=O['equivalent'](expected,actual,'index-stat-proven')
        row=dict(kind=kind,args=args,setup=setup,git=expected,den=actual,equal=good)
        print(n,'parity' if good else 'FAIL',kind,setup,args,flush=True)
        if not good:
            print('git',expected['status'],bytes.fromhex(expected['stdout']),bytes.fromhex(expected['stderr']))
            print('den',actual['status'],bytes.fromhex(actual['stdout']),bytes.fromhex(actual['stderr']))
            print('state', [k for k in expected['repository'].keys()|actual['repository'].keys() if expected['repository'].get(k)!=actual['repository'].get(k)])
    rows.append(row)
output=R/f'target/merge-{"measure" if a.measure else a.tier}.json'; output.write_text(json.dumps(rows,indent=2)+'\n')
if not a.measure:
    failed=sum(not x['equal'] for x in rows); print(f'merge: {len(rows)-failed}/{len(rows)} exact; {failed} mismatches')
    raise SystemExit(bool(failed))
