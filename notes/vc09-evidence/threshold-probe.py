import json,os,pathlib,shutil,subprocess
r=pathlib.Path('/work/den'); source=r/'target/pack-interop-native/0-ref'; target=r/'target/vc09-threshold-probe'
if target.exists(): shutil.rmtree(target)
shutil.copytree(source,target)
packs=list((target/'.git/objects/pack').glob('*.pack'));assert len(packs)==1
for suffix in ('.idx','.rev'):
 p=packs[0].with_suffix(suffix)
 if p.exists(): p.unlink()
rows=[]
for args in [('index-pack','--index-version=2,1',str(packs[0])),('cat-file','--batch-all-objects','--batch-check=%(objectname)')]:
 p=subprocess.run([os.environ['DEN_GIT'],*args],cwd=target,capture_output=True)
 rows.append(dict(args=args,status=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()))
assert rows[0]['status']==0 and 'wrong index v2 file size' in rows[1]['stderr'], rows
(r/'notes/vc09-evidence/index-threshold-probe.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
