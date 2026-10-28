#!/usr/bin/env python3
"""Independent R4c pack writer interop; captures are evidence, not pack-byte parity."""
import argparse, base64, hashlib, json, os, pathlib, runpy, shutil, subprocess
R = pathlib.Path(__file__).resolve().parent.parent
G = str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
os.environ['DEN_GIT']=G
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
a = argparse.ArgumentParser(); a.add_argument('--tier',default='native'); a.add_argument('--core-only',action='store_true'); args=a.parse_args()
root=R/'target'/('pack-write-'+args.tier)
if root.exists(): shutil.rmtree(root)
root.mkdir(parents=True)
records=[]; sizes=[]; contents={}; states={}
def state(p):
    result={}
    for f in sorted(p.rglob('*')):
        data=os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
        digest=hashlib.sha256(data).hexdigest(); contents[digest]=base64.b64encode(data).decode()
        result[str(f.relative_to(p))]={'mode':f.lstat().st_mode,'content':digest}
    return result
def run(cmd,p,data=None,ok=True):
    q=subprocess.run(list(map(str,cmd)),cwd=p,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    snapshot=state(p); key=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest(); states[key]=snapshot
    records.append({'argv':list(map(str,cmd)), 'stdout':q.stdout.hex(),'stderr':q.stderr.hex(),'status':q.returncode,'state':key})
    if ok: assert q.returncode==0,(cmd,q.returncode,q.stderr)
    return q
try:
    corpus=root/'corpus'
    runpy.run_path(str(R/'tools/corpus.py'))['build'](corpus)
    fixtures=sorted(p for p in corpus.iterdir() if (p/'.git').is_dir())
    repeated=root/'similar'; repeated.mkdir()
    run([G,'init','-q','--template='],repeated)
    for n in range(24):
        body=b''.join(('line %04d content for pack similarity\n'%k).encode() for k in range(200)) + ('revision %d\n'%n).encode()
        run([G,'hash-object','-w','--stdin'],repeated,body)
    fixtures.append(repeated)
    own=root/'den-origin'; own.mkdir(); den=R/'target'/args.tier/'den'
    run([den,'init','-q'],own)
    for n in range(3):
        (own/'a').write_bytes(('own object %d\n'%n).encode())
        run([den,'add','a'],own);run([den,'commit','-q','-m','own history'],own)
    fixtures.append(own)
    if not args.core_only:
        sources=root/'inherited';sources.mkdir()
        inherited=sorted(p for p in (R/'target'/('pack-interop-'+args.tier)).glob('*-*') if (p/'.git').is_dir())
        assert len(inherited)==34,('vc09 fixture count',len(inherited))
        for p in inherited:
            dest=sources/('vc09-'+p.name);shutil.copytree(p,dest,symlinks=True);fixtures.append(dest)
        for name in ['stashed','noted','fanned']:
            for mode in ['loose','packed']:
                p=R/'target'/('stash-'+args.tier)/'fixtures'/(name+'-'+mode)
                assert (p/'.git').is_dir(),('vc12 fixture missing',p)
                dest=sources/('vc12-'+name+'-'+mode);shutil.copytree(p,dest,symlinks=True);fixtures.append(dest)
    for src in fixtures:
        ids=run([G,'cat-file','--batch-all-objects','--batch-check=%(objectname)'],src).stdout
        expected={}
        for id in ids.decode().splitlines():
            kind=run([G,'cat-file','-t',id],src).stdout.decode().strip()
            expected[id]=(kind,run([G,'cat-file',kind,id],src).stdout)
        baseline=root/(src.name+'-git'); shutil.copytree(src,baseline,symlinks=True)
        oraclebase=baseline/'.git/objects/pack/pack'
        oid=run([G,'pack-objects','-q','--delta-base-offset',oraclebase],baseline,ids).stdout.decode().strip()
        git_size=pathlib.Path(str(oraclebase)+'-'+oid+'.pack').stat().st_size
        none_oid=run([G,'pack-objects','-q','--window=0','--no-reuse-object',oraclebase],baseline,ids).stdout.decode().strip()
        none_size=pathlib.Path(str(oraclebase)+'-'+none_oid+'.pack').stat().st_size
        for mode in ['none','ofs','ref']:
            p=root/(src.name+'-'+mode); shutil.copytree(src,p,symlinks=True)
            names=root/(src.name+'-'+mode+'.names'); names.write_bytes(ids)
            before=state(p)
            out=run([R/'target'/args.tier/'pack-write-client',p/'.git',names,mode],p,ok=False)
            assert out.returncode==0,('vc13 writer '+src.name+'-'+mode+': validated pair publication',out.returncode,out.stdout,out.stderr)
            name=out.stdout.decode().strip(); stem=p/'.git/objects/pack'/('pack-'+name)
            idx=pathlib.Path(str(stem)+'.idx'); pack=pathlib.Path(str(stem)+'.pack')
            after=state(p)
            assert all(after.get(k)==v for k,v in before.items()),'writer modified existing files'
            assert set(after)-set(before)==({str(pack.relative_to(p)),str(idx.relative_to(p))}-set(before))
            verify=run([G,'verify-pack','-v',idx],p)
            assert b': ok\n' in verify.stdout
            # Isolate the new pair: old packed copies must not mask a broken writer.
            for old in (p/'.git/objects/pack').iterdir():
                if old not in (pack,idx): old.unlink()
            for id,(kind,body) in expected.items():
                loose=p/'.git/objects'/id[:2]/id[2:]
                if loose.exists(): loose.unlink()
            run([G,'fsck','--full'],p)
            for id,(kind,body) in expected.items():
                assert run([G,'cat-file',kind,id],p).stdout==body
                got=run([R/'target'/args.tier/'pack-client',p/'.git',id,'16777216'],p).stdout
                assert got==('%s %d %s\n'%(kind,len(body),id)).encode()+body
            reference_size=none_size if mode=='none' else git_size
            ratio=pack.stat().st_size/reference_size
            sizes.append({'fixture':src.name,'mode':mode,'objects':len(expected),'den':pack.stat().st_size,'git':reference_size,'ratio':ratio,'git_default':git_size,'default_ratio':pack.stat().st_size/git_size,'baseline':'no-delta' if mode=='none' else 'default-ofs'})
            assert ratio<=1.5,(src.name,mode,ratio)
            print('PACK WRITE',src.name,mode,len(expected),ratio,flush=True)
finally:
    (R/'target'/('pack-write-'+args.tier+'.json')).write_text(json.dumps({'processes':records,'sizes':sizes,'states':states,'contents':contents,'core_only':args.core_only}))
print('PACK WRITE COMPLETE',len(sizes),'fixtures/modes',sum(s['objects'] for s in sizes),'objects')
