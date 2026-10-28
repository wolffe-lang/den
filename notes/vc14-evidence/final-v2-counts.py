"""Derive final-v2 counts from bank-bound captures; never rewrite a capture."""
import hashlib,json,pathlib
R=pathlib.Path('/work/den');T=R/'target';O=R/'notes/vc14-evidence';H='4cd291ef291242b7d2c215aba1b08979834df554'
B=pathlib.Path('/bank')/H
bank=json.loads((B/'manifest.json').read_text());bound={r['source']:r for r in bank['files']}
report=dict(head=H,tiers={},captures={})
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def load(p):
 row=bound[str(p)];digest=sha(p);assert digest==row['uncompressed_sha256']
 report['captures'][str(p.relative_to(R))]=dict(sha256=digest,bytes=p.stat().st_size,bank=row['path'])
 return json.loads(p.read_text())
def count(kind,x):
 if kind=='history':
  assert not x['failures'] and x['exact']==x['total'];return dict(exact=x['exact'],total=x['total'],named=len(x['named_refusals']),clients=x['external_clients'])
 if kind=='refs':
  assert all(r['equal'] for r in x);return dict(exact=len(x),total=len(x))
 if kind=='refs_scope':return dict(named=len(x))
 if kind=='merge':
  parity=[r for r in x if 'equal' in r];assert all(r['equal'] for r in parity);return dict(exact=len(parity),named=len(x)-len(parity),total=len(x))
 assert all(r['verified'] for r in x)
 parity=[r for r in x if r['equal']];scopes=len(x)-len(parity);processes=sum(len(r['den']) for r in x)
 return dict(exact_scenarios=len(parity),named=scopes,total=len(x),process_captures=processes,exact_process_comparisons=processes-scopes)
