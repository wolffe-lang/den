"""Verify immutable source inputs; preserve the original cache-contaminated manifest."""
import hashlib,json,pathlib
r=pathlib.Path(__file__).resolve().parents[2]; out=r/'notes/vc09-evidence'
raw=(out/'final-inputs.json').read_bytes(); original=json.loads(raw)
def source(name): return '.lu-cache' not in pathlib.PurePosixPath(name).parts and '__pycache__' not in pathlib.PurePosixPath(name).parts and not name.endswith('.pyc')
expected={k:v for k,v in original.items() if source(k)}
expected.update(json.loads((out/'test-inputs.json').read_text()))
paths=[]
for root in ('src','probes','tools','ci','docs','.github','packaging','tests'):
 paths.extend(p for p in (r/root).rglob('*') if p.is_file() and source(str(p.relative_to(r))))
paths.extend(r/p for p in ('README.md','wolf-toolchain.toml','den-oracle.toml','LICENSE','LICENSE-TRAINING-DATA') if (r/p).is_file())
actual={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
changed=sorted(k for k in expected.keys()|actual.keys() if expected.get(k)!=actual.get(k))
assert not changed, changed
result={'original_manifest_sha256':hashlib.sha256(raw).hexdigest(),'original_entries':len(original),'excluded_original_build_cache_entries':sum(not source(k) for k in original),'git_bound_test_entries':len(json.loads((out/'test-inputs.json').read_text())),'verified_functional_entries':len(actual),'changed':changed,'inputs':actual}
(out/'verified-functional-inputs.json').write_text(json.dumps(result,indent=2)+'\n')
print('FUNCTIONAL INPUTS UNCHANGED',len(actual),'(original manifest retained; generated .lu-cache excluded; tests independently Git-bound)')
