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
for setup in ('','packed','detached','index.lock','HEAD.lock','dirty','staged'):
    cases.append(('clean', ['revert','--no-edit','HEAD'], setup))
for args in (['add','a'], ['commit','--no-edit','-m','resolved']):
    cases.append(('conflict',args,'resolve'))
for style in ('diff3','zdiff3'):
    cases.append(('conflict',['merge','--no-edit','topic'],style))
for kind in ('ff','clean','conflict'):
    for operand in ('refs/heads/topic','light','refs/tags/light','@oid','@short'):
        cases.append((kind,['merge','--no-edit',operand],''))
    cases.append((kind,['merge','topic'],''))
for setup in ('unborn','annotated','rename','crisscross'):
    cases.append(('clean',['merge','--no-edit','annotated' if setup=='annotated' else 'topic'],setup))
cases.append(('clean',['revert','--no-edit','HEAD'],'merge-head'))
cases.append(('clean',['revert','-m','1','HEAD'],'merge-head'))
for kind in ('uptodate','clean','conflict'):
    for args in (['revert','--no-edit','HEAD'],['revert','--no-edit','topic'],['revert','--no-commit','HEAD']):
        cases.append((kind,args,''))
for kind in ('ff','clean'):
    for setup in ('add-file','delete-file','mode-file'):
        cases.append((kind,['merge','--no-edit','topic'],setup))
cases.append(('conflict',['add','-u'],'resolve-delete'))
rows=[]
for n,(kind,args,setup) in enumerate(cases):
    root=base/str(n); root.mkdir(); fixture=root/'fixture'; first,ours,theirs=seed(kind,fixture)
    args=[x.replace('@oid',theirs).replace('@short',theirs[:9]) for x in args]
    run(fixture,'tag','light',theirs)
    if setup=='unborn':
        (fixture/'.git/refs/heads/main').unlink(); (fixture/'.git/index').unlink(); shutil.rmtree(fixture/'.git/logs')
        (fixture/'a').unlink(); (fixture/'keep').unlink()
    elif setup=='annotated': run(fixture,'tag','-am','annotation','annotated',theirs)
    elif setup=='rename':
        run(fixture,'switch','-q','topic'); run(fixture,'mv','a','renamed'); run(fixture,'commit','-qm','rename'); run(fixture,'switch','-q','main')
    elif setup=='crisscross':
        one=run(fixture,'commit-tree',run(fixture,'rev-parse',ours+'^{tree}'),'-p',ours,'-p',theirs,'-m','first merge')
        two=run(fixture,'commit-tree',run(fixture,'rev-parse',theirs+'^{tree}'),'-p',theirs,'-p',ours,'-m','second merge')
        run(fixture,'update-ref','refs/heads/main',one);run(fixture,'update-ref','refs/heads/topic',two)
        run(fixture,'reset','--hard','-q',one)
    elif setup=='merge-head': run(fixture,'merge','--no-edit','topic')
    elif setup in ('add-file','delete-file','mode-file'):
        run(fixture,'switch','-q','topic')
        if setup=='add-file':
            (fixture/'nested').mkdir();(fixture/'nested/new').write_bytes(b'new\n');run(fixture,'add','nested/new')
        elif setup=='delete-file': run(fixture,'rm','keep')
        else: (fixture/'keep').chmod(0o755);run(fixture,'add','keep')
        run(fixture,'commit','-qm',setup);run(fixture,'switch','-q','main')
    elif setup=='packed': run(fixture,'pack-refs','--all')
    elif setup=='detached': run(fixture,'switch','--detach','-q',ours)
    elif setup in ('dirty','staged','dirty-keep'):
        (fixture/('keep' if setup=='dirty-keep' else 'a')).write_bytes(b'local\n')
        if setup=='staged': run(fixture,'add','a')
    elif setup=='untracked':
        run(fixture,'switch','-q','topic'); (fixture/'new').write_bytes(b'topic\n'); run(fixture,'add','new'); run(fixture,'commit','-qm','new'); run(fixture,'switch','-q','main'); (fixture/'new').write_bytes(b'local\n')
    elif setup in ('abort','resolve','resolve-delete'):
        subprocess.run([G,'merge','--no-edit','--no-commit','topic'],cwd=fixture,capture_output=True)
        if setup=='resolve-delete': (fixture/'a').unlink()
        if setup=='resolve':
            (fixture/'a').write_bytes(b'resolved\n')
            if args[0]=='commit': run(fixture,'add','a')
    elif setup in ('diff3','zdiff3'): run(fixture,'config','merge.conflictStyle',setup)
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
        restore(); before=O['snapshot'](repo); before_work=O['worktree_snapshot'](repo)
        actual=O['capture']([D,*args],repo,index_proof=True)
        feature=None
        if args[0]=='merge' and kind in ('clean','conflict') and setup in ('dirty','dirty-keep','staged'):
            feature='merge dirty recursive recovery'
        if setup in ('unborn','annotated','rename','crisscross'):
            feature={'unborn':'merge unborn HEAD','annotated':'merge annotated tag message','rename':'merge rename topology','crisscross':'merge recursive criss-cross bases'}[setup]
        if args[:2]==['revert','-m']: feature='revert -m'
        if kind=='clean' and setup=='' and args==['revert','--no-edit','topic']: feature='merge multi-hunk alignment'
        if feature:
            assert actual['status']==2 and bytes.fromhex(actual['stderr'])==f'den: not yet implemented: {feature}\n'.encode() and actual['stdout']=='', actual
            assert actual['repository']==before and actual['worktree']==before_work
            rows.append(dict(kind=kind,args=args,setup=setup,git=expected,den=actual,disposition='named-not-yet',reason=feature))
            print(n,'named-not-yet',kind,setup,flush=True)
            continue
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
    exact=[x for x in rows if 'equal' in x]
    failed=sum(not x['equal'] for x in exact); print(f'merge: {len(exact)-failed}/{len(exact)} exact; {len(rows)-len(exact)} named not-yet; {failed} mismatches')
    raise SystemExit(bool(failed))
