import hashlib,json,pathlib,subprocess,sys
R=pathlib.Path('/work/den');P=R/'notes/vc14-evidence/final-inputs.json'
paths=subprocess.check_output(['git','-C',str(R),'ls-files','-z']).decode().split('\0')
paths=sorted(p for p in paths if p and not p.startswith('notes/'))
current={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths}
if sys.argv[1]=='capture':
 P.write_text(json.dumps(current,sort_keys=True,indent=2)+'\n')
 print('VC14 FUNCTIONAL INPUTS CAPTURED',len(current),flush=True)
else:
 original=json.loads(P.read_text());assert original==current,{'added':sorted(current.keys()-original.keys()),'removed':sorted(original.keys()-current.keys()),'changed':[p for p in current.keys()&original.keys() if current[p]!=original[p]]}
 print('VC14 FUNCTIONAL INPUTS UNCHANGED',len(current),flush=True)
