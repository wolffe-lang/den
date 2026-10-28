"""Known framing answers and deliberate corrupt batch replies; independent of den."""
import hashlib,json,pathlib,runpy
R=pathlib.Path(__file__).resolve().parent.parent
decode=runpy.run_path(str(R/'tools/pack-batch.py'))['decode']
rows=[]
def frame(kind,body):
 name=hashlib.sha1((kind+' '+str(len(body))+'\0').encode()+body).hexdigest()
 return name,(name+' '+kind+' '+str(len(body))+'\n').encode()+body+b'\n'
def check(name,data,names,expected):
 try: result=decode(data,names);accepted=True
 except (AssertionError,ValueError):result=None;accepted=False
 assert accepted==(expected is not None),(name,accepted)
 if accepted:assert result==expected,(name,result)
 rows.append({'case':name,'input':data.hex(),'names':names,'accepted':accepted,'verified':True})
check('empty',b'',[],{})
for kind in ('blob','tree','commit','tag'):
 body=b'\0\xffline\nwith spaces\n';name,data=frame(kind,body)
 check('binary-'+kind,data,[name],{name:(kind,body)})
first,a=frame('blob',b'');second,b=frame('blob',b'a\n\0b')
check('two-objects',a+b,[first,second],{first:('blob',b''),second:('blob',b'a\n\0b')})
for name,data,names in [
 ('missing-header-lf',a.split(b'\n')[0],[first]),
 ('missing-body-lf',b[:-1],[second]),
 ('truncated-body',b[:-3],[second]),
 ('wrong-object-id',b.replace(second.encode(),first.encode()),[first]),
 ('wrong-object-order',a+b,[second,first]),
 ('duplicate-request',a+a,[first,first]),
 ('extra-object',a+b,[first]),
 ('omitted-object',a,[first,second]),
 ('trailing-garbage',a+b'junk',[first]),
 ('missing-reply',(first+' missing\n').encode(),[first]),
 ('negative-size',(first+' blob -1\n').encode(),[first]),
 ('leading-zero-size',(first+' blob 00\n\n').encode(),[first]),
 ('oversize',(first+' blob 16777217\n').encode(),[first]),
 ('unknown-type',(first+' unknown 0\n\n').encode(),[first]),
 ('non-ascii-header',b'\xff blob 0\n\n',[first]),
 ('body-bit-flip',b[:-2]+bytes([b[-2]^1])+b[-1:],[second]),
 ('nonempty-zero-request',a,[]),
 ('over-count',b'',[f'{i:040x}' for i in range(10001)]),
]:check(name,data,names,None)
(R/'target/pack-batch-vectors.json').write_text(json.dumps(rows))
print('PACK BATCH VECTORS',len(rows),'verified;',sum(r['accepted'] for r in rows),'valid;',sum(not r['accepted'] for r in rows),'rejected')
