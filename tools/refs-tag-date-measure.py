import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];repo=R/'target/tag-date-measure'
if repo.exists():shutil.rmtree(repo)
shutil.copytree(R/'target/refs-oracle-native/seed',repo)
tree=subprocess.check_output([G,'rev-parse','HEAD^{tree}'],cwd=repo).strip()
e=dict(os.environ,GIT_AUTHOR_DATE='946684800 +1400',GIT_COMMITTER_DATE='978307200 -1200')
id=subprocess.check_output([G,'commit-tree',tree.decode(),'-m','first line\nsecond line'],cwd=repo,env=e).decode().strip()
p=subprocess.run([G,'tag','--create-reflog','new',id],cwd=repo,capture_output=True)
log=(repo/'.git/logs/refs/tags/new').read_bytes()
print(p.returncode,p.stderr,log)
(R/'notes/vc06-evidence/tag-date-measure.json').write_text(json.dumps(dict(oid=id,author=e['GIT_AUTHOR_DATE'],committer=e['GIT_COMMITTER_DATE'],log=log.hex()))+'\n')
