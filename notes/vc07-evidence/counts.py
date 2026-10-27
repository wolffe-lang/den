"""Derive vc07 counts and capture identities without entered totals."""
import hashlib,json,pathlib,re
P=pathlib.Path(__file__).resolve().parent
out={'tiers':{},'checked':{}}
def read(name):return json.loads((P/name).read_text())
for tier in ('native','release'):
    commands=read(f'merge-{tier}.json');files=read(f'merge-file-{tier}.json');bases=read(f'merge-bases-{tier}.json')
    exact=[r for r in commands if 'equal' in r];named=[r for r in commands if r.get('disposition')=='named-not-yet']
    assert len(exact)+len(named)==len(commands) and all(r['equal'] for r in exact+files+bases)
    out['tiers'][tier]={'command_total':len(commands),'command_exact':len(exact),'named_not_yet':len(named),'named_features':sorted({r['reason'] for r in named}),'file_exact':len(files),'all_base_sets':len(bases)}
for unit in ('mergebase','mergefile','mergeundo'):
    records=[json.loads(s) for s in (P/f'{unit}-checked.json').read_text().splitlines() if s.startswith('{')]
    assert len(records)==1 and records[0]['verdict']=='exit(0)'
    out['checked'][unit]=records[0]['verdict']
log=(P/'final-gate.log').read_text()
main=[json.loads(line) for line in log.splitlines() if line.startswith('{"not-yet":') and '"parity"' in line]
assert len(main)==1
out['main']=main[0]
manifest=read('final-inputs.json');out['functional_input_count']=len(manifest)
assert f'FUNCTIONAL INPUT MANIFEST UNCHANGED {len(manifest)}' in log
out['capture_sha256']={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ['final-inputs.json','final-gate.log']+[f'merge{part}-{tier}.json' for tier in ('native','release') for part in ('','-file','-bases')]}
(P/'final-counts.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
