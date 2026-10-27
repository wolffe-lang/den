import hashlib,json,pathlib,re
R=pathlib.Path(__file__).resolve().parent
result={}
for tier in ('native','release'):
    rows=json.loads((R/f'refs-oracle-{tier}.json').read_text())
    assert rows and all(row['equal'] for row in rows)
    api=json.loads((R/f'refs-api-{tier}.json').read_text())
    unsupported=json.loads((R/f'refs-unsupported-{tier}.json').read_text())
    assert all(row['den']['status']==2 for row in unsupported)
    result[tier]={'command_state_exact':len(rows),'independent_client_checks':len(api),'named_unsupported_not_parity':len(unsupported)}
result['checked']={}
for unit in ('refs','reflog'):
    rows=[json.loads(line) for line in (R/f'{unit}-checked.json').read_text().splitlines() if line.startswith('{')]
    assert len(rows)==1 and rows[0]['verdict']=='exit(0)'
    result['checked'][unit]=rows[0]['verdict']
log=(R/'final-gate.log').read_text()
assert 'FULL GATE EXIT 0' in log
counts=[json.loads(line) for line in log.splitlines() if line.startswith('{"not-yet"') and '"parity"' in line]
assert len(counts)==1
result['main_matrix']=counts[0]
static=re.search(r'den \(built twice, the same digest\); stripped: (\d+) bytes, sha256 ([0-9a-f]{64})',log)
assert static
result['static']={'stripped_bytes':int(static[1]),'sha256':static[2],'reproduced':True}
inputs=(R/'final-inputs.json').read_bytes()
result['functional_inputs']={'files':len(json.loads(inputs)),'manifest_sha256':hashlib.sha256(inputs).hexdigest()}
assert f"FUNCTIONAL INPUT MANIFEST UNCHANGED {result['functional_inputs']['files']}" in log
(R/'final-counts.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
