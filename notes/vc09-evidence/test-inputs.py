"""Verify tracked test inputs against the final functional Git head's blob hashes."""
import hashlib,json,pathlib,subprocess,sys
r=pathlib.Path(__file__).resolve().parents[2]
p=r/'notes/vc09-evidence/test-inputs.json'
if sys.argv[1]=='capture':
 names=subprocess.check_output(['git','-C',str(r),'ls-files','-z','tests']).decode().split('\0')
 rows={name:hashlib.sha256(subprocess.check_output(['git','-C',str(r),'show','HEAD:'+name])).hexdigest() for name in names if name}
 p.write_text(json.dumps(rows,indent=2)+'\n')
 print('TEST INPUTS BOUND TO GIT HEAD',subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD']).decode().strip(),len(rows))
else:
 rows=json.loads(p.read_text())
 for name,want in rows.items(): assert hashlib.sha256((r/name).read_bytes()).hexdigest()==want,name
 print('TRACKED TEST INPUTS UNCHANGED',len(rows))
