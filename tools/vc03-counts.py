"""Aggregate retained observations; never rerun a command or invent a pass."""
import contextlib,io,json,pathlib,runpy
R=pathlib.Path(__file__).resolve().parent.parent
O=runpy.run_path(str(R/'tools/oracle.py'));P=runpy.run_path(str(R/'tools/index-proof.py'))
def proofs(g,d):
 a=g['repository'].get('.git/index');b=d['repository'].get('.git/index')
 if a is None or b is None:return 0
 return P['canonical_pair'](bytes.fromhex(a['hex']),bytes.fromhex(b['hex']),g.get('index_stat_proof',[]),d.get('index_stat_proof',[]))[2]
result={};texts=set();total=0
cases=json.load(open(R/'tests/cases.json'));counts={};mainproof=0
for c in cases:
 root=R/'target/runs'/c['name'];g=json.load(open(root/'git.json'));d=json.load(open(root/'den.json'))
 with contextlib.redirect_stdout(io.StringIO()):equal=O['equivalent'](g,d,c.get('comparison','loose-object-raw'))
 if equal:
  label='parity'
  if c.get('comparison')=='index-stat-proven':mainproof+=proofs(g,d)
 elif c.get('kind')=='version':
  assert d['status']==0 and d['stderr']=='' and bytes.fromhex(d['stdout'])==b'den 0.0.0 (built with wolf 0.2.35)\n'
  label='shape'
 else:
  feature=c.get('refusal_feature',c['args'][0]);suffix='' if c.get('refusal_style')=='feature-only' else f" ({c['lane']})"
  assert d['status']==2 and d['stdout']=='' and bytes.fromhex(d['stderr'])==f'den: not yet implemented: {feature}{suffix}\n'.encode(),c['name']
  before=json.load(open(root/'before.json'))
  assert d['repository']==before['repository'] and d['worktree']==before['worktree'],c['name']
  label='not-yet'
 counts[label]=counts.get(label,0)+1
 if c['args'][0]=='status':texts.add(g['stdout'])
result['main']={'cases':len(cases),'classes':counts,'canonicalized_tool_side_rows':mainproof};total+=mainproof
for family in ('worktree-oracle','commit-oracle'):
 for tier in ('native','release'):
  rows=json.load(open(R/f'target/{family}-{tier}.json'));assert all(x['equal'] for x in rows)
  count=sum(proofs(x['git'],x['den']) for x in rows)
  result[family+'-'+tier]={'cases':len(rows),'canonicalized_tool_side_rows':count};total+=count
  if family=='worktree-oracle':
   for x in rows:
    if x['case']['args'][0]=='status':texts.add(x['git']['stdout'])
for tier in ('native','release'):
 data=json.load(open(R/f'target/index-integration-{tier}.json'));result['index-'+tier]={'commands':len(data['rows']),'canonicalized_tool_side_rows':data['proof_rows']};total+=data['proof_rows']
result['distinct_status_stdout_texts']=len(texts)
result['canonicalized_tool_side_rows_total']=total
result['codec']=json.load(open(R/'target/codec-corpus/summary.json'))
print(json.dumps(result,indent=2))
(R/'target/vc03-counts.json').write_text(json.dumps(result,indent=2)+'\n')
