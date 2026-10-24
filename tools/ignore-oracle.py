"""Generated Git check-ignore provenance/output/status matrix; no VCS source."""
import argparse,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');args=ap.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{args.tier}/ignore-client')
base=R/f'target/ignore-oracle-{args.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir()
subprocess.run([G,'init','-q'],cwd=base,check=True)
paths=['file','root','a/file','a/root','d/file','a/d/file','foo/a','foo/x/a','space name','a/b','!literal','#hash','trailing ','letter7','foo.txt','a/foo.txt']
for name in paths:
 p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'x\n')
dirs=['a','d','a/d','foo','foo/x']
patterns=[b'file',b'/file',b'*.txt',b'a/*',b'a/**',b'**/file',b'**/a',b'a/**/file',b'a/***/file',b'***',b'foo/**/a',b'foo/*/a',b'foo/*',b'foo/',b'/a/',b'*/',b'fi?e',b'letter[0-9]',b'letter[[:digit:]]',b'[!a-z]*',b'\\!literal',b'\\#hash',b'#hash',b'!file',b'*\n!file',b'a/\n!a/file',b'a/*\n!a/file',b'space name',b'trailing\\ ',b'trailing ',b'file\\',b'\\f\\i\\l\\e',b'[',b'[]a]',b'[!]]',b'/**/file',b'foo/**',b'file\x00junk',b'\xef\xbb\xbffile']
rows=[]
def capture(cmd):
 p=subprocess.run(cmd,cwd=base,capture_output=True,timeout=20)
 assert b'wolf-trap' not in p.stderr
 return dict(status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex())
for pattern in patterns:
 (base/'.gitignore').write_bytes(pattern+b'\n')
 for path in paths+dirs:
  oracle=capture([G,'check-ignore','-v','--no-index',path])
  actual=capture([C,'query',str(base/'.git'),str(base),path,'dir' if path in dirs else 'file'])
  rows.append(dict(pattern_hex=pattern.hex(),path=path,git=oracle,den=actual,equal=oracle==actual))
# Source precedence and nested rules; query exactly the same files without index bypass hacks.
(base/'.gitignore').write_bytes(b'*.txt\n!a/foo.txt\n/a/root\n')
(base/'a/.gitignore').write_bytes(b'foo.txt\n!root\n')
(base/'.git/info/exclude').parent.mkdir(parents=True,exist_ok=True)
(base/'.git/info/exclude').write_bytes(b'file\n')
for path in paths+dirs:
 oracle=capture([G,'check-ignore','-v','--no-index',path])
 actual=capture([C,'query',str(base/'.git'),str(base),path,'dir' if path in dirs else 'file'])
 rows.append(dict(pattern_hex='precedence',path=path,git=oracle,den=actual,equal=oracle==actual))
out=R/f'target/ignore-oracle-{args.tier}.json';out.write_text(json.dumps(rows,indent=2)+'\n')
fail=[x for x in rows if not x['equal']]
print(f'ignore oracle {args.tier}: {len(rows)-len(fail)}/{len(rows)} parity, {len(fail)} mismatches')
for row in fail[:25]:
 print(row['pattern_hex'],repr(row['path']),'git',row['git']['status'],bytes.fromhex(row['git']['stdout']),bytes.fromhex(row['git']['stderr']),'den',row['den']['status'],bytes.fromhex(row['den']['stdout']),bytes.fromhex(row['den']['stderr']))
raise SystemExit(bool(fail))
