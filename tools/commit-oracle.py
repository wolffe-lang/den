"""Strict commit object/ref/reflog/index/worktree/output oracle matrix."""
import argparse,json,os,pathlib,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');ap.add_argument('--filter',default='');a=ap.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{a.tier}/commit-client')
O=runpy.run_path(str(R/'tools/oracle.py'))
base=R/f'target/commit-oracle-{a.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir();seeds=base/'seeds';seeds.mkdir()
def git(repo,*cmd):
 p=subprocess.run([G,*cmd],cwd=repo,capture_output=True)
 assert p.returncode==0,(cmd,p.stdout,p.stderr)
 return p.stdout

def seed(name,source='two'):
 p=seeds/name;shutil.copytree(R/'target/corpus'/source,p,symlinks=True);return p
seed('clean')
p=seed('staged');(p/'a.txt').write_bytes(b'alpha changed\n');git(p,'add','a.txt')
p=seed('both');(p/'a.txt').write_bytes(b'staged\n');git(p,'add','a.txt');(p/'a.txt').write_bytes(b'worktree\n')
p=seed('dirty');(p/'a.txt').write_bytes(b'worktree\n');(p/'b.txt').unlink();(p/'untracked').write_bytes(b'untracked\n')
p=seed('rename');git(p,'mv','a.txt','renamed.txt')
p=seed('amend-orig');(p/'.git/ORIG_HEAD').write_bytes(b'1'*40+b'\n')
seed('merge','merge')
p=seeds/'root';p.mkdir();git(p,'init','-q');(p/'a').write_bytes(b'alpha\n');(p/'b').write_bytes(b'beta\n');git(p,'add','.')
p=seeds/'empty';p.mkdir();git(p,'init','-q')
cases=[]
def case(name,args,fixture='staged',message=None,config='',env=None,lock=None):
 cases.append(dict(name=name,args=args,fixture=fixture,message_hex=None if message is None else message.hex(),config=config,env=env or {},lock=lock))
for fixture in ('clean','staged','both','dirty','rename','root','empty'):
 case(fixture+'-message',['-m','subject'],fixture)
 case(fixture+'-quiet',['-q','-m','subject'],fixture)
case('allow-empty',['--allow-empty','-m','empty'],'clean')
case('root-allow-empty',['--allow-empty','-m','empty'],'empty')
case('allow-empty-message',['--allow-empty-message','-m',''])
case('empty-message-refused',['-m',''])
case('all',['-a','-m','tracked'],'dirty')
case('paragraphs',['-m','one','-m','two'])
case('empty-paragraph',['-m','one','-m','','-m','two','--cleanup=verbatim'])
for mode in ('strip','whitespace','verbatim','scissors','default'):
 case('cleanup-'+mode,['--cleanup='+mode,'-F','{message}'],message=b'\n subject \t\n\n\n# comment\nbody  \n# ------------------------ >8 ------------------------\ncut\n')
case('file-empty',['--allow-empty-message','-F','{message}'],message=b'')
case('file-nul',['-F','{message}'],message=b'a\0b\n')
case('file-utf8',['-F','{message}'],message=b'\xff\n')
case('file-latin1',['-F','{message}'],message=b'\xff\n',config='[i18n]\ncommitEncoding=ISO-8859-1\n')
case('author',['--author','Other Person <other@example.invalid>','-m','subject'])
case('env-ident',['-m','subject'],env={'GIT_AUTHOR_NAME':'Author','GIT_AUTHOR_EMAIL':'author@example.invalid','GIT_COMMITTER_NAME':'Committer','GIT_COMMITTER_EMAIL':'committer@example.invalid'})
for i,date in enumerate(('@0 +0000','Thu, 07 Apr 2005 22:13:13 +0200','2005-04-07T22:13:13+02:00','2005-04-07 22:13:13 +0200','2005.04.07 22:13:13 +0200','04/07/2005 22:13:13 +0200','07.04.2005 22:13:13 +0200')):
 case('date-'+str(i),['--date='+date,'-m','subject'])
for fixture in ('clean','staged','both','root','merge','amend-orig'):
 case('amend-'+fixture,['--amend','-m','amended'],fixture)
case('amend-no-edit',['--amend','--no-edit'],'clean')
case('amend-reset',['--amend','--reset-author','-m','new author'],'clean',env={'GIT_AUTHOR_NAME':'New Author','GIT_AUTHOR_EMAIL':'new@example.invalid','GIT_AUTHOR_DATE':'1700000060 +0000'})
case('reset-without-amend',['--reset-author','-m','subject'])
case('editor-false',[])
case('index-lock',['-m','subject'],lock='index.lock')
case('ref-lock',['-m','subject'],lock='refs/heads/main.lock')
selected=[x for x in cases if a.filter in x['name']];assert selected
rows=[]
for c in selected:
 root=base/c['name'];root.mkdir();repo=root/'repo'
 message=root/'message'
 if c['message_hex'] is not None:message.write_bytes(bytes.fromhex(c['message_hex']))
 cmd=['commit',*[arg.replace('{message}',str(message)) for arg in c['args']]]
 def restore():
  if repo.exists():shutil.rmtree(repo)
  shutil.copytree(seeds/c['fixture'],repo,symlinks=True)
  if c['config']:
   with (repo/'.git/config').open('ab') as f:f.write(('\n'+c['config']).encode())
  if c['lock']:
   p=repo/'.git'/c['lock'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'foreign lock\n')
 prior=dict(os.environ);os.environ.update(c['env'])
 try:
  restore();expected=O['capture']([G,*cmd],repo,index_proof=True)
  restore();actual=O['capture']([C,*cmd],repo,index_proof=True)
 finally:
  os.environ.clear();os.environ.update(prior)
 good=O['equivalent'](expected,actual,'index-stat-proven')
 rows.append(dict(case=c,git=expected,den=actual,equal=good))
 print(('parity' if good else 'FAIL')+': '+c['name'],flush=True)
 if not good:
  print(' git',expected['status'],bytes.fromhex(expected['stdout']),bytes.fromhex(expected['stderr']))
  print(' den',actual['status'],bytes.fromhex(actual['stdout']),bytes.fromhex(actual['stderr']))
(R/f'target/commit-oracle-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
fail=sum(not r['equal'] for r in rows)
print('commit oracle:',len(rows)-fail,'/',len(rows),'parity;',fail,'mismatches')
raise SystemExit(bool(fail))
