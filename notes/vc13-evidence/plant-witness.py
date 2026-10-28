import base64,json,os,pathlib,subprocess
R=pathlib.Path('/work/den');p=R/'target/pack-write-native/binary-git'
def state():
 return {str(f.relative_to(p)):{'mode':f.lstat().st_mode,'data':base64.b64encode(os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b'').decode()} for f in sorted(p.rglob('*'))}
before=state();argv=[str(R/'target/vc13-plant-client'),str(p/'.git'),str(R/'target/pack-write-native/binary-none.names'),'none']
q=subprocess.run(argv,capture_output=True);after=state()
(R/'notes/vc13-evidence/plant-local.json').write_text(json.dumps({'argv':argv,'stdout':q.stdout.hex(),'stderr':q.stderr.hex(),'status':q.returncode,'before':before,'after':after}))
assert q.returncode==1 and b'pack index checksum' in q.stderr and before==after,(q.returncode,q.stdout,q.stderr)
print('EXPECTED RED: vc13 writer binary-none: validated pair publication')
print('status',q.returncode,'stderr',q.stderr.decode().strip(),'complete state unchanged')
