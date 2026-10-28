"""Compare before/after cost witnesses and retain the complete replacement pack proof."""
import gzip,hashlib,json,pathlib
R=pathlib.Path('/work/den');T=R/'target';O=R/'notes/vc13-evidence'
report={'captures':{},'timing_rows':[],'tiers':{},'inputs':{}}
def load(path):
 raw=path.read_bytes();name='performance-'+str(path.relative_to(T)).replace('/','-')+'.gz'
 with (O/name).open('wb') as file:
  with gzip.GzipFile(filename='',mode='wb',fileobj=file,mtime=0) as out:out.write(raw)
 report['captures'][str(path.relative_to(R))]={'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
 return json.loads(raw)
before={};before_sizes={}
for kind in ('ofs','ref'):
 data=load(T/f'pack-write-native-before-vc09-14-{kind}.json')
 assert len(data['sizes'])==3 and all(r['objects']==1002 for r in data['sizes'])
 for row in data['timings']:before[(row['fixture'],row['mode'])]=row
 for row in data['sizes']:before_sizes[(row['fixture'],row['mode'])]=row
after=load(T/'pack-write-native-after-vc09-14.json')
assert len(after['sizes'])==6 and all(r['objects']==1002 for r in after['sizes'])
assert all(r==before_sizes[(r['fixture'],r['mode'])] for r in after['sizes']), 'profile proof changed'
for row in after['timings']:
 old=before[(row['fixture'],row['mode'])]
 report['timing_rows'].append({'fixture':row['fixture'],'mode':row['mode'],'objects':row['objects'],'before_seconds':old['row_seconds'],'after_seconds':row['row_seconds'],'speedup':old['row_seconds']/row['row_seconds'],'before_setup_seconds':old['setup_seconds'],'after_setup_seconds':row['setup_seconds'],'before_snapshot_seconds':old['costs']['snapshot'],'after_snapshot_seconds':row['costs']['snapshot'],'before_writer_seconds':old['costs']['pack-write-client'],'after_writer_seconds':row['costs']['pack-write-client'],'before_reader_seconds':old['costs']['pack-client'],'after_reader_seconds':row['costs']['pack-client'],'before_git_seconds':old['costs']['git-cat-file'],'after_git_seconds':row['costs']['git-cat-file']})
assert len(report['timing_rows'])==6
historical=json.loads((O/'final-counts.json').read_text())
for tier in ('native','release'):
 writer=load(T/f'pack-write-{tier}.json')
 assert not writer['fixture_filter'] and not writer['core_only']
 assert writer['sizes']==historical['writer'][tier]['sizes'],('size or object inventory changed',tier)
 assert len(writer['sizes'])==174 and sum(r['objects'] for r in writer['sizes'])==14055
 assert all(r['status']==0 for r in writer['processes'])
 commands=load(T/f'pack-command-{tier}.json');assert all(r['git']==r['den'] for r in commands['rows'])
 failures=load(T/f'pack-failure-{tier}.json')
 adversarial=load(T/f'pack-adversarial-{tier}.json');assert len(adversarial['cases'])==22
 interop=load(T/f'pack-interop-{tier}/results.json');assert interop['exact']==interop['objects']==2442
 structural=load(T/f'pack-{tier}/results.json');assert len(structural)==141 and all(r['ok'] for r in structural)
 report['tiers'][tier]={'pairs':len(writer['sizes']),'objects':sum(r['objects'] for r in writer['sizes']),'processes':len(writer['processes']),'exact_commands':len(commands['rows']),'named_commands':len(commands['refusals']),'publication_processes':len(failures),'adversarial_cases':len(adversarial['cases']),'adversarial_processes':len(adversarial['rows']),'legacy_single_client_objects':interop['objects'],'legacy_structural_inputs':len(structural),'size_table_identical':True}
vectors=load(T/'pack-batch-vectors.json');assert len(vectors)==24 and all(r['verified'] for r in vectors)
report['batch_vectors']={'valid':sum(r['accepted'] for r in vectors),'rejected':sum(not r['accepted'] for r in vectors)}
checked=load(T/'pack-write-checked.json');assert checked['verdict']=='exit(0)'
report['checked_verdict']=checked['verdict']
for name in ('tools/pack-write-test.py','tools/pack-batch.py','tools/pack-batch-test.py','tools/check-pack-write','probes/pack-client/main.lu','ci/tiers-test.py','.github/workflows/ci.yml','wolf-toolchain.toml','den-oracle.toml'):
 report['inputs'][name]=hashlib.sha256((R/name).read_bytes()).hexdigest()
(O/'performance-counts.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('captures','inputs')},indent=2))
