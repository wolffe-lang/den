"""Explicit interruption seams, foreign temporaries and independent closure client."""
import argparse,base64,hashlib,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
a=argparse.ArgumentParser();a.add_argument('--tier',default='native');a.add_argument('--run',default='final');args=a.parse_args()
C=R/'target'/args.tier/'housekeeping-client';W=C.with_name('pack-write-client');P=C.with_name('pack-client')
root=R/'target'/('recovery-'+args.tier+'-'+args.run);root.mkdir();rows=[];refusals=[];contents={};states={}
def snap(p):
 out={}
 for f in sorted(p.rglob('*')):
  data=os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
  key=hashlib.sha256(data).hexdigest();contents[key]=base64.b64encode(data).decode();out[str(f.relative_to(p))]=[f.lstat().st_mode,key]
 key=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest();states[key]=out;return key
def call(p,tool,*cmd,data=None,ok=True):
 before=snap(p);q=subprocess.run([str(tool),*map(str,cmd)],cwd=p,input=data,capture_output=True)
 row=dict(args=list(map(str,(tool,*cmd))),before=before,after=snap(p),stdout=q.stdout.hex(),stderr=q.stderr.hex(),status=q.returncode);rows.append(row)
 if ok:assert q.returncode==0,row
 return q
try:
 base=root/'base';base.mkdir();call(base,G,'init','-q','-b','main','--template=')
 for i in range(8):
  (base/'file').write_bytes((f'version {i}\n'*100).encode());call(base,G,'add','file');call(base,G,'commit','-qm',f'version {i}')
 call(base,G,'repack','-a','-d','-n','-q')
 (base/'file').write_bytes(b'new version\n');call(base,G,'add','file');call(base,G,'commit','-qm','new')
 (base/'index-only').write_bytes(b'index root\n');call(base,G,'add','index-only')
 git_ids=set(x[:40] for x in call(base,G,'rev-list','--objects','--all','--reflog','--indexed-objects').stdout.decode().splitlines())
 before=snap(base);actual=call(base,C,base/'.git','closure');assert snap(base)==before and set(actual.stdout.decode().splitlines())==git_ids
 ids=call(base,G,'cat-file','--batch-all-objects','--batch-check=%(objectname)').stdout
 expected=call(base,G,'cat-file','--batch',data=ids).stdout
 for phase in ('before-publication','after-publication','before-removal','after-retirement-record','after-pack-removal'):
  p=root/phase;shutil.copytree(base,p);q=call(p,C,p/'.git','repack',phase,ok=False);assert q.returncode==1
  # The interrupted operation never removes unique bodies. The pinned reader
  # confirms the complete namespace even if an obsolete idx has no companion.
  assert call(p,G,'cat-file','--batch',data=ids).stdout==expected
  call(p,C,p/'.git','repack','');assert call(p,G,'cat-file','--batch',data=ids).stdout==expected
  call(p,G,'fsck','--full');before=snap(p);call(p,C,p/'.git','repack','');assert snap(p)==before
  names=root/(phase+'.names');names.write_bytes(ids)
  assert call(p,P,p/'.git','--batch',names,'16777216').stdout==expected
  print('RECOVERY',phase,'all objects retained; recovered; repeated',flush=True)
 for number,(cmd,feature) in enumerate([
  (['gc'],'gc expiry'),
  (['repack','-a','-q'],'server-info'),
  (['repack','-a','-n'],'progress and empty-output'),
  (['repack','-a','-n','-q','-k'],'-k without -d'),
  (['repack','-d'],'incremental selection'),
  (['repack','-A','-d','-n','-q'],'repack -A'),
  (['prune-packed','--expire=now'],'prune-packed --expire=now'),
 ]):
  p=root/('refusal-'+str(number));shutil.copytree(base,p);before=snap(p)
  q=call(p,C.with_name('den'),*cmd,ok=False)
  assert q.returncode==2 and feature.encode() in q.stderr and snap(p)==before
  refusals.append(dict(command=cmd,feature=feature,process=len(rows)-1))
 p=root/'foreign-temporary';shutil.copytree(base,p);foreign=p/'.git/objects/pack/tmp_den_foreign.pack';foreign.write_bytes(b'foreign temporary')
 before=snap(p);q=call(p,C,p/'.git','repack','',ok=False);assert q.returncode==1 and snap(p)==before
 p=root/'foreign-journal';shutil.copytree(base,p);(p/'.git/objects/info/den-repack-retire').write_bytes(b'foreign incomplete record')
 before=snap(p);q=call(p,C,p/'.git','repack','',ok=False);assert q.returncode==1 and snap(p)==before
 p=root/'orphan-publication';shutil.copytree(base,p);names=root/'orphan.names';names.write_bytes(ids)
 name=call(p,W,p/'.git',names,'ofs','orphan-publication').stdout.strip().decode();idx=p/'.git/objects/pack'/('pack-'+name+'.idx')
 call(p,G,'verify-pack',idx);assert call(p,G,'cat-file','--batch',data=ids).stdout==expected
 print('RECOVERY orphan publication restored through unchanged reader',flush=True)
finally:
 (R/'target'/('recovery-'+args.tier+'-'+args.run+'.json')).write_text(json.dumps(dict(rows=rows,refusals=refusals,states=states,contents=contents)))
