"""Retain raw targeted/final captures; counts are derived, not inferred from exits."""
import gzip,hashlib,json,pathlib,sys
R=pathlib.Path('/work/den');P=R/'notes/vc14-evidence';P.mkdir(exist_ok=True)
patterns=['housekeeping*.json','validator-*.json','recovery-*.json','pack-write-*-expansion.json']
if '--final' in sys.argv:patterns += ['pack-write-native.json','pack-write-release.json','pack-command-*.json','pack-failure-*.json','pack-adversarial-*.json','*-checked.json']
manifest={};counts={};sizes=[]
for path in sorted({p for pattern in patterns for p in (R/'target').glob(pattern)}):
 data=path.read_bytes();dest=P/(path.name+'.gz');dest.write_bytes(gzip.compress(data,mtime=0))
 manifest[dest.name]={'raw_sha256':hashlib.sha256(data).hexdigest(),'gzip_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'raw_bytes':len(data)}
 try:x=json.loads(data)
 except json.JSONDecodeError:continue
 if isinstance(x,dict):
  item={key:len(x[key]) for key in ('rows','clients','processes','sizes','refusals','cases') if isinstance(x.get(key),list)}
  if isinstance(x.get('rows'),list):item['named_rows']=sum('named_refusal' in row for row in x['rows'])
  if 'verdict' in x:item['verdict']=x['verdict']
  counts[path.name]=item
  if 'sizes' in x:
   for row in x['sizes']:sizes.append(dict(report=path.name,**row))
(P/'capture-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
(P/'capture-counts.json').write_text(json.dumps(counts,sort_keys=True,indent=2)+'\n')
(P/'pack-sizes.json').write_text(json.dumps(sizes,sort_keys=True,indent=2)+'\n')
(P/'pack-sizes.tsv').write_text('report\tfixture\tmode\tobjects\tden\tgit\tratio\n'+''.join('\t'.join(str(row[key]) for key in ('report','fixture','mode','objects','den','git','ratio'))+'\n' for row in sizes))
print(json.dumps(counts,sort_keys=True,indent=2))
print('VC14 CAPTURES RETAINED',len(manifest),'size rows',len(sizes),flush=True)
