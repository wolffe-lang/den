"""Black-box history display witnesses; no implementation source inputs."""
import os,pathlib,subprocess,json
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT']; D=R/'target/history-measure'; D.mkdir(parents=True,exist_ok=True)
def g(*a,data=None):
 p=subprocess.run([G,*a],cwd=D,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert p.returncode==0,(a,p.stderr);return p.stdout
if not (D/'.git').exists(): g('init','-q')
tree=g('mktree',data=b'').strip()
def commit(msg,parents=(),date='1700000000 +0530'):
 raw=b'tree '+tree+b'\n'+b''.join(b'parent '+p+b'\n' for p in parents)+b'author A <a@b> '+date.encode()+b'\ncommitter C <c@d> 1700000000 +0000\n\n'+msg
 return g('hash-object','--literally','-t','commit','-w','--stdin',data=raw).strip()
rows=[]
for msg in (b'hello\n',b'hello',b'\n\n  hello  \nnext\t\n\nbody\n\n',b'',b'one\n\tindent\n',b'\xff\n',b'a\0b\n'):
 c=commit(msg);g('update-ref','refs/heads/main',c.decode())
 for a in (['log'],['log','--oneline'],['show'],['show','--stat'],['log','--date=iso-strict'],['log','--date=default-local']):
  rows.append({'message':msg.hex(),'args':a,'out':g(*a).hex()})
p=commit(b'parent\n');m=commit(b'merge\n',[p,commit(b'other\n')]);g('update-ref','refs/heads/main',m.decode())
for a in (['log'],['log','--oneline'],['log','-p'],['show'],['show','-s']): rows.append({'message':'merge','args':a,'out':g(*a).hex()})
(R/'target/history-measure.json').write_text(json.dumps(rows,indent=2))
for r in rows: print(r['message'],r['args'],repr(bytes.fromhex(r['out'])))
b=g('hash-object','-w','--stdin',data=b'blob\n').strip()
t=g('mktree',data=b'100644 blob '+b+b'\tspace name\n040000 tree '+tree+b'\tsubdir\n').strip()
tag=g('hash-object','-w','-t','tag','--stdin',data=b'object '+p+b'\ntype commit\ntag v1\ntagger A <a@b> 1700000000 +0530\n\ntag message\n\n').strip()
for obj in (t,tag):
 for extra in ([],['--oneline'],['-s'],['--date=iso']): print(obj.decode(),extra,repr(g('show',*extra,obj.decode())))
