"""Exact default stat width on private PTYs and exported COLUMNS.
All terminals/processes belong to this test inside the lane container.
"""
import argparse,fcntl,json,os,pathlib,pty,struct,subprocess,termios
R=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--tier',required=True);a=p.parse_args()
repo=R/f'target/diff-endpoints-{a.tier}/stat-widths';assert repo.is_dir()
git=os.environ['DEN_GIT'];den=str(R/f'target/{a.tier}/den');rows=[]
def capture(tool,width,columns,flags):
 env=dict(os.environ);env.pop('COLUMNS',None)
 if columns is not None:env['COLUMNS']=columns
 args=[tool,'diff','--stat',*flags]
 if width is None:
  r=subprocess.run(args,cwd=repo,env=env,capture_output=True,timeout=30);return r.stdout,r.stderr,r.returncode
 master,slave=pty.openpty()
 fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,width,0,0))
 mode=termios.tcgetattr(slave);mode[1]&=~termios.OPOST;termios.tcsetattr(slave,termios.TCSANOW,mode)
 process=subprocess.Popen(args,cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=slave,stderr=subprocess.PIPE)
 os.close(slave);output=bytearray()
 try:
  while True:
   try:chunk=os.read(master,65536)
   except OSError:break
   if not chunk:break
   output.extend(chunk)
  _,err=process.communicate(timeout=30)
 finally:os.close(master)
 return bytes(output),err,process.returncode
for width in (None,0,40,80,120):
 for columns in (None,'0','-1','garbage','40','120'):
  for flag in ([],['--stat-width=0'],['--stat-width=60']):
   expected=capture(git,width,columns,flag);actual=capture(den,width,columns,flag)
   rows.append({'width':width,'COLUMNS':columns,'flags':flag,'git':[expected[0].hex(),expected[1].hex(),expected[2]],'den':[actual[0].hex(),actual[1].hex(),actual[2]],'ok':actual==expected})
(R/f'target/diff-terminal-{a.tier}.json').write_text(json.dumps({'rows':rows},indent=2)+'\n')
bad=[(r['width'],r['COLUMNS'],r['flags']) for r in rows if not r['ok']]
print('diff terminal widths',len(rows)-len(bad),'/',len(rows),'failed',bad,flush=True)
assert not bad
