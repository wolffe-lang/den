"""Black-box repository builders. No git implementation source is read.
A corpus manifest records object ids, NOT inode-dependent index bytes.
"""
import json, os, pathlib, shutil, subprocess, sys
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT']
def git(repo,*args,data=None,date=0):
    e=os.environ.copy()
    e['GIT_AUTHOR_DATE']=e['GIT_COMMITTER_DATE']=f'{1700000000+date*60} +0000'
    p=subprocess.run([G,*args],cwd=repo,input=data,capture_output=True,env=e)
    if p.returncode: raise RuntimeError((args,p.returncode,p.stderr))
    return p.stdout

def build(base):
    if base.exists(): shutil.rmtree(base)
    base.mkdir(parents=True)
    manifest={}
    for name in ('two','linear','merge','rename','binary','symlink','empty','thousand','packed'):
        p=base/name;p.mkdir()
        git(p,'init','--template='+os.environ['DEN_EMPTY_TEMPLATE'],'-q')
        if name=='empty':
            tree=git(p,'mktree',data=b'').strip()
            commit=git(p,'commit-tree',tree.decode(),'-m','empty').strip()
            git(p,'update-ref','refs/heads/main',commit.decode())
        else:
            (p/'a.txt').write_bytes(b'alpha\n');(p/'b.txt').write_bytes(b'beta\n')
            if name=='binary':(p/'raw.bin').write_bytes(bytes(range(256)))
            if name=='symlink':(p/'link').symlink_to('a.txt')
            if name=='thousand':
                for i in range(998): (p/f'file-{i:04}').write_text(f'{i}\n')
            git(p,'add','.');git(p,'commit','-qm','initial')
            if name in ('linear','packed'):
                for i in range(1,10):
                    (p/'a.txt').write_text(f'alpha {i}\n')
                    git(p,'add','.');git(p,'commit','-qm',f'change {i}',date=i)
            if name=='merge':
                git(p,'checkout','-qb','side')
                (p/'side').write_text('side\n');git(p,'add','.');git(p,'commit','-qm','side',date=1)
                git(p,'checkout','-q','main')
                (p/'main').write_text('main\n');git(p,'add','.');git(p,'commit','-qm','main',date=2)
                git(p,'merge','--no-ff','-m','merge','side',date=3)
            if name=='rename':
                git(p,'mv','a.txt','renamed.txt');git(p,'commit','-qm','rename',date=1)
            if name=='packed': git(p,'gc','--prune=now')
        # Deterministic object identities; index stat is an observation, not an oid.
        manifest[name]=git(p,'rev-list','--objects','--all').decode().splitlines()
        git(p,'fsck','--full')
    (base/'oids.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return manifest
if __name__=='__main__':
    dest=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else R/'target/corpus').resolve()
    first=build(dest)
    if '--prove-twice' in sys.argv:
        second=build(dest.with_name(dest.name+'-second'))
        assert first==second,'corpus oids are NOT reproducible'
        print('corpus: 9 repositories, oids identical in two independent builds')
    else:print('corpus: 9 repositories')
