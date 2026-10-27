"""Independent commit-DAG merge-base set comparisons, with immutable state."""
import argparse,json,os,pathlib,random,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');a=ap.parse_args()
G=os.environ['DEN_GIT'];D=str(R/f'target/{a.tier}/merge-bases-client');O=runpy.run_path(str(R/'tools/oracle.py'))
root=R/f'target/merge-bases-{a.tier}'
if root.exists():shutil.rmtree(root)
root.mkdir(parents=True)
def git(*args):return subprocess.check_output([G,*args],cwd=root).decode().strip()
git('init','-q'); tree=subprocess.check_output([G,'mktree'],input=b'',cwd=root).decode().strip()
ids=[];rng=random.Random(7007)
for n in range(50):
 parents=[] if n in (0,25) else rng.sample(ids,min(len(ids),rng.randrange(1,4)))
 if n==3: parents=[ids[1],ids[2]]
 if n==4: parents=[ids[2],ids[1]]
 if n in (1,2): parents=[ids[0]]
 flags=[word for p in parents for word in ('-p',p)]
 ids.append(git('commit-tree',tree,*flags,'-m',f'node {n}'))
before=O['snapshot'](root);rows=[]
for i,j in [(3,4),(1,2),(0,25),(49,49)]+[(rng.randrange(50),rng.randrange(50)) for _ in range(80)]:
 expected=subprocess.run([G,'merge-base','--all',ids[i],ids[j]],cwd=root,capture_output=True)
 actual=subprocess.run([D,str(root/'.git'),ids[i],ids[j]],cwd=root,capture_output=True)
 assert expected.returncode in (0,1) and actual.returncode==0 and actual.stderr==b'',(expected,actual)
 good=sorted(expected.stdout.splitlines())==sorted(actual.stdout.splitlines())
 rows.append(dict(left=ids[i],right=ids[j],git=expected.stdout.decode().splitlines(),den=actual.stdout.decode().splitlines(),equal=good))
 assert good,rows[-1]
assert O['snapshot'](root)==before
(R/f'target/merge-bases-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'merge-bases: {len(rows)}/{len(rows)} independent all-base sets; repository immutable')
