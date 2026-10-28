"""Verify all non-installed final inputs against the final checkout and Git tree."""
import hashlib,json,pathlib,subprocess
R=pathlib.Path(__file__).resolve().parents[2]
files=json.loads((R/'notes/vc11-evidence/final-inputs.json').read_text())['files']
checked=0;installed=0
for rel,want in files.items():
 if rel.startswith('.wolf-bin/'):
  installed+=1;continue
 assert hashlib.sha256((R/rel).read_bytes()).hexdigest()==want,rel
 blob=subprocess.check_output(['git','show','HEAD:'+rel],cwd=R)
 assert hashlib.sha256(blob).hexdigest()==want,rel
 checked+=1
print('final tree:',checked,'unchanged tracked inputs;',installed,'installed toolchain files bound by the hasu manifest;',len(files),'total',flush=True)
