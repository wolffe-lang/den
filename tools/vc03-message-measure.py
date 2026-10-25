"""Human subject versus reflog first-line handling and rename mode summary."""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];base=R/'target/vc03-message-measure'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def git(repo,*args):
 p=subprocess.run([G,*args],cwd=repo,capture_output=True);assert p.returncode==0,(args,p.stderr);return p
for i,message in enumerate((b'one\ntwo\n',b' one \n two \n',b'\none\n',b'one\t\t two\n',b'one\r two\n',b'one\n\ntwo\n')):
 repo=base/str(i);shutil.copytree(R/'target/corpus/two',repo,symlinks=True);path=base/f'message-{i}';path.write_bytes(message)
 p=git(repo,'commit','--allow-empty','--cleanup=verbatim','-F',str(path))
 log=(repo/'.git/logs/HEAD').read_bytes().splitlines()[-1]
 rows.append(dict(message_hex=message.hex(),stdout=p.stdout.hex(),reflog_hex=log.hex(),editmsg_hex=(repo/'.git/COMMIT_EDITMSG').read_bytes().hex()))
 print(repr(message),'stdout',repr(p.stdout),'reflog',repr(log))
repo=base/'rename-mode';shutil.copytree(R/'target/corpus/two',repo,symlinks=True);git(repo,'mv','a.txt','renamed.txt');os.chmod(repo/'renamed.txt',0o755);git(repo,'add','renamed.txt');p=git(repo,'commit','-m','renamed mode')
rows.append(dict(case='rename-mode',stdout=p.stdout.hex(),stderr=p.stderr.hex()));print('rename-mode',repr(p.stdout),repr(p.stderr))
(R/'target/vc03-message-measure.json').write_text(json.dumps(rows,indent=2)+'\n')
