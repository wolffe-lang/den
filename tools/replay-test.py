"""vc08 independent replay fixtures. Complete state at every process boundary.
Reference: Git 2.56.0 git-cherry-pick/rebase, Description and Sequencer Options.
No implementation source; the pinned executable constructs every expected state.
"""
import argparse, json, os, pathlib, runpy, shutil, subprocess
R = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--tier', default='native')
ap.add_argument('--measure', action='store_true')
ap.add_argument('--filter', default='')
a = ap.parse_args()
G = os.environ['DEN_GIT']; D = str(R / f'target/{a.tier}/den')
O = runpy.run_path(str(R / 'tools/oracle.py'))
mode = a.tier + ('-packed' if os.environ.get('DEN_PACKED_FIXTURES') == '1' else '')
pack_fixture = runpy.run_path(str(R / 'tools/packed-fixture.py'))['pack_fixture']
base = R / f'target/replay-{mode}'
base.mkdir(parents=True, exist_ok=True)
def git(repo, *args, **kw):
    p = subprocess.run([G, *args], cwd=repo, capture_output=True, **kw)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout.decode().strip()
def seed(repo, kind):
    repo.mkdir(); git(repo, 'init', '-q')
    baseline=b'first\nmiddle\nlast\n'
    if kind=='repeated': baseline=b'same\nmiddle\nsame\n'
    if kind=='binary': baseline=b'first\0\nmiddle\nlast\n'
    (repo/'a').write_bytes(baseline); (repo/'keep').write_text('keep\n')
    git(repo, 'add', '.'); git(repo, 'commit', '-qm', 'base')
    root = git(repo, 'rev-parse', 'HEAD'); git(repo, 'branch', 'base')
    git(repo, 'switch', '-qc', 'topic')
    (repo/'a').write_bytes(b'theirs\0\nmiddle\nlast\n' if kind=='binary' else b'theirs\nmiddle\nsame\n' if kind=='repeated' else b'theirs\nmiddle\nlast\n')
    env = dict(os.environ, GIT_AUTHOR_NAME='Original Author', GIT_AUTHOR_EMAIL='original@example.invalid', GIT_AUTHOR_DATE='1600000000 +0530')
    git(repo, 'commit', '-qam', 'first pick\n\nbody', env=env)
    first = git(repo, 'rev-parse', 'HEAD'); git(repo, 'tag', 'first', first)
    if kind=='second-conflict':
        (repo/'a').write_text('theirs\nmiddle\nsecond\n'); git(repo,'add','a')
    else:
        (repo/'second').write_text('second\n'); git(repo, 'add', 'second')
    git(repo, 'commit', '-qm', 'second pick', env=env)
    second = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'commit', '--allow-empty', '-qm', 'empty pick', env=env)
    empty = git(repo, 'rev-parse', 'HEAD'); git(repo, 'tag', 'empty', empty)
    git(repo, 'switch', '-q', 'main')
    if kind in ('conflict', 'clean', 'second-conflict','binary','repeated'):
        ours=b'ours\nmiddle\nlast\n' if kind=='conflict' else b'first\nmiddle\nours\n'
        if kind=='repeated': ours=b'same\nmiddle\nours\n'
        if kind=='binary': ours=b'ours\0\nmiddle\nlast\n'
        (repo/'a').write_bytes(ours)
        git(repo, 'commit', '-qam', 'ours')
    if kind == 'redundant': git(repo, 'cherry-pick', first)
    git(repo,'branch','source',first)
    ours=git(repo,'rev-parse','HEAD')
    return dict(root=root, first=first, second=second, empty=empty, ours=ours, prefix=first[:9])
CASES=[]
def case(name, kind, setup, steps): CASES.append((name,kind,setup,steps))
for kind in ('ff','clean','conflict','redundant'):
    case('pick-'+kind,kind,'',[['cherry-pick','first']])
    case('sequence-'+kind,kind,'',[['cherry-pick','@first','@second']])
for flag in ('','--allow-empty','--keep-redundant-commits','--empty=drop','--empty=keep'):
    for kind,target in (('ff','empty'),('redundant','first')):
        case('empty-'+kind+'-'+flag,kind,'',[['cherry-pick',*([flag] if flag else []),target]])
