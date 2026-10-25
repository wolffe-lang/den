#!/usr/bin/env python3
"""Codec interop against every corpus object/pack entry; no production pack code.
Pack/delta fixture reader is derived directly from gitformat-pack, not Git code.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[1]
G=os.environ['DEN_GIT']


def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',default='target/zpipe');a=p.parse_args()
    binary=(ROOT/a.binary).resolve(); work=ROOT/'target/codec-corpus'; work.mkdir(exist_ok=True)
    counts={'loose':0,'pack_entries':0,'written':0,'corrupt_refused':0,'empty_corpora':0};sizes=[]
    def git(repo,*args,data=None,ok=True):
        c=subprocess.run([G,*args],cwd=repo,input=data,capture_output=True,timeout=60)
        if ok:assert c.returncode==0,(args,c.returncode,c.stderr)
        else:assert c.returncode!=0,(args,c.stdout,c.stderr)
        return c.stdout
    def den(op,data,cap,level=1,error=None):
        inp=work/'input';out=work/'output';inp.write_bytes(data);out.unlink(missing_ok=True)
        c=subprocess.run([str(binary),op,str(inp),str(out),str(cap),str(level)],capture_output=True,timeout=30)
        if error:
            assert c.returncode==1 and c.stderr.strip()==error.encode(),(error,c.returncode,c.stderr)
            counts['corrupt_refused']+=1;return
        assert c.returncode==0 and not c.stderr,(op,c.returncode,c.stderr)
        if op=='hash':return c.stdout.decode().strip()
        return out.read_bytes(),list(map(int,c.stdout.split()))
    def inflate(data):
        d=zlib.decompressobj();expected=d.decompress(data);assert d.eof
        raw,meta=den('inflate',data,len(expected))
        assert raw==expected and meta==[len(data)-len(d.unused_data),len(raw)]
        return raw,meta[0]
    def raw_object(kind,body):return kind.encode()+b' '+str(len(body)).encode()+b'\0'+body
    def varint(data,pos):
        n=0;shift=0
        while True:
            b=data[pos];pos+=1;n|=(b&127)<<shift
            if not b&128:return n,pos
            shift+=7;assert shift<64
    def delta(base,data):
        n,pos=varint(data,0);assert n==len(base)
        total,pos=varint(data,pos);out=bytearray()
        while pos<len(data):
            b=data[pos];pos+=1;assert b
            if b&128:
                offset=length=0
                for i in range(4):
                    if b&(1<<i):offset|=data[pos]<<(8*i);pos+=1
                for i in range(3):
                    if b&(16<<i):length|=data[pos]<<(8*i);pos+=1
                length=length or 65536;assert offset+length<=len(base);out.extend(base[offset:offset+length])
            else:assert pos+b<=len(data);out.extend(data[pos:pos+b]);pos+=b
        assert len(out)==total;return bytes(out)
    for repo in sorted((ROOT/'target/corpus').iterdir()):
        if not repo.is_dir():continue
        for f in sorted((repo/'.git/objects').glob('[0-9a-f][0-9a-f]/*')):
            oid=f.parent.name+f.name;raw,consumed=inflate(f.read_bytes());assert consumed==f.stat().st_size
            assert den('hash',raw,0)==oid==hashlib.sha1(raw).hexdigest()
            h,body=raw.split(b'\0',1);kind,n=h.split(b' ');assert int(n)==len(body)
            assert git(repo,'cat-file',kind.decode(),oid)==body
            counts['loose']+=1
        for pack in sorted((repo/'.git/objects/pack').glob('*.pack')):
            data=pack.read_bytes();assert data[:8]==b'PACK\0\0\0\2' and hashlib.sha1(data[:-20]).digest()==data[-20:]
            mapping={int(parts[4]):parts[0] for line in git(repo,'verify-pack','-v',str(pack.with_suffix('.idx'))).decode().splitlines()
                     if len(parts:=line.split())>=5 and len(parts[0])==40}
            entries={};pos=12
            for _ in range(int.from_bytes(data[8:12],'big')):
                start=pos;b=data[pos];pos+=1;kind=(b>>4)&7;n=b&15;shift=4
                while b&128:b=data[pos];pos+=1;n|=(b&127)<<shift;shift+=7
                base=None
                if kind==6:
                    b=data[pos];pos+=1;distance=b&127
                    while b&128:b=data[pos];pos+=1;distance=((distance+1)<<7)+(b&127)
                    base=start-distance
                elif kind==7:base=data[pos:pos+20].hex();pos+=20
                body,consumed=inflate(data[pos:]);assert len(body)==n;pos+=consumed
                entries[start]=(kind,body,base);counts['pack_entries']+=1
            assert pos==len(data)-20
            decoded={};pending=dict(entries)
            while pending:
                progressed=False
                for off,(kind,body,base) in list(pending.items()):
                    if kind in [6,7]:
                        baseoff=base if kind==6 else next((k for k,v in mapping.items() if v==base),None)
                        if baseoff not in decoded:continue
                        kind,old=decoded[baseoff];body=delta(old,body)
                    assert kind in [1,2,3,4]
                    name=['','commit','tree','blob','tag'][kind];oid=mapping[off];raw=raw_object(name,body)
                    assert den('hash',raw,0)==oid==hashlib.sha1(raw).hexdigest()
                    assert git(repo,'cat-file',name,oid)==body
                    decoded[off]=(kind,body);del pending[off];progressed=True
                assert progressed,'unresolved delta'
        # Rebuild every object as a den-encoded loose stream; Git must read/fsck it.
        dest=work/repo.name
        if dest.exists():shutil.rmtree(dest)
        dest.mkdir();git(dest,'init','-q','--template='+os.environ['DEN_EMPTY_TEMPLATE'])
        reference=work/(repo.name+'-git')
        if reference.exists():shutil.rmtree(reference)
        reference.mkdir();git(reference,'init','-q','--template='+os.environ['DEN_EMPTY_TEMPLATE'])
        den_size=git_size=0;largest=0;objects=[]
        for line in git(repo,'cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype) %(objectsize)').decode().splitlines():
            oid,kind,n=line.split();body=git(repo,'cat-file',kind,oid);assert len(body)==int(n)
            raw=raw_object(kind,body);encoded,_=den('deflate',raw,len(raw)*2+100)
            assert zlib.decompress(encoded)==raw
            assert git(reference,'-c','core.looseCompression=1','hash-object','-w','-t',kind,'--stdin',data=body).strip().decode()==oid
            oracle=(reference/'.git/objects'/oid[:2]/oid[2:]).read_bytes()
            c=zlib.compressobj(1);assert c.compress(raw)+c.flush()==oracle
            den_size+=len(encoded);git_size+=len(oracle);largest=max(largest,len(encoded)/len(oracle))
            f=dest/'.git/objects'/oid[:2]/oid[2:];f.parent.mkdir(exist_ok=True);f.write_bytes(encoded)
            assert git(dest,'cat-file',kind,oid)==body;counts['written']+=1;objects.append((f,encoded,raw))
        head=subprocess.run([G,'rev-parse','--verify','HEAD'],cwd=repo,capture_output=True)
        if head.returncode==0:git(dest,'update-ref','refs/heads/main',head.stdout.strip().decode())
        else:
            assert head.returncode in (1,128) and not objects,(repo,head.stderr)
            counts['empty_corpora']+=1
        git(dest,'fsck','--full','--strict')
        if objects:
            f,encoded,raw=objects[0]
        else:
            # A valid unborn store has no object to mutate. Exercise the same
            # corruption boundary with an independent synthetic empty blob,
            # then remove it so the rebuilt store is empty again. No skip.
            raw=b'blob 0\0';encoded=zlib.compress(raw,1);identifier=hashlib.sha1(raw).hexdigest()
            f=dest/'.git/objects'/identifier[:2]/identifier[2:];f.parent.mkdir(exist_ok=True)
        corrupt=encoded[:-1]+bytes([encoded[-1]^1]);den('inflate',corrupt,len(raw),error='checksum')
        den('inflate',encoded[:-1],len(raw),error='truncated')
        f.write_bytes(corrupt);git(dest,'fsck','--full',ok=False)
        if objects:f.write_bytes(encoded)
        else:f.unlink()
        sizes.append(dict(corpus=repo.name,den=den_size,git_level1=git_size,ratio=den_size/git_size if git_size else None,max_object_ratio=largest))
        print('PASS corpus',repo.name,sizes[-1],flush=True)
    # The documented two-entry pack is an independent stream boundary fixture.
    text=(ROOT/'notes/vc00-evidence/formats/two-object.pack.hex').read_text()
    pack=bytes.fromhex(' '.join(line.split('  ',1)[1] for line in text.splitlines()))
    first,n=inflate(pack[13:]);assert first==b'alpha\n' and n==14
    second,m=inflate(pack[14+n:]);assert second==b'beta\n' and m==13
    summary=dict(counts=counts,sizes=sizes,zlib=zlib.ZLIB_RUNTIME_VERSION)
    (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    assert all((s['ratio'] is None and s['den']==s['git_level1']==0) or s['ratio']<=1.25 for s in sizes),sizes
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
