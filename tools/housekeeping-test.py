"""Independent vc14 housekeeping contract: exact process bytes, complete states,
canonical object sets/bodies and non-pack bytes. Pack representation follows R4c.
"""
import argparse, base64, hashlib, json, os, pathlib, shutil, subprocess, time
R = pathlib.Path(__file__).resolve().parent.parent
G = str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH'] = str(pathlib.Path(G).parent.parent/'libexec/git-core')
a = argparse.ArgumentParser(); a.add_argument('--tier',default='native'); a.add_argument('--run',default='final'); args = a.parse_args()
D = R/'target'/args.tier/'den'
root = R/'target'/('housekeeping-'+args.tier+'-'+args.run)
root.mkdir(parents=True,exist_ok=True)
rows, states, contents = [], {}, {}
def snap(p):
    out = {}
    for f in sorted(p.rglob('*')):
        data = os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
        digest = hashlib.sha256(data).hexdigest(); contents[digest] = base64.b64encode(data).decode()
        out[str(f.relative_to(p))] = dict(mode=f.lstat().st_mode, content=digest)
    key = hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest(); states[key] = out
    return key
def call(tool,p,cmd,data=None):
    before = snap(p); t = time.monotonic()
    q = subprocess.run([str(tool),*cmd],cwd=p,input=data,capture_output=True)
    return dict(args=cmd,before=before,after=snap(p),stdout=q.stdout.hex(),stderr=q.stderr.hex(),status=q.returncode,seconds=time.monotonic()-t)
def git(p,*cmd,data=None):
    q = subprocess.run([G,*cmd],cwd=p,input=data,capture_output=True)
    assert q.returncode == 0,(cmd,q.stdout,q.stderr)
    return q.stdout
def inventory(p):
    q = call(G,p,['cat-file','--batch-all-objects','--batch'])
    assert q['status']==0 and q['before']==q['after']
    return q

def packed_sets(p):
    groups, captures = [], []
    for idx in sorted((p/'.git/objects/pack').glob('*.idx')):
        q = call(G,p,['verify-pack','-v',str(idx)])
        assert q['status']==0 and q['before']==q['after'],q
        names = []
        for line in bytes.fromhex(q['stdout']).decode().splitlines():
            fields = line.split()
            if fields and len(fields[0])==40 and all(c in '0123456789abcdef' for c in fields[0]): names.append(fields[0])
        groups.append(sorted(names));captures.append(q)
    return sorted(groups),captures

def canonical_state(p):
    # Every path is retained above. Only the format's representation-variable
    # pack pair files become a canonical all-object batch in this comparison.
    result = {}
    for path, item in states[snap(p)].items():
        if path.startswith('.git/objects/pack/pack-') and path.endswith(('.pack','.idx','.rev')):
            continue
        if path.startswith('.git/objects/') and len(path.split('/'))==4 and len(path.split('/')[-2])==2:
            # Loose compressed bytes may differ by R-vc00-2; retain presence.
            result[path] = dict(mode=item['mode'],object=path.split('/')[-2]+path.split('/')[-1]); continue
        result[path] = item
    return result
try:
    fixtures = []
    for shape in ('large-mixed','closure','empty'):
        p = root/(shape+'-source'); p.mkdir(exist_ok=False)
        git(p,'init','-q','-b','main','--template=')
        if shape != 'empty':
            n = 1000 if shape=='large-mixed' else 5
            for i in range(n):
                body = (b'repetitive line\n'*30 + str(i).encode()) if i%3==0 else hashlib.sha256(str(i).encode()).digest()*8 if i%3==1 else f'file {i}\n'.encode()
                (p/f'f{i:04}').write_bytes(body)
            git(p,'add','.'); git(p,'commit','-qm','initial')
            git(p,'hash-object','-w','--stdin',data=b'unreachable retained\n')
            (p/'staged-only').write_bytes(b'index root\n');git(p,'add','staged-only')
            git(p,'branch','past');(p/'f0000').write_bytes(b'reflog history\n');git(p,'add','f0000');git(p,'commit','-qm','second')
            git(p,'reset','--soft','HEAD~1')
        fixtures.append(p)
    for source in fixtures:
        for packed in (False,True):
            base = root/(source.name+('-packed' if packed else '-loose'));shutil.copytree(source,base)
            if packed:
                names = git(base,'cat-file','--batch-all-objects','--batch-check=%(objectname)')
                git(base,'pack-objects','-q','.git/objects/pack/pack',data=names)
            for cmd in (['repack','-a','-n','-q'],['repack','-a','-d','-n','-q'],['repack','-a','-d','-k','-n','-q'],['prune-packed','-n'],['prune-packed','-q']):
                label = f'{source.name}-{packed}-{len(rows)}'
                gp,dp = root/(label+'-git'),root/(label+'-den')
                shutil.copytree(base,gp)
                if cmd==['prune-packed','-n']:
                    # Raw directory order is observable here. Execute both
                    # read-only processes on one immutable physical fixture,
                    # not two directories with independent filesystem ordering.
                    dp=gp
                else:
                    shutil.copytree(base,dp)
                for repeat in range(2):
                    g,d = call(G,gp,cmd),call(D,dp,cmd)
                    if cmd==['prune-packed','-n']: assert g['before']==g['after']==d['before']==d['after']
                    row = dict(label=label,repeat=repeat,git=g,den=d);rows.append(row)
                    if packed and source.name != 'empty-source' and '-d' in cmd and '-k' not in cmd:
                        row['named_refusal'] = 'repack unreachable packed retirement (use -k)'
                        assert d['status']==2 and row['named_refusal'].encode() in bytes.fromhex(d['stderr']) and d['before']==d['after']
                        continue
                    assert tuple(g[k] for k in ('stdout','stderr','status'))==tuple(d[k] for k in ('stdout','stderr','status')),(label,repeat,'exact process bytes; full captures retained')
                    gi,di = inventory(gp),inventory(dp);row.update(git_objects=gi,den_objects=di)
                    assert gi['stdout']==di['stdout'],(label,'canonical all-object bytes')
                    gs,gc = packed_sets(gp);ds,dc = packed_sets(dp);row.update(git_packs=gc,den_packs=dc)
                    assert gs==ds,(label,'per-pack object membership',gs,ds)
                    assert canonical_state(gp)==canonical_state(dp),(label,'non-representation state')
                    for tool,p in ((G,gp),(D,dp)):
                        f = call(G,p,['fsck','--full','--no-progress']);row.setdefault('fsck',[]).append(f)
                        assert f['status']==0 and f['before']==f['after'],(label,'git fsck',f)
                    print('HOUSEKEEPING',label,repeat,round(d['seconds'],3),flush=True)
finally:
    (R/'target'/('housekeeping-'+args.tier+'-'+args.run+'.json')).write_text(json.dumps(dict(rows=rows,states=states,contents=contents)))
print('HOUSEKEEPING COMPLETE',len(rows),'rows',sum('named_refusal' not in r for r in rows),'exact',sum('named_refusal' in r for r in rows),'named refusals')
