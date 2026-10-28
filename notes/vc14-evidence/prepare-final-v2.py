import hashlib,json,pathlib,shutil
R=pathlib.Path('/work/den');B=pathlib.Path('/evidence-bank')
manifest=json.loads((B/'manifest.json').read_text());rows={r['source']:r for r in manifest['files']}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
for family in ('housekeeping','validator','recovery'):
 for tier in ('native','release'):
  stem=family+'-'+tier+'-final';report=R/'target'/(stem+'.json');row=rows[str(report)]
  assert sha(report)==row['uncompressed_sha256']
  bank=B/pathlib.Path(row['path']).relative_to('/home/mfwolffe/lanes/vc14/evidence-bank')
  assert sha(bank)==row['sha256']==row['sha256_second_read']
  fixture=R/'target'/stem
  assert fixture.is_dir() and not fixture.is_symlink()
  print('VC14 VERIFIED BANK BEFORE REBUILD',stem,flush=True)
  shutil.rmtree(fixture)
