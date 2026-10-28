import hashlib,json,pathlib,tarfile,tomllib
R=pathlib.Path('/work/den');P=R/'notes/vc14-evidence/pins'
expected=[('wolf-lang','wolf','0.2.35','4cc4045bbbb605c07835bc4f32685953c784eeef4cd3139a48b457dfc90dad1a'),('wolf-interp','lupin','0.1.56','ad703550ac4787e8e4bb26989d591a731410274d7332f2b4e8b9a64c878822cc')]
for repo,tool,version,digest in expected:
 filename=f'{tool}-{version}-x86_64-unknown-linux-gnu.tar.gz';a=pathlib.Path('/archives')/filename;ids=[]
 for n in (1,2):
  release=json.loads((P/f'{repo}-release-{n}.json').read_text());asset=next(x for x in release['assets'] if x['name']==filename)
  assert asset['digest']=='sha256:'+digest;ids.append((asset['id'],asset['name'],asset['digest']))
  assert hashlib.sha256(a.read_bytes()).hexdigest()==digest
 assert ids[0]==ids[1]
 for kind in ('ref','tag'):
  assert json.loads((P/f'{repo}-{kind}-1.json').read_text())==json.loads((P/f'{repo}-{kind}-2.json').read_text())
 assert json.loads((P/f'{repo}-tag-1.json').read_text())['object']['sha']==tomllib.loads((R/'wolf-toolchain.toml').read_text())[tool]['rev']
 with tarfile.open(a) as archive:
  member=next(m for m in archive if m.isfile() and m.name.endswith('/'+tool))
  data=archive.extractfile(member).read();assert hashlib.sha256(data).digest()==hashlib.sha256((R/'.wolf-bin'/tool).read_bytes()).digest()
  if tool=='wolf':
   rt=next(m for m in archive if m.isfile() and m.name.endswith('/libwolf_rt.a'))
   assert hashlib.sha256(archive.extractfile(rt).read()).digest()==hashlib.sha256((R/'.wolf-bin/libwolf_rt.a').read_bytes()).digest()
 print(tool,ids[0],flush=True)
assert (R/'.wolf-bin/std/STD-REV').read_text().strip()=='2386522eb059cca5a84108562c2c0a0e72345d34'
for n in (1,2):
 files=sorted(p for p in (R/'.wolf-bin').rglob('*') if p.is_file())
 manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 oracle=next((R/'target/oracle').glob('*/root/opt/git/bin/git'));manifest['oracle']=hashlib.sha256(oracle.read_bytes()).hexdigest()
 assert manifest['oracle']=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
 (P/f'staged-oracle-{n}.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
assert (P/'staged-oracle-1.json').read_bytes()==(P/'staged-oracle-2.json').read_bytes()
print('VC14 PINS VERIFIED twice-read metadata, archives, staged binaries/runtime/std and oracle',flush=True)