for setup in ('packed','detached','dirty','dirty-keep','staged','untracked','index.lock','HEAD.lock','refs/heads/main.lock','CHERRY_PICK_HEAD.lock','AUTO_MERGE.lock'):
    case('pick-setup-'+setup,'clean',setup,[['cherry-pick','first']])
for flag in ('--allow-empty','--keep-redundant-commits','--empty=drop'):
    case('sequence-options-'+flag,'conflict','',[['cherry-pick',flag,'@first','@second'],['cherry-pick','--skip']])
for style in ('diff3','zdiff3'):
    case('pick-style-'+style,'conflict',style,[['cherry-pick','first']])
for sequence in (False,True):
    for action in ('continue','skip','abort'):
        steps=[['cherry-pick','@first',*(['@second'] if sequence else [])]]
        if action=='continue': steps += [['@write','a','resolved\n'],['add','a']]
        steps += [['cherry-pick','--'+action]]
        case('pick-'+('sequence-' if sequence else '')+action,'conflict','',steps)
for kind in ('ff','clean','conflict'):
    for onto in (False,True):
        args=['rebase',*(['--onto','main','base'] if onto else ['main'])]
        case('rebase-'+kind+('-onto' if onto else ''),kind,'topic',[args])
for action in ('continue','skip','abort'):
    steps=[['rebase','main']]
    if action=='continue': steps += [['@write','a','resolved\n'],['add','a']]
    steps += [['rebase','--'+action]]
    case('rebase-'+action,'conflict','topic',steps)
case('rebase-continue-committed','conflict','topic',[
    ['rebase','main'],['@write','a','resolved\n'],['add','a'],
    ['commit','--no-edit','--cleanup=strip','--author','Original Author <original@example.invalid>','--date','1600000000 +0530','-F','.git/MERGE_MSG'],
    ['rebase','--continue']])
for setup in ('packed','dirty','staged','index.lock','HEAD.lock','ORIG_HEAD.lock','refs/heads/topic.lock'):
    case('rebase-setup-'+setup,'clean','topic:'+setup,[['rebase','main']])
for action in ('continue','skip','abort'):
    steps=[['cherry-pick','@first','@second']]
    if action=='continue': steps += [['@write','a','resolved\n'],['add','a']]
    steps += [['cherry-pick','--'+action]]
    case('sequence-second-'+action,'second-conflict','',steps)
for action in ('skip','abort'):
    case('rebase-second-'+action,'second-conflict','topic',[['rebase','main'],['rebase','--'+action]])
case('rebase-equivalent','clean','topic:equivalent',[['rebase','main']])
case('rebase-reapply','clean','topic:equivalent',[['rebase','--reapply-cherry-picks','main']])
case('rebase-reapply-simple','ff','topic:equivalent-simple',[['rebase','--reapply-cherry-picks','main']])
case('scope-repeat','repeated','',[['cherry-pick','first']])
case('scope-binary','binary','',[['cherry-pick','first']])
case('scope-delete','ff','delete',[['cherry-pick','first']])
case('scope-symlink','clean','symlink',[['cherry-pick','first']])
case('scope-rename','clean','topic:rename',[['rebase','--onto','main','empty']])
case('rebase-detached','clean','topic:detached',[['rebase','main']])
case('rebase-noop','clean','topic',[['rebase','HEAD']])
for operand in ('source','refs/heads/source','refs/tags/first','@first','@prefix'):
    case('pick-name-'+operand,'clean','',[['cherry-pick',operand]])
for operand in ('refs/heads/main','@ours'):
    case('rebase-name-'+operand,'clean','topic',[['rebase',operand]])
case('pick-orig-head','clean','orig-head',[['cherry-pick','ORIG_HEAD']])
case('scope-config-rebase','clean','topic:config:rebase.autostash=true',[['rebase','main']])
case('scope-config-pick','clean','config:commit.cleanup=verbatim',[['cherry-pick','first']])
case('scope-moved-pick','conflict','',[
    ['cherry-pick','@first','@second'],['@writeid','.git/refs/heads/main','@root'],['cherry-pick','--abort']])
