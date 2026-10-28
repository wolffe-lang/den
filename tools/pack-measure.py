import hashlib,json,os,pathlib,subprocess
R=pathlib.Path('/work/den'); G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
rows=[]
for name in ['linear-ofs','empty-none','m2-unborn-none','similar-ofs']:
 p=R/'target/pack-write-native'/name
 if not p.exists():continue
 cmds=[['count-objects','-v'],['fsck','--full']]
 for idx in (p/'.git/objects/pack').glob('*.idx'):cmds.append(['verify-pack','-v',str(idx)])
 for cmd in cmds:
  q=subprocess.run([G]+cmd,cwd=p,capture_output=True); row={'fixture':name,'args':cmd,'status':q.returncode,'out':q.stdout.decode(),'err':q.stderr.decode()};rows.append(row);print(json.dumps(row),flush=True)
(R/'target/pack-measure.json').write_text(json.dumps(rows,indent=2))
