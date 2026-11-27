"""Independent commit-DAG merge-base set comparisons, with immutable state.

The first 84 rows (seed 7007) are one 50-commit graph with equal dates. The
shapes after them each draw from their own seeded generator, printed in their
PASS line and in any FAIL line with the pair, so a red reruns exactly:
skewed (7011) draws committer dates at random, so parents are often newer than
children; wide (7013) has 12 roots and merges of up to four parents across
them; deep (7017) has one side an ancestor of the other at depth; unrelated
(7019) has two disjoint histories, so no base (Git exits 1 with nothing, den
prints nothing).
"""
import argparse,json,os,pathlib,random,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');a=ap.parse_args()
G=os.environ['DEN_GIT'];D=str(R/f'target/{a.tier}/merge-bases-client');O=runpy.run_path(str(R/'tools/oracle.py'))
root=R/f'target/merge-bases-{a.tier}'
if root.exists():shutil.rmtree(root)
root.mkdir(parents=True)
def git(*args,env=None):return subprocess.check_output([G,*args],cwd=root,env=env).decode().strip()
git('init','-q'); tree=subprocess.check_output([G,'mktree'],input=b'',cwd=root).decode().strip()
ids=[];rng=random.Random(7007)
for n in range(50):
 parents=[] if n in (0,25) else rng.sample(ids,min(len(ids),rng.randrange(1,4)))
 if n==3: parents=[ids[1],ids[2]]
 if n==4: parents=[ids[2],ids[1]]
 if n in (1,2): parents=[ids[0]]
 flags=[word for p in parents for word in ('-p',p)]
 ids.append(git('commit-tree',tree,*flags,'-m',f'node {n}'))
def compare(left,right,shape,seed):
 expected=subprocess.run([G,'merge-base','--all',left,right],cwd=root,capture_output=True)
 actual=subprocess.run([D,str(root/'.git'),left,right],cwd=root,capture_output=True)
 assert expected.returncode in (0,1) and actual.returncode==0 and actual.stderr==b'',(shape,seed,expected,actual)
 good=sorted(expected.stdout.splitlines())==sorted(actual.stdout.splitlines())
 row=dict(shape=shape,seed=seed,left=left,right=right,git=expected.stdout.decode().splitlines(),den=actual.stdout.decode().splitlines(),equal=good)
 if not good:print(f'FAIL merge-bases-{shape} seed={seed} left={left} right={right} git={row["git"]} den={row["den"]}',flush=True)
 return row
before=O['snapshot'](root);rows=[]
for i,j in [(3,4),(1,2),(0,25),(49,49)]+[(rng.randrange(50),rng.randrange(50)) for _ in range(80)]:
 rows.append(compare(ids[i],ids[j],'graph',7007))
 assert rows[-1]['equal'],rows[-1]
assert O['snapshot'](root)==before
print(f'merge-bases: {len(rows)}/{len(rows)} independent all-base sets; repository immutable')
def dated(seconds):return {**os.environ,'GIT_COMMITTER_DATE':f'{seconds} +0000','GIT_AUTHOR_DATE':f'{seconds} +0000'}
def build(count,parents_of,date_of,label):
 made=[]
 for n in range(count):
  flags=[word for p in parents_of(n,made) for word in ('-p',p)]
  made.append(git('commit-tree',tree,*flags,'-m',f'{label} node {n}',env=dated(date_of(n))))
 return made
shapes=[]
# skewed: the first graph's rule with dates drawn at random, so parents are often newer than children.
r=random.Random(7011)
def skew_parents(n,made):
 if n in (0,25): return []
 if n in (1,2): return [made[0]]
 if n==3: return [made[1],made[2]]
 if n==4: return [made[2],made[1]]
 return r.sample(made,min(len(made),r.randrange(1,4)))
dates=[1700000000+r.randrange(0,100000) for _ in range(50)]
skewed=build(50,skew_parents,lambda n:dates[n],'7011')
shapes.append(('skewed',7011,[(skewed[3],skewed[4]),(skewed[4],skewed[3])]+[(skewed[r.randrange(50)],skewed[r.randrange(50)]) for _ in range(40)]))
# wide: 12 roots, then 72 commits of 1-4 parents drawn from everything before.
r=random.Random(7013)
wide=build(84,lambda n,made:[] if n<12 else r.sample(made,min(len(made),r.randrange(1,5))),lambda n:1700000000+n,'7013')
shapes.append(('wide',7013,[(wide[r.randrange(84)],wide[r.randrange(84)]) for _ in range(40)]))
# deep: a chain of 300, with a short side branch every 25 commits merged back in.
r=random.Random(7017)
chain=[];side=[]
for n in range(300):
 parents=[] if n==0 else [chain[-1]]
 if n%25==5:
  side.append(git('commit-tree',tree,'-p',chain[n-3],'-m',f'7017 side {n}',env=dated(1700000000+n*2-1)))
  parents.append(side[-1])
 chain.append(git('commit-tree',tree,*[w for p in parents for w in ('-p',p)],'-m',f'7017 chain {n}',env=dated(1700000000+n*2)))
pairs=[]
for depth in (1,50,150,299):
 pairs+=[(chain[299-depth],chain[299]),(chain[299],chain[299-depth])]
pairs+=[(side[r.randrange(len(side))],chain[299]),(chain[r.randrange(300)],side[r.randrange(len(side))])]
shapes.append(('deep',7017,pairs))
# unrelated: two disjoint histories, so no pair across them has a base.
r=random.Random(7019)
one=build(40,lambda n,made:[] if n==0 else [made[r.randrange(n)]],lambda n:1700000000+n,'7019a')
two=build(40,lambda n,made:[] if n==0 else [made[r.randrange(n)]],lambda n:1700000000+n,'7019b')
shapes.append(('unrelated',7019,[(one[r.randrange(40)],two[r.randrange(40)]) for _ in range(20)]))
before=O['snapshot'](root);failed=0;total=0;names=[]
for shape,seed,shape_pairs in shapes:
 found=[compare(left,right,shape,seed) for left,right in shape_pairs]
 bad=sum(not row['equal'] for row in found)
 failed+=bad;total+=len(found);rows+=found;names.append(f'{shape} {seed}')
 print(f'{"PASS" if bad==0 else "FAIL"} merge-bases-{shape} seed={seed}: {len(found)-bad}/{len(found)} all-base sets equal Git\'s',flush=True)
assert O['snapshot'](root)==before
(R/f'target/merge-bases-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'merge-bases-shapes: {total-failed}/{total} all-base sets across {", ".join(names)}; repository immutable')
raise SystemExit(1 if failed else 0)
