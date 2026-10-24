import json,os,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parent.parent
out=R/'target/probes';rows=[]
expected_absent={'argv0','regex','glob','bigint','deflate','mmap'}
for p in sorted((R/'probes').glob('*/main.lu')):
 name=p.parent.name
 if name=='tls':continue # driven by probe-tls with the local and external servers
 if len(sys.argv)>1 and name not in sys.argv[1:]:continue
 for tier in ('native','checked'):
  log=out/f'{name}-{tier}.log'
  if tier=='native':
   cmd=[os.environ['WOLF'],'build','--deny-warnings',str(p),'-o',str(out/name)]
  else:cmd=[os.environ['WOLF'],'conform-run',str(p),'--checked','--json']
  result=subprocess.run(cmd,cwd=R,capture_output=True,timeout=180)
  data=result.stdout+result.stderr
  if tier=='native' and result.returncode==0:
   result=subprocess.run(['/usr/bin/time','-v',str(out/name)],cwd=R,capture_output=True,timeout=180,env={**os.environ,'TZ':'UTC'})
   data+=result.stdout+result.stderr
  log.write_bytes(data)
  verdict=None
  if tier=='checked':
   for line in result.stdout.splitlines():
    if line.startswith(b'{'):verdict=json.loads(line).get('verdict')
   if verdict=='exit(0)':status='present'
   elif verdict=='unsupported':status='unsupported'
   elif name in expected_absent and verdict and verdict.startswith('fail('):status='absent'
   else:status='FAILED'
  else:
   status='absent' if name in expected_absent and result.returncode==2 else ('present' if result.returncode==0 else 'FAILED')
  row={'probe':name,'tier':tier,'status':status,'exit':result.returncode,'log':str(log.relative_to(R))}
  rows.append(row);print(json.dumps(row),flush=True)
(out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
if any(r['status']=='FAILED' for r in rows):sys.exit(1)
