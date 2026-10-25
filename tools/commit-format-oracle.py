"""Compare pure formatting results to Git-created commit objects, not guessed text."""
import argparse,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');ap.add_argument('--dates-only',action='store_true');a=ap.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{a.tier}/commit-format-client')
base=R/f'target/commit-format-oracle-{a.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir();repo=base/'repo';repo.mkdir();rows=[]
def run(command,data=None,env=None):return subprocess.run(command,cwd=repo,input=data,capture_output=True,env=env,timeout=30)
def git(*args,data=None,env=None):return run([G,*args],data,env)
assert git('init','-q').returncode==0
tree=git('mktree',data=b'').stdout.strip().decode()
for text in ['@0 +0000','@1 -0000','1700000000 +0000','@1700000000 -0730',
 'Thu, 07 Apr 2005 22:13:13 +0200','07 Apr 2005 22:13:13 +0200',
 '2005-04-07T22:13:13+02:00','2005-04-07 22:13:13 +0200','2005-04-07T20:13:13Z',
 '2005-04-07T22:13:13.019 +0200','2005.04.07 22:13:13 +0200',
 '04/07/2005 22:13:13 +0200','07.04.2005 22:13:13 +0200',
 '2024-02-29T12:00:00Z','2005-04-07','1969-12-31T23:59:59Z',
 '2000-02-30T12:00:00Z','2000-02-31T12:00:00Z','2023-02-29T12:00:00Z','2005-04-31T12:00:00Z','2005-13-01T12:00:00Z','2005-00-01T12:00:00Z','2005-04-00T12:00:00Z','2005-01-32T12:00:00Z','2005-04-07T24:00:00Z','2005-04-07T22:60:00Z','2005-04-07T22:13:60Z','@1 +2400','@1 +2460','@9223372036854775807 +0000']:
 p=git('commit-tree',tree,'-m','date',env=dict(os.environ,GIT_AUTHOR_DATE=text))
 q=run([C,'date',text])
 expected=None
 if p.returncode==0:
  body=git('cat-file','commit',p.stdout.strip().decode()).stdout
  author=next(line for line in body.splitlines() if line.startswith(b'author '))
  expected=b' '.join(author.rsplit(b' ',2)[1:])+b'\n'
 good=q.returncode==0 and q.stdout==expected if expected is not None else q.returncode!=0
 rows.append(dict(kind='date',input=text,git_status=p.returncode,expected_hex=None if expected is None else expected.hex(),den_status=q.returncode,den_stdout=q.stdout.hex(),den_stderr=q.stderr.hex(),equal=good))
 print(('parity' if good else 'FAIL')+': date '+text)
 if not good:print(' git',p.returncode,expected,p.stderr,'den',q.returncode,q.stdout,q.stderr)
messages=[b'',b'  subject  \n\n\nbody\t \n\n',b'# comment\nsubject\n# other\n',b'subject\n# ------------------------ >8 ------------------------\ncut\n',b'! comment\nsubject\n',b';; comment\nsubject\n',b'\n\t\n',b'a\r\nb\r\n']
for mode in ([] if a.dates_only else ['strip','whitespace','verbatim','scissors','default']):
 for marker in ['#','!',';;']:
  for number,message in enumerate(messages):
   path=base/'message';path.write_bytes(message)
   p=git('-c','core.commentString='+marker,'commit','--allow-empty','--allow-empty-message','-q','--cleanup='+mode,'-F',str(path))
   assert p.returncode==0,(mode,marker,p.stderr)
   body=git('cat-file','commit','HEAD').stdout.split(b'\n\n',1)[1]
   q=run([C,'cleanup',mode,marker,'0',str(path)])
   good=q.returncode==0 and q.stdout==body
   rows.append(dict(kind='cleanup',mode=mode,marker=marker,input_hex=message.hex(),expected_hex=body.hex(),den_status=q.returncode,den_stdout=q.stdout.hex(),den_stderr=q.stderr.hex(),equal=good))
   if not good:print('FAIL cleanup',mode,marker,number,repr(body),q.returncode,repr(q.stdout),repr(q.stderr))
(R/f'target/commit-format-oracle-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
fail=sum(not x['equal'] for x in rows)
print('commit-format oracle:',len(rows)-fail,'/',len(rows),'parity;',fail,'mismatches')
raise SystemExit(bool(fail))
