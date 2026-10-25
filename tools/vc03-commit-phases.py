"""Observe only lane-owned Git fixtures and a lane-owned failing editor.
No hook or editor implementation source is read; the tiny editor is test input.
"""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT']
base=R/'target/vc03-commit-phases'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def git(repo,*args,data=None,env=None):
 p=subprocess.run([G,*args],cwd=repo,input=data,env=env,capture_output=True)
 rows.append(dict(repo=repo.name,args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 return p
editor=base/'editor'
editor.write_text('''#!/bin/sh
if test -e .git/index.lock; then printf yes > "$DEN_PHASE_DIR/held"; cp .git/index.lock "$DEN_PHASE_DIR/during-lock"; else printf no > "$DEN_PHASE_DIR/held"; fi
if test -e .git/index; then cp .git/index "$DEN_PHASE_DIR/during-index"; fi
exit 1
''');editor.chmod(0o755)
for all_flag in (False,True):
 for message in ('editor','empty'):
  root=base/f'{"all" if all_flag else "normal"}-{message}';root.mkdir();repo=root/'repo'
  shutil.copytree(R/'target/corpus/two',repo,symlinks=True)
  (repo/'a.txt').write_bytes(b'new content\n')
  if not all_flag:assert git(repo,'add','a.txt').returncode==0
  before=(repo/'.git/index').read_bytes()
  options=['commit']+(['-a'] if all_flag else [])+([] if message=='editor' else ['-m',''])
  p=git(repo,*options,env=dict(os.environ,GIT_EDITOR=str(editor),DEN_PHASE_DIR=str(root)))
  after=(repo/'.git/index').read_bytes()
  record=dict(case=root.name,status=p.returncode,before_hex=before.hex(),after_hex=after.hex(),held=(root/'held').read_text() if (root/'held').exists() else None)
  for filename in ('during-lock','during-index'):
   record[filename]=None if not (root/filename).exists() else (root/filename).read_bytes().hex()
  rows.append(record);print(root.name,'status',p.returncode,'held',record['held'],'index_changed',before!=after)
# A merge whose tree differs from BOTH parents discriminates combined/no summary.
repo=base/'merge-both';repo.mkdir();git(repo,'init','-q')
commits=[]
for content in (b'A\n',b'B\n',b'C\n'):
 blob=git(repo,'hash-object','-w','--stdin',data=content).stdout.strip().decode()
 tree=git(repo,'mktree',data=f'100644 blob {blob}\tfile\n'.encode()).stdout.strip().decode()
 parents=[] if not commits else ['-p',commits[0]] if len(commits)==1 else ['-p',commits[0],'-p',commits[1]]
 commits.append(git(repo,'commit-tree',tree,*parents,'-m','merge' if len(commits)==2 else 'parent').stdout.strip().decode())
git(repo,'update-ref','refs/heads/main',commits[-1]);git(repo,'read-tree','--reset',commits[-1]);git(repo,'checkout','--','file')
p=git(repo,'commit','--amend','-m','amended merge');print('merge differs both',p.returncode,repr(p.stdout),repr(p.stderr))
(R/'target/vc03-commit-phases.json').write_text(json.dumps(rows,indent=2)+'\n')
