"""Pinned Git config syntax/precedence comparison, independent of den unit tests."""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT'];D=str(R/'target/native/den')
base=R/'target/config-oracle'
if base.exists():shutil.rmtree(base)
base.mkdir()
repo=base/'repo';repo.mkdir()
subprocess.run([G,'init','-q'],cwd=repo,check=True)
global_file=base/'global';global_file.write_text('[case]\nkey=global\n')
rows=[]
cases=[
 ('simple',b'[case]\nkey = simple\n','case.key',{}),
 ('case',b'[CASE]\nKEY = value\n','Case.Key',{}),
 ('implicit',b'[case]\nkey\n','case.key',{}),
 ('empty',b'[case]\nkey =\n','case.key',{}),
 ('quoted',b'[case]\nkey = " a # ; "\n','case.key',{}),
 ('mixed-quotes',b'[case]\nkey = a " b " c  # comment\n','case.key',{}),
 ('escapes',b'[case]\nkey = "a\\nb\\tc\\b\\\"\\\\"\n','case.key',{}),
 ('continuation',b'[case]\nkey = a\\\n  b\n','case.key',{}),
 ('comment-continuation',b'[case]\nkey = a # c\\\nnext=b\n','case.key',{}),
 ('quoted-subsection',b'[CASE "Sub.Case"]\nKEY=x\n','case.Sub.Case.key',{}),
 ('old-subsection',b'[CASE.Sub.Case]\nKEY=x\n','case.sub.case.key',{}),
 ('inline-section',b'[case] key=x\n','case.key',{}),
 ('bom',b'\xef\xbb\xbf[case]\nkey=x\r\n','case.key',{}),
 ('leading-trailing-space',b'[case]\nkey =  a  b   \n','case.key',{}),
 ('priority',b'[case]\nkey=repo\n','case.key',{}),
 ('runtime',b'[case]\nkey=repo\n','case.key',{'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'case.key','GIT_CONFIG_VALUE_0':'first','GIT_CONFIG_KEY_1':'case.key','GIT_CONFIG_VALUE_1':'last'}),
 ('missing',b'[case]\nkey=x\n','case.missing',{}),
 ('count-empty',b'[case]\nkey=x\n','case.key',{'GIT_CONFIG_COUNT':''}),
 ('empty-global',b'[case]\nother=x\n','case.key',{'GIT_CONFIG_GLOBAL':''}),
 ('bad-escape',b'[case]\nkey=\\q\n','case.key',{}),
 ('bad-section',b'[case\nkey=x\n','case.key',{}),
 ('bad-quote',b'[case]\nkey="x\n','case.key',{}),
 ('missing-env-key',b'[case]\nkey=x\n','case.key',{'GIT_CONFIG_COUNT':'1'}),
 ('invalid-key',b'[case]\nkey=x\n','bad',{}),
]
for name,text,key,overrides in cases:
 (repo/'.git/config').write_bytes(b'[core]\nrepositoryformatversion=0\n'+text)
 env=dict(os.environ,GIT_CONFIG_GLOBAL=str(global_file),**{k:v for k,v in overrides.items() if k!='GIT_CONFIG_GLOBAL'})
 if 'GIT_CONFIG_GLOBAL' in overrides:env['GIT_CONFIG_GLOBAL']=overrides['GIT_CONFIG_GLOBAL']
 def capture(tool):
  p=subprocess.run([tool,'config','--get',key],cwd=repo,env=env,capture_output=True)
  return dict(status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex())
 a,b=capture(G),capture(D)
 row=dict(name=name,config_hex=text.hex(),key=key,overrides=overrides,git=a,den=b,equal=a==b)
 rows.append(row)
 print(('parity' if row['equal'] else 'FAIL')+': '+name,flush=True)
 if not row['equal']:
  print(' git',a['status'],bytes.fromhex(a['stdout']),bytes.fromhex(a['stderr']))
  print(' den',b['status'],bytes.fromhex(b['stdout']),bytes.fromhex(b['stderr']))
(R/'target/config-oracle.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(int(any(not r['equal'] for r in rows)))
