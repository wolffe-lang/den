"""Derive vc12 counts from complete retained captures, never from expected totals."""
import gzip,hashlib,json,pathlib,shutil,sys
R=pathlib.Path(__file__).resolve().parents[2];T=R/'target';OUT=R/'notes/vc12-evidence'
report=dict(tiers={},captures={})
def load(name,p):
 raw=p.read_bytes();dest=OUT/(name+'.json.gz')
 with dest.open('wb') as f:
  with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(raw)
 report['captures'][dest.name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
 return json.loads(raw)
def count(kind,x):
 if kind=='history':
  assert not x['failures'] and x['exact']==x['total']
  return dict(exact=x['exact'],total=x['total'],named=len(x['named_refusals']),clients=x['external_clients'])
 if kind=='refs':
  assert all(r['equal'] for r in x);return dict(exact=len(x),total=len(x))
 if kind=='refs_scope':return dict(named=len(x))
 if kind=='merge':
  parity=[r for r in x if 'equal' in r];assert all(r['equal'] for r in parity)
  return dict(exact=len(parity),named=len(x)-len(parity),total=len(x))
 assert all(r['verified'] for r in x)
 parity=[r for r in x if r['equal']];scopes=len(x)-len(parity);processes=sum(len(r['den']) for r in x)
 return dict(exact_scenarios=len(parity),named=scopes,total=len(x),process_captures=processes,exact_process_comparisons=processes-scopes)
for tier in ('native','release'):
 result={}
 s=load('stash-'+tier,T/f'stash-{tier}.json')
 assert not s['failures'] and s['zero_skips'] and all(r['verified'] for r in s['rows'])
 result['stash']={}
 for mode in ('loose','packed'):
  rows=[r for r in s['rows'] if r['mode']==mode];parity=[r for r in rows if r['disposition']=='parity'];named=[r for r in rows if r['disposition']!='parity']
  result['stash'][mode]=dict(exact_cases=len(parity),exact_processes=sum(r['processes'] for r in parity),named=len(named),
   named_process_captures=sum(r['processes'] for r in named),corpus_cases=sum(r['fixture'].startswith('corpus:') for r in parity),
   stash_cases=sum(r['name'].startswith(('push','list','apply','pop','drop','clear')) for r in parity),
   notes_cases=sum(r['name'].startswith('notes') for r in parity),
   corpus_stash=sum(r['name'].startswith('corpus-stash') for r in parity),corpus_notes=sum(r['name'].startswith('corpus-notes') for r in parity))
 c=load('stash-api-'+tier,T/f'stash-api-{tier}.json')
 assert not c['failures'] and all(r['ok'] for r in c['rows'])
 result['stash_client']={mode:dict(exact=sum(r['mode']==mode for r in c['rows'])) for mode in ('loose','packed')}
 for kind in ('blame','revision'):
  x=load(kind+'-'+tier,T/f'{kind}-{tier}.json')
  assert not x['failures'] and x['zero_skips']
  assert all(r['expected']==r['actual'] and r['unchanged'] for r in x['rows']+x['clients']+x['named_scope'])
  result[kind]={mode:dict(exact=sum(r['mode']==mode for r in x['rows']),clients=sum(r['mode']==mode for r in x['clients']),named=sum(r['mode']==mode for r in x['named_scope'])) for mode in ('loose','packed')}
 for mode in ('loose','packed'):
  suffix='-packed' if mode=='packed' else ''
  paths=dict(history=T/f'history-{tier}{suffix}.json',refs=T/f'refs-oracle-{tier}{suffix}.json',refs_scope=T/f'refs-unsupported-{tier}{suffix}.json',merge=T/f'merge-{tier}{suffix}.json',replay=T/f'replay-{tier}{suffix}.json')
  result[mode]={kind:count(kind,load(f'{kind}-{tier}-{mode}',p)) for kind,p in paths.items()}
 structural=load('structural-'+tier,T/f'pack-{tier}/results.json');assert all(r['ok'] for r in structural)
 result['pack_structural']=dict(exact=len(structural),total=len(structural))
 interop=load('interop-'+tier,T/f'pack-interop-{tier}/results.json');assert interop['objects']==interop['exact'] and all(r['equal'] for r in interop['rows'])
 result['pack_interop']=dict(exact=interop['exact'],objects=interop['objects'],fixtures=len(interop['inventories']),entry_types={k:sum(r['entry_types'][k] for r in interop['inventories']) for k in ('1','2','3','4','6','7')})
 report['tiers'][tier]=result
units=('stash','blame','revision','pack','pretty','walk','refs','reflog','sequencer')
for unit in units:
 p=T/f'{unit}-checked.json';rows=[json.loads(line) for line in p.read_text().splitlines() if line.startswith('{')]
 assert len(rows)==1 and rows[0]['verdict']=='exit(0)',(unit,rows)
 shutil.copyfile(p,OUT/p.name)
report['checked_units']=list(units);report['zero_new_skips']=True
def summary(line):
 try:value=json.loads(line)
 except ValueError:return None
 return value if isinstance(value,dict) and value and all(isinstance(v,int) for v in value.values()) and 'parity' in value else None
main=[summary(line) for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if line.startswith('{"')]
main=[m for m in main if m and sum(m.values())==190]
assert len(main)==1,main
report['main']=main[0]
shutil.copyfile(T/'dist/sums.txt',OUT/'static-sums.txt')
(OUT/'final-counts.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(tiers=report['tiers'],main=report['main']),indent=2),flush=True)
