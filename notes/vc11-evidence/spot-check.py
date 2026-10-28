"""Manual independent spot-check of the raw-path importing-client evidence."""
import gzip,hashlib,json,pathlib
P=pathlib.Path(__file__).resolve().parent
bindings=json.loads((P/'final-counts.json').read_text())['captures']
body=b'raw\xff\nlast'
blob=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
for tier in ('native','release'):
 name=f'blame-{tier}.json.gz';raw=gzip.decompress((P/name).read_bytes())
 assert hashlib.sha256(raw).hexdigest()==bindings[name]['sha256']
 data=json.loads(raw)
 assert f'.git/objects/{blob[:2]}/{blob[2:]}' in data['fixture_states']['loose']
 for mode in ('loose','packed'):
  row=next(r for r in data['clients'] if r['mode']==mode and r['args']==['root',"b'raw\\xff'"])
  assert row['actual']==row['expected'] and row['unchanged']
  out=bytes.fromhex(row['actual']['stdout'])
  assert row['actual']['status']==0 and not row['actual']['stderr']
  assert b'filename "raw\\377"\n' in out
  assert b'\traw\xff\n' in out and out.endswith(b'\tlast\n')
  assert len([line for line in out.splitlines() if line.startswith(b'41186fe3bc2cfc83349dfb4c920095d51599db89 ')])==2
  print(tier,mode,'raw-byte-path/source lines and capture binding verified',flush=True)
print('independent raw blob SHA-1',blob,flush=True)
