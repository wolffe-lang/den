import hashlib,json,os,pathlib,shutil,subprocess
R=pathlib.Path('/work/den');G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
report=[]
for row in json.loads((R/'target/pack-write-native.json').read_text())['sizes']:
 if row['mode']!='none':continue
 src=R/'target/pack-write-native'/(row['fixture']+'-git');p=R/'target/no-delta-baselines'/row['fixture']
 assert not p.exists();shutil.copytree(src,p)
 ids=subprocess.check_output([G,'cat-file','--batch-all-objects','--batch-check=%(objectname)'],cwd=p)
 q=subprocess.run([G,'pack-objects','-q','--window=0','--no-reuse-object','.git/objects/pack/pack'],cwd=p,input=ids,capture_output=True)
 assert q.returncode==0,q.stderr
 stem=p/'.git/objects/pack'/('pack-'+q.stdout.decode().strip());pack=stem.with_suffix('.pack');idx=stem.with_suffix('.idx')
 size=pack.stat().st_size;ratio=row['den']/size;assert ratio<=1.5,(row,ratio)
 report.append({'fixture':row['fixture'],'den':row['den'],'git_no_delta':size,'ratio':ratio,'default_ratio':row['ratio'],'stdout':q.stdout.hex(),'stderr':q.stderr.hex(),'status':q.returncode,'input':ids.decode(),'pack':pack.read_bytes().hex(),'idx':idx.read_bytes().hex(),'pack_mode':pack.stat().st_mode,'idx_mode':idx.stat().st_mode})
(R/'notes/vc13-evidence/no-delta-baselines.json').write_text(json.dumps(report))
print('NO DELTA BASELINE',len(report),'fixtures; max',max((r['ratio'],r['fixture']) for r in report))
