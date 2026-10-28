"""Bind the sole final vc12 gauntlet to functional inputs in both set directions."""
import hashlib,json,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[2]
OUT=R/'notes/vc12-evidence/final-inputs.json'
ROOTS=('src','probes','tools','ci','tests','.github','.wolf-bin','docs')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs():
 paths=[]
 for name in ROOTS:
  paths.extend(p for p in (R/name).rglob('*') if p.is_file() and not {'.lu-cache','__pycache__'}.intersection(p.relative_to(R).parts) and p.suffix!='.pyc')
 paths.extend(R/name for name in ('wolf-toolchain.toml','den-oracle.toml','README.md'))
 return {str(p.relative_to(R)):sha(p) for p in sorted(set(paths))}
now=inputs();script=sha(pathlib.Path(__file__))
if sys.argv[1]=='capture':
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
 OUT.write_text(json.dumps(dict(functional_head=head,verification_script_sha256=script,files=now),indent=2)+'\n')
 print('VC12 INPUTS CAPTURED',len(now),head,flush=True)
else:
 old=json.loads(OUT.read_text());before=old['files']
 assert old['verification_script_sha256']==script
 if sys.argv[1]=='tracked':
  # The final tree has no installed toolchain; check every tracked input.
  before={k:v for k,v in before.items() if not k.startswith('.wolf-bin/')}
  now={k:v for k,v in now.items() if not k.startswith('.wolf-bin/')}
 assert before.keys()==now.keys(),dict(added=sorted(now.keys()-before.keys()),missing=sorted(before.keys()-now.keys()))
 assert all(before[k]==now[k] for k in before),[k for k in before if before[k]!=now[k]]
 print('VC12 FUNCTIONAL INPUTS UNCHANGED',len(now),flush=True)
