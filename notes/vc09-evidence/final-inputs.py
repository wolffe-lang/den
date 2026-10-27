"""Bind final gate to every functional input, not the checkout's stale index."""
import hashlib,json,pathlib,sys
r=pathlib.Path(__file__).resolve().parents[2]
paths=[]
for root in ('src','probes','tools','ci','docs','.github','packaging'):
 paths.extend(p for p in (r/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc'))
paths.extend(r/p for p in ('README.md','wolf-toolchain.toml','den-oracle.toml','LICENSE','LICENSE-TRAINING-DATA') if (r/p).is_file())
actual={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
file=r/'notes/vc09-evidence/final-inputs.json'
if sys.argv[1]=='capture':
 file.write_text(json.dumps(actual,indent=2)+'\n'); print('FINAL INPUTS CAPTURED',len(actual),flush=True)
else:
 expected=json.loads(file.read_text()); assert actual==expected, sorted(k for k in actual.keys()|expected.keys() if actual.get(k)!=expected.get(k))
 print('FINAL INPUT MANIFEST UNCHANGED',len(actual),flush=True)
