import json, os, pathlib, shutil, subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];base=R/'target/refs-cleanup-measure';base.mkdir(parents=True,exist_ok=True)
seed=R/'target/refs-oracle-native/seed';one=subprocess.check_output([G,'rev-parse','HEAD'],cwd=seed).strip()
rows=[]
for command in [('switch','main'),('reset','--soft','HEAD'),('reset','--hard','HEAD')]:
 for name in ['AUTO_MERGE.lock','REBASE_HEAD.lock','MERGE_HEAD.lock','MERGE_MSG.lock','MERGE_MODE.lock','SQUASH_MSG.lock','CHERRY_PICK_HEAD.lock','REVERT_HEAD.lock']:
  repo=base/('-'.join(command)+'-'+name)
  if repo.exists():shutil.rmtree(repo)
  shutil.copytree(seed,repo)
  path=repo/'.git'/name;path.write_bytes(one+b'\n')
  p=subprocess.run([G,*command],cwd=repo,capture_output=True)
  row=dict(command=command,name=name,remaining=path.exists(),status=p.returncode,stderr=p.stderr.hex())
  rows.append(row);print(command,name,p.returncode,path.exists(),p.stderr,flush=True)
(R/'notes/vc06-evidence/cleanup-lock-measure.json').write_text(json.dumps(rows,indent=2)+'\n')
