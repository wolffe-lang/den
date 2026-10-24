"""Focused flag/ignore black-box measurements to resolve implementation questions."""
import json,os,pathlib,shutil,subprocess,runpy
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT']
P=runpy.run_path(str(R/'tools/index-proof.py'))
base=R/'target/vc03-behavior'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def git(repo,*args):
 p=subprocess.run([G,*args],cwd=repo,capture_output=True)
 row=dict(repo=repo.name,args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex())
 rows.append(row);return row

def entry(repo):
 raw=(repo/'.git/index').read_bytes();e=P['entries'](raw)[0]
 return dict(raw_hex=raw.hex(),flags=int.from_bytes(raw[e['offset']+60:e['offset']+62],'big'),extended=e['extended'],oid=raw[e['offset']+40:e['offset']+60].hex())
for flag in ('assume-unchanged','skip-worktree'):
 repo=base/flag;repo.mkdir();git(repo,'init','-q')
 (repo/'file').write_bytes(b'old\n');git(repo,'add','file');git(repo,'commit','-qm','root')
 git(repo,'update-index','--'+flag,'file');before=entry(repo)
 (repo/'file').write_bytes(b'changed\n')
 added=git(repo,'add','file');after=entry(repo)
 git(repo,'status','--porcelain')
 rows.append(dict(repo=flag,before=before,after=after))
 print(flag,added,'entry unchanged',before==after)
repo=base/'ignore';repo.mkdir();git(repo,'init','-q');(repo/'file').write_bytes(b'x')
(repo/'a/d/e').mkdir(parents=True);(repo/'a/file').write_bytes(b'x');(repo/'a/d/e/file').write_bytes(b'x')
for pattern in (b'!file\n',b'a/***/file\n',b'file\0junk\n!file\n',b'\0file\nfile\n',b'\xef\xbb\xbffile\n'):
 (repo/'.gitignore').write_bytes(pattern)
 for verbose in (False,True):
  for path in ('file','a/file','a/d/e/file'):
   args=['check-ignore','--no-index']+(['-v'] if verbose else [])+[path]
   row=git(repo,*args);row['pattern_hex']=pattern.hex()
   print(pattern,args,row['status'],bytes.fromhex(row['stdout']),bytes.fromhex(row['stderr']))
(R/'target/vc03-behavior.json').write_text(json.dumps(rows,indent=2)+'\n')
