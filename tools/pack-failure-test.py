import argparse,base64,hashlib,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
a=argparse.ArgumentParser();a.add_argument('--tier',default='native');args=a.parse_args()
D=R/'target'/args.tier/'den'; C=D.with_name('pack-write-client'); root=R/'target'/('pack-failure-'+args.tier)
if root.exists():shutil.rmtree(root)
root.mkdir();rows=[]
def state(p):
 return {str(f.relative_to(p)):{'mode':f.lstat().st_mode,'data':base64.b64encode(os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b'').decode()} for f in sorted(p.rglob('*'))}
def run(cmd,p,data=None):
 q=subprocess.run(list(map(str,cmd)),cwd=p,input=data,capture_output=True)
 row={'args':list(map(str,cmd)),'out':q.stdout.hex(),'err':q.stderr.hex(),'status':q.returncode,'state':state(p)};rows.append(row);return row
src=R/'target'/('pack-write-'+args.tier)/'corpus/two'
try:
 for failure in ['write','sync','pack-rename','idx-rename','corrupt-index','corrupt-pack','directory-sync','repeat']:
  p=root/failure;shutil.copytree(src,p,symlinks=True)
  ids=subprocess.check_output([G,'cat-file','--batch-all-objects','--batch-check=%(objectname)'],cwd=p); names=root/(failure+'.names');names.write_bytes(ids)
  before=state(p); r=run([C,p/'.git',names,'ofs',failure],p)
  if failure not in ['directory-sync','repeat']:
   assert r['status']==1 and r['state']==before,(failure,r)
  else:
   assert r['status']==(0 if failure=='repeat' else 1),(failure,r)
   idx=list((p/'.git/objects/pack').glob('*.idx'));assert len(idx)==1
   assert run([G,'verify-pack',idx[0]],p)['status']==0
   if failure=='repeat':
    second=run([C,p/'.git',names,'ofs'],p);assert second==r|{'args':second['args']},(r,second)
  print('PACK FAILURE',failure,flush=True)
 p=root/'cli';shutil.copytree(src,p,symlinks=True)
 ids=subprocess.check_output([G,'cat-file','--batch-all-objects','--batch-check=%(objectname)'],cwd=p)
 before=state(p); r=run([D,'pack-objects','-q','--delta-base-offset','.git/objects/pack/pack'],p,ids)
 assert r['status']==0,r
 assert all(r['state'].get(k)==v for k,v in before.items())
 idx=list((p/'.git/objects/pack').glob('*.idx'));assert len(idx)==1
 assert run([G,'verify-pack',idx[0]],p)['status']==0
 assert run([G,'fsck','--full'],p)['status']==0
 # A mutated public index must fail validation before any final file is visible.
 assert not any('tmp_den_' in k for k in state(p))
finally:
 (R/'target'/('pack-failure-'+args.tier+'.json')).write_text(json.dumps(rows))
print('PACK FAILURE COMPLETE',8,'failure/repeat rows plus CLI publication')
