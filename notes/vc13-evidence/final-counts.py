"""Retain complete captures and derive vc13 plus inherited counts after the sole gate."""
import gzip,hashlib,json,pathlib,sys,tarfile
R=pathlib.Path(__file__).resolve().parents[2];T=R/'target';O=R/'notes/vc13-evidence'
# Reuse the reviewed vc12 accounting without editing its historical script.
source=R/'notes/vc12-evidence/final-counts.py'
text=source.read_text().replace("OUT=R/'notes/vc12-evidence'","OUT=R/'notes/vc13-evidence'").replace("OUT/'final-counts.json'","OUT/'inherited-counts.json'")
ns={'__file__':str(source),'__name__':'__main__'};exec(compile(text,str(source),'exec'),ns)
report={'inherited':ns['report'],'writer':{},'commands':{},'failures':{},'adversarial':{},'captures':{}}
known={v['sha256']:k for k,v in ns['report']['captures'].items()}
def retain(p,decode=True):
 raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest();dest=known.get(digest)
 if dest is None:
  dest='component-'+p.name+'.gz'
  with (O/dest).open('wb') as f:
   with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(raw)
  known[digest]=dest
 report['captures'][str(p.relative_to(R))]={'capture':dest,'sha256':digest,'bytes':len(raw)}
 return json.loads(raw) if decode else None
for tier in ('native','release'):
 x=retain(T/f'pack-write-{tier}.json');assert not x['core_only'];sizes=x['sizes']
 assert len(sizes)==174 and all(r['ratio']<=1.5 for r in sizes)
 assert all(r['status']==0 for r in x['processes'])
 report['writer'][tier]={'sources':len({r['fixture'] for r in sizes}),'pairs':len(sizes),'objects':sum(r['objects'] for r in sizes),'processes':len(x['processes']),'sizes':sizes,'max_ratio':{mode:max(r['ratio'] for r in sizes if r['mode']==mode) for mode in ('none','ofs','ref')}}
 x=retain(T/f'pack-command-{tier}.json');assert all(r['git']==r['den'] for r in x['rows']);assert all(r['den']['status']==2 for r in x['refusals'])
 report['commands'][tier]={'exact':len(x['rows']),'named':len(x['refusals'])}
 x=retain(T/f'pack-failure-{tier}.json');report['failures'][tier]={'processes':len(x),'failure_repeat_cases':8,'cli_publications':1}
 x=retain(T/f'pack-adversarial-{tier}.json');assert len(x['cases'])==22
 chains=[r for r in x['cases'] if r['case'].startswith('chain-')];assert len(chains)==2 and all(r['max_depth']==50 for r in chains)
 report['adversarial'][tier]={'cases':len(x['cases']),'processes':len(x['rows']),'chains':chains}
checked=[json.loads(line) for line in (T/'pack-write-checked.json').read_text().splitlines() if line.startswith('{')]
assert len(checked)==1 and checked[0]['verdict']=='exit(0)'
retain(T/'pack-write-checked.json')
# Keep other final top-level component captures, avoiding content duplicates and
# known exploratory pre-gate measurements. Every retained source is listed.
for p in sorted(T.glob('*.json')):
 if p.name in ('pack-measure.json','stash-measure.json'):continue
 if str(p.relative_to(R)) not in report['captures']:retain(p,decode=False)
main={};cases=json.loads((R/'tests/cases.json').read_text())
with tarfile.open(O/'main-captures.tar.gz','w:gz') as tar:
 for case in cases:
  for name in ('before.json','git.json','den.json'):
   p=T/'runs'/case['name']/name;raw=p.read_bytes();key=f'{case["name"]}/{name}'
   main[key]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};tar.add(p,arcname=key,recursive=False)
report['main_captures']=main
(O/'final-counts.json').write_text(json.dumps(report,indent=2)+'\n')
rows=report['writer']['native']['sizes'];other=report['writer']['release']['sizes'];assert rows==other
lines=['fixture\tmode\tden_bytes\tgit_bytes\tratio\tbaseline\tdefault_ratio']
for row in rows:lines.append('\t'.join(str(row[k]) for k in ('fixture','mode','den','git','ratio','baseline','default_ratio')))
(O/'pack-sizes.tsv').write_text('\n'.join(lines)+'\n')
print('VC13 COUNTS',json.dumps({k:v for k,v in report.items() if k in ('commands','failures','adversarial')}),flush=True)
print('VC13 WRITER COUNTS',json.dumps({tier:{k:v for k,v in result.items() if k!='sizes'} for tier,result in report['writer'].items()}),flush=True)
print('VC13 MAIN CAPTURES',len(main),'components',len(report['captures']),flush=True)
