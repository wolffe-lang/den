"""Pinned black-box cache, detached state and rename similarity witnesses."""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT']
base=R/'target/vc03-worktree-measure'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def git(repo,*args):
 p=subprocess.run([G,*args],cwd=repo,capture_output=True)
 row=dict(repo=repo.name,args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex());rows.append(row)
 assert p.returncode==0,row
 return p.stdout

def fresh(name,data=b'file\n'):
 p=base/name;p.mkdir();git(p,'init','-q');(p/'file').write_bytes(data);git(p,'add','file');git(p,'commit','-qm','root');return p

def cache(repo):
 raw=(repo/'.git/index').read_bytes();return raw[raw.find(b'TREE'):-20].hex()
repo=fresh('cache')
for label,args in [('before',None),('add-same',['add','file']),('chmod-noop',['add','--chmod=-x','file']),('write-tree',['write-tree']),('add-ctime-change',['add','file'])]:
 if label=='add-ctime-change':
  st=(repo/'file').stat();os.utime(repo/'file',ns=(st.st_atime_ns,st.st_mtime_ns))
 if args:git(repo,*args)
 rows.append(dict(repo='cache',label=label,cache=cache(repo),index_hex=(repo/'.git/index').read_bytes().hex()))
 print(label,cache(repo))
repo=fresh('detached')
git(repo,'checkout','--detach','HEAD');print('checkout-head',git(repo,'status').decode())
git(repo,'commit','--allow-empty','-qm','child');print('after-commit',git(repo,'status').decode())
git(repo,'tag','anchor');git(repo,'checkout','--detach','anchor');print('at-tag',git(repo,'status').decode())
repo=fresh('manual');(repo/'.git/HEAD').write_bytes(git(repo,'rev-parse','HEAD'));print('manual',git(repo,'status').decode())
# One source/one destination avoids matching tie ambiguity while deriving score.
pairs=[('two-of-three',b'a\nb\nc\n',b'a\nb\nX\n'),('reorder',b'a\nb\nc\n',b'c\na\nb\n'),
 ('half',b'a'*63+b'\n'+b'b'*63+b'\n',b'a'*63+b'\n'+b'c'*63+b'\n'),
 ('long-half',b'a'*64+b'b'*64,b'a'*64+b'c'*64),('long-shift',b'a'*64+b'b'*64,b'x'+b'a'*64+b'b'*63),
 ('crlf',b'a\r\nb\r\nc\r\n',b'a\nb\nc\n'),('one-line',b'abcdef\n',b'abcdeg\n'),
 ('binary-half',b'\0'+b'a'*63+b'b'*64,b'\0'+b'a'*63+b'c'*64),
 ('duplicate',b'a\na\nb\n',b'a\nb\nb\n'),('grow',b'a\nb\n',b'a\nb\nc\nd\n')]
for name,old,new in pairs:
 repo=fresh('rename-'+name,old);(repo/'file').unlink();(repo/'moved').write_bytes(new);git(repo,'add','-A')
 status=git(repo,'status','--porcelain');summary=git(repo,'diff','--cached','--summary','--find-renames=1%')
 rows.append(dict(repo=repo.name,old_hex=old.hex(),new_hex=new.hex()))
 print(name,status.decode().strip(),summary.decode().strip())
(R/'target/vc03-worktree-measure.json').write_text(json.dumps(rows,indent=2)+'\n')