for tier in ('native','release'):
 result={};s=load(T/f'stash-{tier}.json');assert not s['failures'] and s['zero_skips'] and all(r['verified'] for r in s['rows']);result['stash']={}
 for mode in ('loose','packed'):
  rows=[r for r in s['rows'] if r['mode']==mode];parity=[r for r in rows if r['disposition']=='parity'];named=[r for r in rows if r['disposition']!='parity']
  result['stash'][mode]=dict(exact_cases=len(parity),exact_processes=sum(r['processes'] for r in parity),named=len(named),named_process_captures=sum(r['processes'] for r in named),corpus_cases=sum(r['fixture'].startswith('corpus:') for r in parity))
 c=load(T/f'stash-api-{tier}.json');assert not c['failures'] and all(r['ok'] for r in c['rows']);result['stash_client']={mode:sum(r['mode']==mode for r in c['rows']) for mode in ('loose','packed')}
 for kind in ('blame','revision'):
  x=load(T/f'{kind}-{tier}.json');assert not x['failures'] and x['zero_skips'];assert all(r['expected']==r['actual'] and r['unchanged'] for r in x['rows']+x['clients']+x['named_scope'])
  result[kind]={mode:dict(exact=sum(r['mode']==mode for r in x['rows']),clients=sum(r['mode']==mode for r in x['clients']),named=sum(r['mode']==mode for r in x['named_scope'])) for mode in ('loose','packed')}
 for mode in ('loose','packed'):
  suffix='-packed' if mode=='packed' else ''
  paths=dict(history=T/f'history-{tier}{suffix}.json',refs=T/f'refs-oracle-{tier}{suffix}.json',refs_scope=T/f'refs-unsupported-{tier}{suffix}.json',merge=T/f'merge-{tier}{suffix}.json',replay=T/f'replay-{tier}{suffix}.json')
  result[mode]={kind:count(kind,load(p)) for kind,p in paths.items()}
 x=load(T/f'pack-{tier}/results.json');assert all(r['ok'] for r in x);result['pack_structural']=len(x)
 x=load(T/f'pack-interop-{tier}/results.json');assert x['objects']==x['exact'] and all(r['equal'] for r in x['rows']);result['pack_interop']=dict(exact=x['exact'],objects=x['objects'],fixtures=len(x['inventories']),entry_types={k:sum(r['entry_types'][k] for r in x['inventories']) for k in ('1','2','3','4','6','7')})
 x=load(T/f'pack-write-{tier}.json');assert not x['core_only'] and not x['fixture_filter'];assert all(r['status']==0 for r in x['processes']);sizes=x['sizes'];assert all(r['ratio']<=1.5 for r in sizes)
 result['writer']=dict(sources=len({r['fixture'] for r in sizes}),pairs=len(sizes),objects=sum(r['objects'] for r in sizes),processes=len(x['processes']),sizes=sizes,max_ratio={m:max(r['ratio'] for r in sizes if r['mode']==m) for m in ('none','ofs','ref')})
 x=load(T/f'pack-command-{tier}.json');assert all(r['git']==r['den'] for r in x['rows']);assert all(r['den']['status']==2 for r in x['refusals']);result['pack_commands']=dict(exact=len(x['rows']),named=len(x['refusals']))
 x=load(T/f'pack-failure-{tier}.json');result['pack_publication_processes']=len(x)
 x=load(T/f'pack-adversarial-{tier}.json');result['pack_adversarial']=dict(cases=len(x['cases']),processes=len(x['rows']),chains=[r for r in x['cases'] if r['case'].startswith('chain-')])
 x=load(T/f'housekeeping-{tier}-final.json');exact=[r for r in x['rows'] if 'named_refusal' not in r];named=[r for r in x['rows'] if 'named_refusal' in r]
 assert all(tuple(r['git'][k] for k in ('stdout','stderr','status'))==tuple(r['den'][k] for k in ('stdout','stderr','status')) and r['git_objects']['stdout']==r['den_objects']['stdout'] for r in exact)
 assert all(r['den']['status']==2 and r['den']['before']==r['den']['after'] for r in named);result['housekeeping']=dict(exact=len(exact),named=len(named),rows=len(x['rows']),max_den_seconds=max(r['den']['seconds'] for r in x['rows']))
 x=load(T/f'validator-{tier}-final.json');assert all(r['git']==r['den'] and r['before']==r['den']['state'] for r in x['rows']);assert all(r['den']['status']==0 and r['before']==r['den']['state']==r['git']['state'] for r in x['clients']);result['validator']=dict(exact=len(x['rows']),clients=len(x['clients']))
 x=load(T/f'recovery-{tier}-final.json');result['recovery']=dict(process_captures=len(x['rows']),option_refusals=len(x['refusals']),interruption_phases=5)
 report['tiers'][tier]=result
report['checked']={}
for p in sorted(T.glob('*checked*.json')):
 if 'targeted' in p.name or 'parent-slot' in p.name:continue
 try:x=load(p)
 except json.JSONDecodeError:continue
 if isinstance(x,dict) and 'verdict' in x:report['checked'][p.name]=x['verdict']
log=pathlib.Path('/lane/final-v2.log').read_text();main=[]
for line in log.splitlines():
 if not line.startswith('{'):continue
 try:x=json.loads(line)
 except ValueError:continue
 if isinstance(x,dict) and 'parity' in x and all(isinstance(v,int) for v in x.values()) and sum(x.values())==190:main.append(x)
assert len(main)==1;report['main']=main[0]
assert 'VC14 GAUNTLET-V2 EXIT 0' in log and 'VC14 FUNCTIONAL INPUTS UNCHANGED 392' in log and 'VC14 FINAL-V2 EXIT 0' in log
report['static_sums']=(T/'dist/sums.txt').read_text()
# Census other component records without mislabelling their rows as parity.
census={}
def shape(x):
 if isinstance(x,list):
  out={'rows':len(x)}
  if x and isinstance(x[0],dict):
   out['row_keys']=sorted(x[0]);out['boolean_tallies']={key:sum(r.get(key) is True for r in x if isinstance(r,dict)) for key in ('equal','ok','verified','unchanged') if key in x[0]}
  return out
 if isinstance(x,dict):
  out={k:v for k,v in x.items() if isinstance(v,(bool,int,float)) or k=='verdict'}
  out['collections']={k:len(v) for k,v in x.items() if isinstance(v,(list,dict)) and k not in ('contents','states')}
  for k in ('summary','counts','results'):
   if isinstance(x.get(k),dict):out[k]={a:b for a,b in x[k].items() if isinstance(b,(bool,int,float,str)) and len(str(b))<200}
  return out
 return {'type':type(x).__name__}
