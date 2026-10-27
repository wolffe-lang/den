"""External merge client versus independently generated git merge-file inputs."""
import argparse,json,os,pathlib,random,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');a=ap.parse_args()
G=os.environ['DEN_GIT'];D=str(R/f'target/{a.tier}/merge-client')
root=R/f'target/merge-file-{a.tier}';root.mkdir(parents=True,exist_ok=True)
cases=[(b'old',b'ours',b'theirs'),(b'',b'new\n',b'other\n'),(b'a\nb\nc\n',b'A\nb\nc\n',b'a\nb\nC\n')]
for n in range(1,9):
 base=[f'line-{i}\n'.encode() for i in range(n)]
 for i in range(n):
  for j in range(n):
   left=base.copy();right=base.copy();left[i]=b'ours\n';right[j]=b'theirs\n'
   cases.append((b''.join(base),b''.join(left),b''.join(right)))
for n in range(300):
 rng=random.Random(n);base=[f'l{i}\n'.encode() for i in range(10)]
 left=base.copy();right=base.copy()
 for values in (left,right):
  for _ in range(3):
   pos=rng.randrange(len(values)+1)
   values[pos:pos+rng.randrange(3)]=[rng.choice([b'x\n',b'y\n',b'z\n']) for _ in range(rng.randrange(3))]
 cases.append((b''.join(base),b''.join(left),b''.join(right)))
rows=[]
for n,(base,left,right) in enumerate(cases):
 for style in ('merge','diff3','zdiff3'):
  (root/'base').write_bytes(base);(root/'ours').write_bytes(left);(root/'theirs').write_bytes(right)
  args=[G,'merge-file','-p','-L','ours','-L','base','-L','theirs']
  if style!='merge':args.append('--'+style)
  expected=subprocess.run([*args,'ours','base','theirs'],cwd=root,capture_output=True)
  actual=subprocess.run([D,'base','ours','theirs',style],cwd=root,capture_output=True)
  good=(expected.returncode,expected.stdout,expected.stderr)==(actual.returncode,actual.stdout,actual.stderr)
  rows.append(dict(case=n,style=style,base=base.hex(),ours=left.hex(),theirs=right.hex(),git=[expected.returncode,expected.stdout.hex(),expected.stderr.hex()],den=[actual.returncode,actual.stdout.hex(),actual.stderr.hex()],equal=good))
  if not good:print('FAIL',n,style,expected.returncode,actual.returncode,repr(expected.stdout),repr(actual.stdout),flush=True)
(R/f'target/merge-file-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
failed=sum(not r['equal'] for r in rows);print(f'merge-file: {len(rows)-failed}/{len(rows)} exact; {failed} failures',flush=True)
raise SystemExit(bool(failed))
