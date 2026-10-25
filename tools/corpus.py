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
    # M2 states are separate fixtures; the original nine builders stay unchanged.
    for name in ('m2-ignore','m2-staged-rename','m2-modes','m2-unborn','m2-amend','m2-index-v4','m2-edited-rename'):
        p=base/name;p.mkdir()
        git(p,'init','--template='+os.environ['DEN_EMPTY_TEMPLATE'],'-q')
        if name=='m2-unborn':
            (p/'new').write_bytes(b'new\n')
        else:
            (p/'a.txt').write_bytes(b'alpha\n');(p/'b.txt').write_bytes(b'beta\n')
            if name=='m2-modes':
                (p/'link').symlink_to('a.txt')
                (p/'exec').write_bytes(b'#!/bin/sh\necho den\n');(p/'exec').chmod(0o755)
            if name=='m2-edited-rename':(p/'a.txt').write_bytes(b'a'*64)
            if name=='m2-index-v4':git(p,'-c','index.version=4','add','.')
            else:git(p,'add','.')
            git(p,'commit','-qm','initial')
            if name=='m2-edited-rename':
                git(p,'mv','a.txt','renamed.txt');(p/'renamed.txt').write_bytes(b'b'*64);git(p,'add','renamed.txt')
            if name=='m2-staged-rename':git(p,'mv','a.txt','renamed.txt')
            if name=='m2-amend':
                git(p,'commit','--amend','-qm','amended root',date=1)
                (p/'a.txt').write_bytes(b'child\n');git(p,'add','a.txt');git(p,'commit','-qm','child',date=2)
                git(p,'commit','--amend','-qm','amended child',date=3)
            if name=='m2-ignore':
                (p/'.gitignore').write_bytes(b'*.tmp\n/root-only\ncache/\n**/deep.log\na/**/secret\n!keep.tmp\nescaped\\ \n\\!literal\n\\#hash\nnumber[0-9]\nquest?on\n')
                for path in ('hide.tmp','keep.tmp','root-only','cache/hidden','a/deep.log','a/sub/secret','escaped ','!literal','#hash','number7','question','nested/keep.tmp','nested/drop.tmp','local-only','global-only'):
                    f=p/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b'fixture\n')
                (p/'nested/.gitignore').write_bytes(b'!keep.tmp\n')
                (p/'.git/info').mkdir(exist_ok=True);(p/'.git/info/exclude').write_bytes(b'local-only\n')
                (p/'global.ignore').write_bytes(b'global-only\n')
                with (p/'.git/config').open('ab') as out:out.write(b'\n[core]\nexcludesFile = global.ignore\n')
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
        print(f'corpus: {len(first)} repositories, oids identical in two independent builds')
    else:print(f'corpus: {len(first)} repositories')
