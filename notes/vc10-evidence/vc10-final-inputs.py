"""Bind the one complete vc10 gate to all functional paths, both set directions."""
import hashlib,json,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[2]
OUT=R/'notes/vc10-evidence/final-inputs.json'
ROOTS=('src','probes','tools','ci','tests','.github','.wolf-bin')
IGNORED={'.lu-cache','__pycache__'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs():
 paths=[]
 for name in ROOTS:
  paths.extend(p for p in (R/name).rglob('*') if p.is_file() and not IGNORED.intersection(p.relative_to(R).parts) and p.suffix!='.pyc')
 paths.extend(R/name for name in ('wolf-toolchain.toml','den-oracle.toml'))
 return {str(p.relative_to(R)):digest(p) for p in sorted(set(paths))}
now=inputs();script=digest(pathlib.Path(__file__))
if sys.argv[1]=='capture':
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
 OUT.write_text(json.dumps(dict(functional_head=head,verification_script_sha256=script,files=now),indent=2)+'\n')
 print('VC10 INPUTS CAPTURED',len(now),head,flush=True)
else:
 old=json.loads(OUT.read_text());before=old['files']
 assert old['verification_script_sha256']==script,'verification helper changed'
 assert before.keys()==now.keys(),dict(added=sorted(now.keys()-before.keys()),missing=sorted(before.keys()-now.keys()))
 changed=[name for name in before if before[name]!=now[name]]
 assert not changed,changed
 print('VC10 FUNCTIONAL INPUTS UNCHANGED',len(now),flush=True)