case('scope-moved-branch','conflict','topic',[
    ['rebase','main'],['@writeid','.git/refs/heads/topic','@root'],['rebase','--abort']])
case('scope-foreign-state','conflict','topic',[
    ['rebase','main'],['@write','.git/rebase-merge/foreign','leave intact\n'],['rebase','--abort']])
for cmd in ('cherry-pick','rebase'):
    for action in ('skip','abort'):
        initial=[cmd,'@first','@second'] if cmd=='cherry-pick' else [cmd,'main']
        case(cmd+'-dirty-'+action,'conflict','topic' if cmd=='rebase' else '',[
            initial,['@write','keep','local during operation\n'],[cmd,'--'+action]])
for cmd in ('cherry-pick','rebase'):
    initial=[cmd,'@first','@second'] if cmd=='cherry-pick' else [cmd,'main']
    setup='topic' if cmd=='rebase' else ''
    case(cmd+'-unresolved-continue','conflict',setup,[initial,[cmd,'--continue']])
    for action in ('skip','abort'):
        for lock in ('index.lock','HEAD.lock'):
            case(cmd+'-'+action+'-'+lock,'conflict',setup,[initial,['@write','.git/'+lock,'foreign lock\n'],[cmd,'--'+action]])
for cmd,flag,operand in [('rebase','-i','main'),('rebase','--apply','main'),('rebase','--rebase-merges','main'),('cherry-pick','-n','first')]:
    case('scope-'+cmd+'-'+flag,'clean','topic' if cmd=='rebase' else '',[[cmd,flag,operand]])
for cmd in ('cherry-pick','rebase'):
    for action in ('continue','skip','abort'):
        case(cmd+'-absent-'+action,'ff','',[[cmd,'--'+action]])
