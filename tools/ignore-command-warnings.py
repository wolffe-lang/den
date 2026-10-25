"""Measure which porcelain operations load a symlink ignore source."""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT']
base=R/'target/ignore-command-warnings'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
commands=[['status'],['status','--untracked-files=no'],['status','--porcelain','--ignored'],['add','a.txt'],['add','-u'],['add','.'],['add','untracked'],['commit','-q','--allow-empty','-m','empty'],['commit','--allow-empty','-m','empty'],['commit','-m','nothing'],['commit','-a','-m','tracked']]
for i,args in enumerate(commands):
 repo=base/str(i);shutil.copytree(R/'target/corpus/two',repo,symlinks=True)
 (repo/'rules').write_bytes(b'*.tmp\n');(repo/'.gitignore').symlink_to('rules');(repo/'untracked').write_bytes(b'new\n')
 p=subprocess.run([G,*args],cwd=repo,capture_output=True)
 rows.append(dict(args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 print(args,p.returncode,repr(p.stderr))
(R/'target/ignore-command-warnings.json').write_text(json.dumps(rows,indent=2)+'\n')
