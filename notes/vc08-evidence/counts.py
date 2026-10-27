"""Derive vc08 evidence totals from captures and verify the exact tested sources."""
import hashlib,json,pathlib,sys
E=pathlib.Path(__file__).resolve().parent
R=E.parent.parent
manifest=json.loads((E/'final-inputs.json').read_text())
for name,digest in manifest.items():
    assert hashlib.sha256((R/name).read_bytes()).hexdigest()==digest, name
out={'functional_files':len(manifest),'tiers':{}}
sets=[]
for tier in ('native','release'):
    rows=json.loads((E/f'replay-{tier}.json').read_text())
    assert rows and all(r['verified'] for r in rows)
    parity=[r for r in rows if r['disposition']=='parity']
    named=[r for r in rows if r['disposition']=='named-not-yet']
    assert len(parity)+len(named)==len(rows)
    assert all(r['equal'] for r in parity)
    assert all(not r['equal'] and r['reason'] for r in named)
    sets.append({r['name'] for r in rows})
    client=json.loads((E/f'sequencer-api-{tier}.json').read_text())
    assert client and all(r['status'] in (0,2) for r in client)
    out['tiers'][tier]={'exact_scenarios':len(parity),'named_scenarios':len(named),
        'exact_process_comparisons':sum(len(r['git']) for r in rows)-len(named),
        'independent_client_checks':len(client),'new_skips':0}
assert sets[0]==sets[1]
checked=[json.loads(line) for line in (E/'sequencer-checked.json').read_text().splitlines() if line.startswith('{')]
assert len(checked)==1 and checked[0]['verdict']=='exit(0)'
out['actual_checked']={checked[0]['file']:checked[0]['verdict']}
(E/'final-counts.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
