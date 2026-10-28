import argparse,base64,hashlib,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
a=argparse.ArgumentParser();a.add_argument('--tier',default='native');args=a.parse_args()
D=R/'target'/args.tier/'den'; root=R/'target'/('pack-write-'+args.tier)
rows=[]; contents={}; states={}; refused=[]
def snapshot(p):
 out={}
 for f in sorted(p.rglob('*')):
  data=os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
  digest=hashlib.sha256(data).hexdigest();contents[digest]=base64.b64encode(data).decode()
  out[str(f.relative_to(p))]={'mode':f.lstat().st_mode,'content':digest}
 key=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest();states[key]=out;return key
def call(tool,p,cmd):
 q=subprocess.run([str(tool)]+cmd,cwd=p,capture_output=True)
 return {'stdout':q.stdout.hex(),'stderr':q.stderr.hex(),'status':q.returncode,'state':snapshot(p)}
try:
 for p in sorted(root.iterdir()):
  if not (p/'.git').is_dir():continue
  before=snapshot(p)
  commands=[['count-objects'],['count-objects','-v'],['fsck','--full','--no-dangling']]
  if not p.name.startswith('similar'):commands.append(['fsck','--full'])
  for idx in (p/'.git/objects/pack').glob('*.idx'):
   commands.extend([['verify-pack',str(idx)],['verify-pack','-v',str(idx)]])
  for cmd in commands:
   g=call(G,p,cmd);d=call(D,p,cmd)
   if cmd[0]=='fsck' and bytes.fromhex(g['stdout']).count(b'dangling ')>1:
    refused.append({'fixture':p.name,'args':cmd,'git':g,'den':d})
    assert d['status']==2 and b'fsck multiple dangling object order' in bytes.fromhex(d['stderr']) and d['state']==before
    continue
   rows.append({'fixture':p.name,'args':cmd,'git':g,'den':d})
   assert g==d,(p.name,cmd,g,d)
   assert d['state']==before,(p.name,cmd,'mutation')
  print('PACK COMMAND',p.name,len(commands),flush=True)
 p=root/'linear-ofs'
 for cmd,feature in [(['pack-objects','--stdout'],'pack-objects --stdout'),(['pack-objects','--thin'],'pack-objects --thin'),(['pack-objects','--window=11'],'pack-objects --window=11'),(['pack-objects','--depth=51'],'pack-objects --depth=51'),(['pack-objects','--cruft'],'pack-objects --cruft'),(['verify-pack','-s'],'verify-pack -s'),(['fsck','--strict'],'fsck --strict')]:
  before=snapshot(p);d=call(D,p,cmd);refused.append({'args':cmd,'den':d})
  assert d['status']==2 and feature.encode() in bytes.fromhex(d['stderr']) and before==d['state'],(cmd,d)
finally:
 (R/'target'/('pack-command-'+args.tier+'.json')).write_text(json.dumps({'rows':rows,'refusals':refused,'states':states,'contents':contents}))
print('PACK COMMAND COMPLETE',len(rows),'exact',len(refused),'named')
