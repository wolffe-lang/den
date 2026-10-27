"""Derive vc09 totals from completed captures; retain full compressed records."""
import gzip,hashlib,json,pathlib,shutil
r=pathlib.Path(__file__).resolve().parents[2]; t=r/'target'; out=r/'notes/vc09-evidence'
report={'tiers':{},'captures':{}}
for tier in ('native','release'):
 paths={
  'structural':t/f'pack-{tier}/results.json',
  'interop':t/f'pack-interop-{tier}/results.json',
  'history':t/f'history-{tier}-packed.json',
  'refs':t/f'refs-oracle-{tier}-packed.json',
  'refs_scope':t/f'refs-unsupported-{tier}-packed.json',
  'merge':t/f'merge-{tier}-packed.json',
  'replay':t/f'replay-{tier}-packed.json'}
 counts={}
 for name,p in paths.items():
  b=p.read_bytes(); x=json.loads(b)
  dest=out/f'{name}-{tier}.json.gz'
  with dest.open('wb') as f:
   with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as g: g.write(b)
  report['captures'][dest.name]={'sha256':hashlib.sha256(b).hexdigest(),'uncompressed_bytes':len(b)}
  if name=='structural':
   assert all(row['ok'] for row in x); counts[name]={'exact':len(x),'total':len(x)}
  elif name=='interop':
   assert x['objects']==x['exact'] and all(row['equal'] for row in x['rows'])
   counts[name]={'objects':x['objects'],'exact':x['exact'],'fixtures':len(x['inventories']),'entry_types':{k:sum(v['entry_types'][k] for v in x['inventories']) for k in ('1','2','3','4','6','7')}}
  elif name=='history':
   assert not x['failures'] and x['exact']==x['total']; counts[name]={'exact':x['exact'],'total':x['total'],'named':len(x['named_refusals']),'clients':x['external_clients']}
  elif name=='refs':
   assert all(row['equal'] for row in x); counts[name]={'exact':len(x),'total':len(x)}
  elif name=='refs_scope': counts[name]={'named':len(x)}
  elif name=='merge':
   parity=[row for row in x if 'equal' in row]; assert all(row['equal'] for row in parity)
   counts[name]={'exact':len(parity),'named':len(x)-len(parity),'total':len(x)}
  else:
   assert all(row['verified'] for row in x); parity=[row for row in x if row['equal']]
   counts[name]={'exact_scenarios':len(parity),'named':len(x)-len(parity),'total':len(x),'process_comparisons':sum(len(row['den']) for row in x)}
 report['tiers'][tier]=counts
checked=[json.loads(line) for line in (t/'pack-checked.json').read_text().splitlines() if line.startswith('{')]
assert len(checked)==1 and checked[0]['verdict']=='exit(0)'
shutil.copyfile(t/'pack-checked.json',out/'pack-checked.json')
shutil.copyfile(t/'dist/sums.txt',out/'static-sums.txt')
report['checked_verdict']=checked[0]['verdict']; report['zero_new_skips']=True
(out/'final-counts.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
