"""Independent multi-candidate fixtures; pinned Git binary is the only oracle.

--measure saves observations before the client exists. Later runs compare the
public pairer and existing status/commit consumers, keeping every disagreement.
"""
import argparse, hashlib, json, os, pathlib, random, runpy, shutil, subprocess
ROOT=pathlib.Path(__file__).resolve().parent.parent

def cases():
    rows=[]
    def add(name,old,new,copies=False,threshold=50):
        rows.append(dict(name=name,old=old,new=new,copies=copies,threshold=threshold))
    a=b'a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n'
    b=b'a\nb\nc\nd\ne\nf\ng\nh\ni\nX\n'
    c=b'a\nb\nc\nd\ne\nf\ng\nh\nY\nZ\n'
    def files(*items):return {p:(d,0o100644) for p,d in items}
    add('exact-path-order',files(('old/z',a),('old/a',a)),files(('new/y',a),('new/b',a)))
    add('exact-basename',files(('old/z',a),('old/a',a)),files(('new/a',a),('new/z',a)))
    add('exact-before-approx',files(('old/a',a),('old/b',b)),files(('new/a',b),('new/b',c)))
    add('equal-score-order',files(('old/z',a),('old/a',a)),files(('new/y',b),('new/b',b)))
    add('equal-score-basename',files(('old/z',a),('old/a',a)),files(('new/a',b),('new/z',b)))
    add('basename-before-higher',files(('old/a',a),('old/b',b)),files(('new/a',c),('new/b',a.replace(b'j\n',b'Y\n'))))
    add('basename-below-prepass',files(('old/a',a),('old/b',b)),files(('new/a',a[:12]+b'X\nY\nZ\nQ\n'),('new/b',a[:14]+b'X\nY\nZ\n')))
    add('eight-equal-no-basename',files(*[(f'old/s{i}',a) for i in range(8)]),files(*[(f'new/d{i}',b) for i in range(8)]))
    add('one-source-two-exact',files(('old',a)),files(('a',a),('b',a)))
    add('copy-deleted-reuse',files(('old',a)),files(('a',a),('b',a)),True)
    add('copy-modified',files(('old',a)),files(('old',b),('new',a)),True)
    add('copy-modified-inexact',files(('old',a)),files(('old',c),('new',b)),True)
    add('copy-unchanged-excluded',files(('old',a)),files(('old',a),('new',a)),True)
    add('copy-vs-delete',files(('keep',a),('old',a)),files(('keep',b),('new',a)),True)
    add('symlink-exact',{'old':(b'target',0o120000)},{'new':(b'target',0o120000)})
    add('symlink-inexact',{'old':(a,0o120000)},{'new':(b,0o120000)})
    add('type-mismatch',{'old':(a,0o120000)},{'new':(a,0o100644)})
    add('mode-change',{'old':(a,0o100644)},{'new':(b,0o100755)})
    add('unequal-r100',files(('old',b'a'*64)),files(('new',b'b'*64)))
    add('unequal-r100-exact-threshold',files(('old',b'a'*64)),files(('new',b'b'*64)),threshold=100)
    add('exact-empty',files(('old',b'')),files(('new',b'')))
    for threshold in (1,49,50,51,90,100):
        add(f'threshold-{threshold}',files(('old',a)),files(('new',a[:10]+b'Q\nR\nS\nT\nU\n')),threshold=threshold)
    rng=random.Random(0x76633034)
    for n in range(80):
        old={};new={}
        for i in range(1+rng.randrange(6)):
            data=b''.join(bytes([97+rng.randrange(12)])+b'\n' for _ in range(20))
            old[f'old/{i}']=(data,0o100644)
        for j in range(1+rng.randrange(6)):
            data=bytearray(rng.choice(list(old.values()))[0])
            for _ in range(rng.randrange(8)):data[2*rng.randrange(20)]=97+rng.randrange(12)
            new[f'new/{j}']=(bytes(data),0o100644)
        add(f'seeded-{n}',old,new)
    for n in range(160):
        old={};new={}
        for i in range(1+rng.randrange(8)):
            data=b''.join(bytes([97+rng.randrange(8)])+b'\n' for _ in range(20))
            old[f'old/{i}/{rng.randrange(3)}']=(data,0o100644)
        for j in range(1+rng.randrange(8)):
            data=bytearray(rng.choice(list(old.values()))[0])
            for _ in range(rng.randrange(8)):data[2*rng.randrange(20)]=97+rng.randrange(8)
            new[f'new/{j}/{rng.randrange(3)}']=(bytes(data),0o100644)
        copies=n%2==0
        if copies:
            for path,(data,mode) in old.items():
                if rng.randrange(2):new[path]=(data.replace(b'a',b'X'),mode)
        add(f'duplicate-basename-{n}',old,new,copies)
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');ap.add_argument('--measure',action='store_true');ap.add_argument('--consumers',action='store_true');args=ap.parse_args()
    git=os.environ['DEN_GIT'];driver=ROOT/f'target/{args.tier}/rename-client'
    base=ROOT/f'target/rename-pairing-{args.tier}';base.mkdir(parents=True,exist_ok=True)
    observations=[]
    consumer_rows=[]
    oracle=runpy.run_path(str(ROOT/'tools/oracle.py')) if args.consumers else None
    for case in cases():
        repo=base/'repo'
        if repo.exists():shutil.rmtree(repo)
        repo.mkdir()
        def run(*argv):
            p=subprocess.run(argv,cwd=repo,capture_output=True,timeout=30)
            assert p.returncode==0,(argv,p.returncode,p.stdout,p.stderr)
            return p.stdout
        def put(entries):
            for path,(data,mode) in entries.items():
                f=repo/path;f.parent.mkdir(parents=True,exist_ok=True)
                if mode==0o120000:f.symlink_to(data.decode())
                else:f.write_bytes(data);f.chmod(mode & 0o777)
        run(git,'init','-q');put(case['old']);run(git,'add','.');run(git,'commit','-qm','root')
        for path in case['old']:(repo/path).unlink()
        put(case['new']);run(git,'add','-A')
        flag=('-C' if case['copies'] else '-M')+str(case['threshold'])+'%'
        raw=run(git,'diff','--cached','--name-status','-z',flag)
        parts=raw.split(b'\0');expected=[];i=0
        while i<len(parts) and parts[i]:
            status=parts[i].decode();i+=1
            if status[0] in 'RC':
                expected.append((parts[i].decode(),parts[i+1].decode(),int(status[1:]),status[0]));i+=2
            else:i+=1
        source=[p for p in sorted(case['old']) if p not in case['new'] or case['copies'] and case['old'][p]!=case['new'][p]]
        destination=[p for p in sorted(case['new']) if p not in case['old']]
        observed=None
        if not args.measure:
            command=[str(driver),str(case['threshold']),'true' if case['copies'] else 'false']
            for side,paths in [('old',source),('new',destination)]:
                for index,path in enumerate(paths):
                    data,mode=case[side][path];f=base/f'{side}-{index}';f.write_bytes(data)
                    command += [side,path,str(mode),'true' if side=='old' and path in case['new'] else 'false',str(f)]
            text=run(*command).decode();observed=[]
            for line in text.splitlines():
                src,dst,units,percent,copy=line.split();observed.append((source[int(src)],destination[int(dst)],int(percent),'C' if copy=='true' else 'R'))
        observations.append(dict(name=case['name'],inputs={side:{p:{'hex':d.hex(),'mode':m} for p,(d,m) in case[side].items()} for side in ('old','new')},threshold=case['threshold'],copies=case['copies'],oracle=expected,actual=observed,ok=observed is None or sorted(expected)==sorted(observed),raw=raw.hex()))
        if args.measure or not observations[-1]['ok']:print(observations[-1],flush=True)
        if args.consumers and case['threshold']==50:
            run(git,'config','status.renames','copies' if case['copies'] else 'true')
            for flags in (['--porcelain'],['--porcelain','-z'],['--no-renames','--porcelain']):
                expected_status=oracle['capture']([git,'status',*flags],repo,index_proof=True)
                actual_status=oracle['capture']([str(ROOT/f'target/{args.tier}/worktree-client'),'status',*flags],repo,index_proof=True)
                ok=expected_status['status']==actual_status['status']==0 and oracle['equivalent'](expected_status,actual_status,'index-stat-proven')
                consumer_rows.append(dict(name=case['name'],command=['status',*flags],ok=ok,oracle=expected_status,actual=actual_status))
            backup=base/'backup'
            if backup.exists():shutil.rmtree(backup)
            shutil.copytree(repo,backup,symlinks=True)
            expected_commit=oracle['capture']([git,'commit','-m','pairing'],repo,index_proof=True)
            shutil.rmtree(repo);shutil.copytree(backup,repo,symlinks=True)
            actual_commit=oracle['capture']([str(ROOT/f'target/{args.tier}/commit-client'),'commit','-m','pairing'],repo,index_proof=True)
            ok=expected_commit['status']==actual_commit['status']==0 and oracle['equivalent'](expected_commit,actual_commit,'index-stat-proven')
            consumer_rows.append(dict(name=case['name'],command=['commit','-m','pairing'],ok=ok,oracle=expected_commit,actual=actual_commit))

    out=ROOT/f'target/rename-pairing-{args.tier}{"-measure" if args.measure else ""}.json';out.write_text(json.dumps(dict(driver_sha256=None if args.measure else hashlib.sha256(driver.read_bytes()).hexdigest(),cases=observations),indent=2)+'\n')
    if args.consumers:(ROOT/f'target/rename-consumers-{args.tier}.json').write_text(json.dumps(consumer_rows,indent=2)+'\n')
    failures=[r for r in observations+consumer_rows if not r['ok']]
    assert not failures,[(r['name'],r.get('command'),r.get('oracle'),r.get('actual')) for r in failures]
    print(f'PASS {len(observations)} independent multi-candidate cases, {len(consumer_rows)} full-state consumer comparisons; zero skips')
if __name__=='__main__':main()