rows=[]
for n,(name,kind,setup,steps) in enumerate(CASES):
    if a.filter not in name: continue
    root=base/str(n)
    if root.exists(): shutil.rmtree(root)
    root.mkdir(); fixture=root/'fixture'; ids=seed(fixture,kind)
    if setup.startswith('topic'):
        git(fixture,'switch','-q','topic'); setup=setup.removeprefix('topic').removeprefix(':')
    if setup=='delete': git(fixture,'rm','a'); git(fixture,'commit','-qm','delete')
    elif setup=='symlink':
        (fixture/'link').symlink_to('a'); git(fixture,'add','link'); git(fixture,'commit','-qm','link')
    elif setup=='rename': git(fixture,'mv','keep','moved'); git(fixture,'commit','-qm','rename')
    elif setup=='orig-head': (fixture/'.git/ORIG_HEAD').write_text(ids['first']+'\n')
    elif setup.startswith('config:'):
        key,value=setup.removeprefix('config:').split('=',1); git(fixture,'config',key,value)
    elif setup=='equivalent-simple':
        git(fixture,'switch','-q','main')
        git(fixture,'cherry-pick','first',env=dict(os.environ,GIT_COMMITTER_DATE='1700000001 +0000'))
        git(fixture,'switch','-q','topic')
    elif setup=='equivalent':
        git(fixture,'switch','-q','main'); git(fixture,'cherry-pick','first'); git(fixture,'switch','-q','topic')
    elif setup=='packed': git(fixture,'pack-refs','--all')
    elif setup=='detached': git(fixture,'switch','--detach','-q','HEAD')
    elif setup in ('dirty','dirty-keep','staged'):
        path='keep' if setup=='dirty-keep' else 'a'; (fixture/path).write_text('local\n')
        if setup=='staged': git(fixture,'add',path)
    elif setup=='untracked': (fixture/'second').write_text('untracked\n'); steps=[['cherry-pick','@second']]
    elif setup in ('diff3','zdiff3'): git(fixture,'config','merge.conflictStyle',setup)
    elif setup: (fixture/'.git'/setup).write_bytes(b'foreign lock\n')
    steps=[[ids[x[1:]] if x.startswith('@') and x[1:] in ids else x for x in step] for step in steps]
    if mode.endswith('-packed'): pack_fixture(G, fixture)
    repo=root/'repo'
    def execute(exe):
        if repo.exists(): shutil.rmtree(repo)
        shutil.copytree(fixture,repo,symlinks=True)
        out=[]; before=[]
        for step in steps:
            if step[0]=='@write': (repo/step[1]).write_text(step[2]); continue
            if step[0]=='@writeid': (repo/step[1]).write_text(step[2]+'\n'); continue
            before.append((O['snapshot'](repo),O['worktree_snapshot'](repo)))
            out.append(O['capture']([exe,*step],repo,index_proof=True))
        return out,before
    expected,_=execute(G)
    row=dict(name=name,kind=kind,setup=setup,steps=steps,git=expected)
    if not a.measure:
        actual,before=execute(D); row['den']=actual
        refusal=None
        if name.startswith(('scope-rebase-','scope-cherry-pick-')):
            refusal=(0,steps[0][0]+' '+steps[0][1])
        inherited={'scope-repeat':'merge repeated-line alignment','scope-binary':'merge binary conflict','scope-delete':'merge modify/delete conflict','scope-symlink':'merge nonregular tree entry','scope-rename':'merge rename topology'}
        if name in inherited: refusal=(0,inherited[name])
        if name=='scope-config-rebase': refusal=(0,'replay configuration rebase.autostash')
        if name=='scope-config-pick': refusal=(0,'replay configuration commit.cleanup')
        if name=='scope-moved-pick': refusal=(1,'cherry-pick abort moved HEAD')
        if name=='scope-moved-branch': refusal=(1,'rebase changed original branch')
        if name=='scope-foreign-state': refusal=(1,'replay state entry rebase-merge/foreign')
        if name=='pick-setup-AUTO_MERGE.lock': refusal=(0,'replay AUTO_MERGE lock transient stat')
        if name in ('cherry-pick-dirty-skip','cherry-pick-dirty-abort'): refusal=(1,'cherry-pick dirty recovery transient stat')
        if name=='rebase-reapply': refusal=(0,'merge multi-hunk alignment')
        if name=='rebase-equivalent': refusal=(0,'rebase possible upstream patch equivalence; use --reapply-cherry-picks')
        if name=='rebase-continue': refusal=(len(actual)-1,'rebase continuation editor execution')
        checks=[]
        for i,(e,d) in enumerate(zip(expected,actual)):
            if refusal and i==refusal[0]:
                good=(d['status']==2 and d['stdout']=='' and bytes.fromhex(d['stderr'])==f'den: not yet implemented: {refusal[1]}\n'.encode()
                      and d['repository']==before[i][0] and d['worktree']==before[i][1])
                row['reason']=refusal[1]
            else: good=O['equivalent'](e,d,'index-stat-proven')
            checks.append(good)
        row['verified']=len(expected)==len(actual) and all(checks)
        row['disposition']='named-not-yet' if refusal else 'parity'
        row['equal']=row['verified'] and not refusal
        print(name,('NAMED' if refusal else 'PASS') if row['verified'] else 'FAIL',flush=True)
    else:
        print('\nCASE',name,flush=True)
        for step,result in zip([s for s in steps if not s[0].startswith('@')],expected):
            print(step,'status',result['status'],'stdout',bytes.fromhex(result['stdout']),'stderr',bytes.fromhex(result['stderr']),flush=True)
            for key,value in result['repository'].items():
                if key in ('HEAD','ORIG_HEAD','CHERRY_PICK_HEAD','REBASE_HEAD','MERGE_MSG','AUTO_MERGE','COMMIT_EDITMSG') or key.startswith(('sequencer/','rebase-merge/','rebase-apply/','logs/')):
                    print(key,value,flush=True)
    rows.append(row)
assert rows, 'empty selection'
path=R/f'target/replay-{"measure" if a.measure else mode}.json'
path.write_text(json.dumps(rows,indent=2)+'\n')
if not a.measure:
    failures=sum(not r['verified'] for r in rows)
    parity=[r for r in rows if r['disposition']=='parity']
    print(f'replay: {sum(r["equal"] for r in parity)}/{len(parity)} exact; {len(rows)-len(parity)} named; {failures} failures')
    raise SystemExit(bool(failures))
