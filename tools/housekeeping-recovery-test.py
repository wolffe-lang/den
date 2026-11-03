"""Explicit interruption seams, foreign temporaries and independent closure client."""
import argparse,base64,hashlib,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
# git-config(1): gc.auto=0 disables every auto-gc heuristic; gc.autoDetach
# controls background return. git-maintenance(1): maintenance.auto=false stops
# porcelain-triggered maintenance; autoDetach=false also keeps any auto work joined.
# Fresh owned repositories and joined commands mean no pre-existing writer exists.
# These are command-scoped controls, never persistent config or snapshot exclusions.
GIT_SETUP=['-c','gc.auto=0','-c','maintenance.auto=false','-c','gc.autoDetach=false','-c','maintenance.autoDetach=false']
a=argparse.ArgumentParser();a.add_argument('--tier',default='native');a.add_argument('--run',default='final');a.add_argument('--proof-only',action='store_true');args=a.parse_args()
C=R/'target'/args.tier/'housekeeping-client';W=C.with_name('pack-write-client');P=C.with_name('pack-client')
root=R/'target'/('recovery-'+args.tier+'-'+args.run);root.mkdir();rows=[];refusals=[];contents={};states={}
def snap(p):
 out={}
 for f in sorted(p.rglob('*')):
  data=os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
  key=hashlib.sha256(data).hexdigest();contents[key]=base64.b64encode(data).decode();out[str(f.relative_to(p))]=[f.lstat().st_mode,key]
 key=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest();states[key]=out;return key
def call(p,tool,*cmd,data=None,ok=True,setup=True,defaults=(),trace=None):
 argv=[str(tool),*defaults,*(GIT_SETUP if str(tool)==G and setup else []),*map(str,cmd)]
 env=dict(os.environ)
 if trace is not None:env['GIT_TRACE2_EVENT']=str(trace.resolve())
 before=snap(p);q=subprocess.run(argv,cwd=p,input=data,capture_output=True,env=env)
 row=dict(args=argv,before=before,after=snap(p),stdout=q.stdout.hex(),stderr=q.stderr.hex(),status=q.returncode,
          environment={k:v for k,v in env.items() if k.startswith(('GIT_','DEN_')) or k in ('HOME','TMPDIR','PATH','TZ','LC_ALL')});rows.append(row)
 if ok:assert q.returncode==0,row
 return q
def auto_work_proof():
 # git-maintenance(1): maintenance.auto=false prevents commands from invoking
 # maintenance run --auto; it does not stop explicitly started foreign writers.
 # Force the trigger on, with foreground completion, in a separate counterfactual
 # repository. Trace2 proves that setup controls remove the automatic child,
 # rather than hiding its transient lock from the complete snapshot.
 defaults=['-c','gc.auto=1','-c','maintenance.auto=true','-c','gc.autoDetach=false','-c','maintenance.autoDetach=false']
 observations=[]
 for name,controlled in (('counterfactual',False),('controlled',True)):
  p=root/('auto-'+name);p.mkdir();call(p,G,'init','-q','-b','main','--template=')
  trace=root/('auto-'+name+'.trace.jsonl')
  call(p,G,'commit','--allow-empty','-qm','maintenance proof',setup=controlled,defaults=defaults,trace=trace)
  events=[json.loads(line) for line in trace.read_text().splitlines()]
  children=[event for event in events if event.get('event')=='child_start' and 'maintenance' in event.get('argv',[]) and '--auto' in event.get('argv',[])]
  observations.append(dict(name=name,automatic_children=children,trace=str(trace)))
 (root/'auto-work-proof.json').write_text(json.dumps(observations,indent=2)+'\n')
 if not observations[0]['automatic_children']:
  print('FAIL vc14-auto-work-counterfactual',flush=True);return False
 print('PASS vc14-auto-work-counterfactual automatic helper observed; foreground joined',flush=True)
 if observations[1]['automatic_children']:
  print('FAIL vc14-setup-no-automatic-maintenance',flush=True);return False
 print('PASS vc14-setup-no-automatic-maintenance no helper started; every snapshot path retained',flush=True)
 return True
try:
 if not auto_work_proof():raise SystemExit(1)
 if args.proof_only:raise SystemExit(0)
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