for p in sorted(T.glob('*.json')):
 if any(s in p.name for s in ('housekeeping','validator-','recovery-','pack-write-','parent-slot','measure')):continue
 try:x=load(p)
 except json.JSONDecodeError:continue
 census[p.name]=shape(x)
for tier in ('native','release'):
 for p in sorted((T/f'diffbinary-{tier}').glob('summary*.json')):census[str(p.relative_to(T))]=shape(load(p))
report['component_census']=census
for p in sorted(set(T.glob('*/results.json')) | set(T.glob('*/summary*.json')) | set((T/'codec').glob('*.json')) | {T/'config/checked.json'}):
 if not p.exists():continue
 census[str(p.relative_to(T))]=shape(load(p))
report['log_summaries']={'codec_vectors':[],'codec_corpus':[],'codec_fuzz':[],'config_cli':[],'hunks':[],'scorer':[]}
for line in log.splitlines():
 if line.startswith('PASS config '):report['log_summaries']['config_cli'].append(line)
 if line.startswith('hunks:'):report['log_summaries']['hunks'].append(line)
 if line.startswith('delta:'):report['log_summaries']['scorer'].append(line)
 if not line.startswith('{'):continue
 try:value=json.loads(line)
 except ValueError:continue
 if not isinstance(value,dict):continue
 if 'zlib_compile' in value and 'vectors' in value:report['log_summaries']['codec_vectors'].append(value)
 if 'counts' in value and 'zlib' in value and 'sizes' in value:report['log_summaries']['codec_corpus'].append(value)
 if 'rounds' in value and 'input_sha256' in value:report['log_summaries']['codec_fuzz'].append(value)
assert all(len(report['log_summaries'][k])==2 for k in ('codec_vectors','codec_corpus','codec_fuzz','hunks')), {k:len(v) for k,v in report['log_summaries'].items()}
for tier in ('native','release'):
 invocations=[int(line.split()[3]) for line in report['log_summaries']['config_cli'] if line.split()[2]==tier+':']
 assert invocations and len(set(invocations))==1
 report['tiers'][tier]['config_cli']=dict(checks_per_invocation=invocations[0],invocations=len(invocations),oracle_parity=False)
report['final_log']=bound['/lane/final-v2.log'];assert sha(pathlib.Path('/lane/final-v2.log'))==report['final_log']['uncompressed_sha256']
for tier in ('native','release'):
 scorer=load(T/f'rename-scorer-{tier}.json')
 assert all(r['ok'] for suite in scorer['suites'] for r in suite['rows'])
 report['tiers'][tier]['scorer_suites']=[dict(suite=suite['suite'],total=len(suite['rows']),exact=sum(r['ok'] for r in suite['rows']),input_sha256=suite['input_sha256']) for suite in scorer['suites']]
(O/'final-v2-counts.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
lines=['tier\tfixture\tmode\tobjects\tden\tgit\tratio\tbaseline\tdefault_ratio']
for tier,result in report['tiers'].items():
 for row in result['writer']['sizes']:lines.append(tier+'\t'+'\t'.join(str(row[k]) for k in ('fixture','mode','objects','den','git','ratio','baseline','default_ratio')))
(O/'final-v2-pack-sizes.tsv').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('captures','component_census','tiers')},indent=2))
for tier,result in report['tiers'].items():print('TIER',tier,json.dumps({k:({a:b for a,b in v.items() if a!='sizes'} if k=='writer' else v) for k,v in result.items()},sort_keys=True))
print('COMPONENT CENSUS',json.dumps(census,sort_keys=True))
