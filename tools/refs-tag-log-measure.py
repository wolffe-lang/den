import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];base=R/'target/tag-log-measure';base.mkdir(parents=True,exist_ok=True)
seed=R/'target/refs-oracle-native/seed';rows=[]
for kind,revision in [('commit','HEAD'),('tree','HEAD^{tree}'),('blob','HEAD:a'),('tag','annotated')]:
 for annotation in [False,True]:
  repo=base/f'{kind}-{int(annotation)}'
  if repo.exists():shutil.rmtree(repo)
  shutil.copytree(seed,repo)
  obj=subprocess.check_output([G,'rev-parse',revision],cwd=repo).decode().strip()
  args=[G,'tag','--create-reflog']+(['-m','new annotation'] if annotation else [])+['new',obj]
  p=subprocess.run(args,cwd=repo,capture_output=True)
  log=repo/'.git/logs/refs/tags/new'
  row=dict(kind=kind,annotated=annotation,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex(),log=log.read_bytes().hex() if log.exists() else None)
  rows.append(row);print(kind,annotation,p.returncode,p.stderr,log.read_bytes() if log.exists() else None)
(R/'notes/vc06-evidence/tag-log-measure.json').write_text(json.dumps(rows,indent=2)+'\n')
