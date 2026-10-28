"""Strict Git git-cat-file(1) BATCH OUTPUT decoder for independent test clients.

No implementation source used. Every frame, identity, requested name and byte
is checked; batching reduces process boundaries, not the object inventory.
"""
import hashlib,re

def decode(data, names):
    assert len(names)<=10000 and len(set(names))==len(names), 'batch requested names'
    objects={};pos=0;total=0
    for wanted in names:
        end=data.find(b'\n',pos)
        assert end!=-1 and end-pos<=80, 'batch header boundary'
        match=re.fullmatch(rb'([0-9a-f]{40}) (blob|tree|commit|tag) (0|[1-9][0-9]*)',data[pos:end])
        assert match is not None, 'batch header grammar'
        name,kind,size=match.groups();name=name.decode();kind=kind.decode();size=int(size)
        assert name==wanted and name not in objects, 'batch requested object order'
        assert size<=16777216 and total+size<=134217728, 'batch payload bound'
        pos=end+1
        assert len(data)-pos>=size+1 and data[pos+size:pos+size+1]==b'\n', 'batch body framing'
        body=data[pos:pos+size];pos+=size+1;total+=size
        assert hashlib.sha1((kind+' '+str(size)+'\0').encode()+body).hexdigest()==name, 'batch object identity'
        objects[name]=(kind,body)
    assert pos==len(data), 'batch trailing bytes or unexpected object'
    return objects
