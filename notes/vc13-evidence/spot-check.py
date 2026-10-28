"""Independent hand spot-check of the retained worst-ratio REF pack, not production code."""
import base64,gzip,hashlib,json,pathlib,struct,zlib
R=pathlib.Path(__file__).resolve().parents[2];P=R/'notes/vc13-evidence'
counts=json.loads((P/'final-counts.json').read_text())
path=P/counts['captures']['target/pack-write-native.json']['capture']
raw=gzip.decompress(path.read_bytes());assert hashlib.sha256(raw).hexdigest()==counts['captures']['target/pack-write-native.json']['sha256']
d=json.loads(raw)
record=next(r for r in d['processes'] if len(r['argv'])>2 and r['argv'][1]=='verify-pack' and any('/similar-ref/.git/' in s for s in r['argv']))
assert record['status']==0 and record['stderr']==''
state=d['states'][record['state']]
idxpath=next(k for k in state if k.startswith('.git/objects/pack/pack-') and k.endswith('.idx'))
packpath=idxpath[:-4]+'.pack'
def content(key):
 digest=state[key]['content'];data=base64.b64decode(d['contents'][digest]);assert hashlib.sha256(data).hexdigest()==digest;return data
idx=content(idxpath);data=content(packpath)
assert hashlib.sha1(idx[:-20]).digest()==idx[-20:]
assert hashlib.sha1(data[:-20]).digest()==data[-20:]==idx[-40:-20]
assert data[:8]==b'PACK\0\0\0\2'
count=struct.unpack_from('>I',idx,1028)[0];assert count==24==struct.unpack_from('>I',data,8)[0]
ids=[idx[1032+20*i:1052+20*i].hex() for i in range(count)]
crcs=struct.unpack_from('>'+str(count)+'I',idx,1032+20*count)
offsets=struct.unpack_from('>'+str(count)+'I',idx,1032+24*count)
assert all(o<2**31 for o in offsets)
entries={name:(offsets[i],crcs[i]) for i,name in enumerate(ids)};cache={}
def varint(src,pos):
 n=0;shift=0
 while True:
  b=src[pos];pos+=1;n|=(b&127)<<shift
  if b<128:return n,pos
  shift+=7;assert shift<64
def decode(name):
 if name in cache:return cache[name]
 offset,crc=entries[name];end=min([x for x in offsets if x>offset]+[len(data)-20]);entry=data[offset:end]
 assert zlib.crc32(entry)==crc
 b=entry[0];kind=(b>>4)&7;size=b&15;pos=1;shift=4
 while b&128:
  b=entry[pos];pos+=1;size|=(b&127)<<shift;shift+=7
 base=''
 if kind==7:base=entry[pos:pos+20].hex();pos+=20
 assert kind in (3,7)
 inflater=zlib.decompressobj();plain=inflater.decompress(entry[pos:]);assert inflater.eof and not inflater.unused_data and len(plain)==size
 depth=0
 if base:
  body,depth=decode(base);depth+=1
  base_size,p=varint(plain,0);target_size,p=varint(plain,p);assert base_size==len(body);result=bytearray()
  while p<len(plain):
   op=plain[p];p+=1;assert op
   if op&128:
    start=length=0
    for i in range(4):
     if op&(1<<i):start|=plain[p]<<(8*i);p+=1
    for i in range(3):
     if op&(1<<(i+4)):length|=plain[p]<<(8*i);p+=1
    length=length or 65536;assert start+length<=len(body);result+=body[start:start+length]
   else:result+=plain[p:p+op];p+=op
  assert len(result)==target_size;plain=bytes(result)
 assert hashlib.sha1(b'blob '+str(len(plain)).encode()+b'\0'+plain).hexdigest()==name
 cache[name]=(plain,depth);return cache[name]
for name in ids:decode(name)
name=max(ids,key=lambda n:cache[n][1]);body,depth=cache[name]
client=next(r for r in d['processes'] if r['argv'][0].endswith('/pack-client') and '/similar-ref/.git' in r['argv'][1] and r['argv'][2]==name)
assert client['status']==0 and client['stderr']=='' and bytes.fromhex(client['stdout'])==f'blob {len(body)} {name}\n'.encode()+body
packed_state=client['state'];git=next(r for r in d['processes'] if r['argv'][1:]==['cat-file','blob',name] and r['state']==packed_state)
assert git['status']==0 and git['stderr']=='' and bytes.fromhex(git['stdout'])==body
row=next(r for r in counts['writer']['native']['sizes'] if r['fixture']=='similar' and r['mode']=='ref')
assert len(data)==row['den']==1461 and row['git']==1044 and len(data)/1044==row['ratio']
print('SPOT CHECK PASS: similar-ref; independent idx/pack SHA1, CRC32, REF delta reconstruction, all 24 canonical OIDs')
print('Selected deepest object',name,'depth',depth,'body bytes',len(body),'body SHA256',hashlib.sha256(body).hexdigest())
print('Captured Git cat-file and importing-client bodies match; pack-only state is identical')
print('Size',len(data),'/ Git',row['git'],'=',row['ratio'],'< 1.5; REF headroom',1.5-row['ratio'])
