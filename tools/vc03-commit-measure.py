"""Pinned date field bounds, attached HEAD lock behavior and empty merge amend."""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT']
base=R/'target/vc03-commit-measure'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def git(repo,*args,env=None,data=None):
 p=subprocess.run([G,*args],cwd=repo,env=env,input=data,capture_output=True)
 rows.append(dict(repo=repo.name,args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 return p
repo=base/'dates';repo.mkdir();assert git(repo,'init','-q').returncode==0
tree=git(repo,'mktree',data=b'').stdout.strip().decode()
for clock in ['24:01:00','25:00:00','99:00:00','100:00:00','22:61:00','22:99:00','22:100:00','22:13:61','22:13:99','22:13:100']:
 text='2005-04-07T'+clock+'Z'
 p=git(repo,'commit-tree',tree,'-m','date',env=dict(os.environ,GIT_AUTHOR_DATE=text))
 author=None
 if p.returncode==0:author=next(x for x in git(repo,'cat-file','commit',p.stdout.strip().decode()).stdout.splitlines() if x.startswith(b'author ')).decode()
 rows.append(dict(date=text,status=p.returncode,author=author));print(text,p.returncode,author)
for zone in ['+2400','+2460','+9999','+10039','+10000','+123456','+5','+005','+00:60','-0000','-2460']:
 text='@1 '+zone;p=git(repo,'commit-tree',tree,'-m','date',env=dict(os.environ,GIT_AUTHOR_DATE=text));author=None
 if p.returncode==0:author=next(x for x in git(repo,'cat-file','commit',p.stdout.strip().decode()).stdout.splitlines() if x.startswith(b'author ')).decode()
 rows.append(dict(date=text,status=p.returncode,author=author));print(text,p.returncode,author)
repo=base/'head-lock';repo.mkdir();git(repo,'init','-q');(repo/'file').write_bytes(b'a\n');git(repo,'add','file');git(repo,'commit','-qm','root')
old=git(repo,'rev-parse','HEAD').stdout.strip().decode();(repo/'file').write_bytes(b'b\n');git(repo,'add','file');(repo/'.git/HEAD.lock').write_bytes(b'foreign HEAD lock\n')
p=git(repo,'commit','-m','with HEAD lock');new=git(repo,'rev-parse','HEAD').stdout.strip().decode()
rows.append(dict(case='head-lock',old=old,new=new,status=p.returncode,lock_hex=(repo/'.git/HEAD.lock').read_bytes().hex()))
print('HEAD.lock commit',p.returncode,repr(p.stdout),repr(p.stderr),old,new)
repo=base/'merge-amend';repo.mkdir();git(repo,'init','-q');(repo/'file').write_bytes(b'a\n');git(repo,'add','file');git(repo,'commit','-qm','root')
first=git(repo,'rev-parse','HEAD').stdout.strip().decode();tree=git(repo,'write-tree').stdout.strip().decode()
second=git(repo,'commit-tree',tree,'-p',first,'-m','other').stdout.strip().decode()
merge=git(repo,'commit-tree',tree,'-p',first,'-p',second,'-m','merge').stdout.strip().decode();git(repo,'update-ref','refs/heads/main',merge)
for options in [['--no-edit'],['-m','amended merge']]:
 p=git(repo,'commit','--amend',*options);print('empty merge amend',options,p.returncode,repr(p.stdout),repr(p.stderr))
 rows.append(dict(case='merge-amend',status=p.returncode,parents=git(repo,'rev-list','--parents','-n','1','HEAD').stdout.decode()))
(R/'target/vc03-commit-measure.json').write_text(json.dumps(rows,indent=2)+'\n')
