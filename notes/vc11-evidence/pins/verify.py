"""Fresh twice-read release/ref/archive/staged identities, unchanged toolchain."""
import hashlib,json,pathlib
P=pathlib.Path(__file__).resolve().parent
for name,version,expected in [('wolf','0.2.35','4cc4045bbbb605c07835bc4f32685953c784eeef4cd3139a48b457dfc90dad1a'),('lupin','0.1.56','ad703550ac4787e8e4bb26989d591a731410274d7332f2b4e8b9a64c878822cc')]:
 reads=[]
 for n in (1,2):
  meta=json.loads((P/f'vc11-{name}-release-{n}.json').read_text())
  asset=next(a for a in meta['assets'] if a['name']==f'{name}-{version}-x86_64-unknown-linux-gnu.tar.gz')
  assert asset['digest']=='sha256:'+expected,(name,asset)
  reads.append((asset['id'],asset['name'],asset['digest']))
  tag=(P/f'{name}-tag-{n}.txt').read_text();assert tag
 assert reads[0]==reads[1]
 assert (P/f'{name}-tag-1.txt').read_bytes()==(P/f'{name}-tag-2.txt').read_bytes()
 archive=P/'archives'/reads[0][1]
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
 print(name,reads[0],flush=True)
for kind in ('archive','staged'):
 assert (P/f'{kind}-shas-1.txt').read_bytes()==(P/f'{kind}-shas-2.txt').read_bytes()
print('pins: release assets, tag refs, archives and staged files agree across both reads',flush=True)
