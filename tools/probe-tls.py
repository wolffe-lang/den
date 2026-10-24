"""OpenSSL is a black-box server. Never reads any TLS implementation source."""
import json,os,pathlib,re,socket,ssl,subprocess,time
R=pathlib.Path(__file__).resolve().parent.parent;T=R/'target/tls';rows=[]
def run(*args):subprocess.run(args,check=True,cwd=R,capture_output=True)
run('openssl','req','-x509','-newkey','ed25519','-nodes','-keyout',str(T/'key.pem'),'-out',str(T/'cert.pem'),'-subj','/CN=localhost','-days','2','-addext','subjectAltName=DNS:localhost','-addext','basicConstraints=critical,CA:TRUE')
run('openssl','x509','-in',str(T/'cert.pem'),'-outform','DER','-out',str(T/'anchor.der'))
(T/'random').write_bytes(os.urandom(32));(T/'scalar').write_bytes(os.urandom(32))
# Concatenated DER anchors: the std TLS API accepts explicit roots, not PEM.
roots=b''
for pem in re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----',pathlib.Path('/etc/ssl/certs/ca-certificates.crt').read_text(),re.S):
    roots+=ssl.PEM_cert_to_DER_cert(pem)
(T/'roots.der').write_bytes(roots)
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
with (T/'server.log').open('wb') as log:
 server=subprocess.Popen(['openssl','s_server','-accept',f'127.0.0.1:{port}','-cert',str(T/'cert.pem'),'-key',str(T/'key.pem'),'-tls1_3','-ciphersuites','TLS_CHACHA20_POLY1305_SHA256','-groups','X25519','-www','-quiet'],stdout=log,stderr=log)
 try:
  for _ in range(100):
   try:
    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
   except OSError:time.sleep(.05)
  for name,addr,host,anchor in [('local',f'127.0.0.1:{port}','localhost',str(T/'anchor.der')),('github','github.com:443','github.com',str(T/'roots.der'))]:
   for tier in ('native','checked'):
    args=[]
    env={**os.environ,'TZ':'UTC','TLS_PROBE_ADDR':addr,'TLS_PROBE_HOST':host,'TLS_PROBE_ROOTS':anchor}
    if tier=='native':cmd=[str(R/'target/probes/tls'),*args]
    else:cmd=[os.environ['WOLF'],'conform-run',str(R/'probes/tls/main.lu'),'--checked','--json']
    start=time.monotonic()
    try:
     p=subprocess.run(cmd,cwd=R,capture_output=True,timeout=120,env=env)
     data=p.stdout+p.stderr;status=p.returncode
    except subprocess.TimeoutExpired as e:data=(e.stdout or b'')+(e.stderr or b'')+b'\nTIMEOUT 120s\n';status=124
    (R/f'target/probes/tls-{name}-{tier}.log').write_bytes(data)
    row={'server':name,'tier':tier,'exit':status,'seconds':round(time.monotonic()-start,3)}
    print(json.dumps(row),flush=True);rows.append(row)
 finally:
  server.terminate()
  try:server.wait(timeout=5)
  except subprocess.TimeoutExpired:server.kill();server.wait()
(T/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
