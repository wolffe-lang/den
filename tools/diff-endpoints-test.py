"""Independent diff endpoint/pathspec/rename matrix; complete read-only state.
No implementation-derived expected output; fixed Git is called for every row.
"""
import argparse,hashlib,json,os,pathlib,random,runpy,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parent.parent
O=runpy.run_path(str(ROOT/'tools/oracle.py'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tier',choices=('native','release'),required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    git=os.environ['DEN_GIT'];den=str(ROOT/f'target/{a.tier}/den')
    base=ROOT/f'target/diff-endpoints-{a.tier}'
    if base.exists():shutil.rmtree(base)
    base.mkdir(parents=True);rows=[]
    def g(repo,*args,data=None):
        p=subprocess.run([git,*args],cwd=repo,input=data,capture_output=True,timeout=30)
        assert p.returncode==0,(args,p.returncode,p.stdout,p.stderr)
        return p.stdout.strip().decode()
    def write(repo,path,data):
        p=repo/path;p.parent.mkdir(parents=True,exist_ok=True)
        if p.is_symlink():p.unlink()
        p.write_bytes(data)
    def state(repo):return {'repository':O['snapshot'](repo),'worktree':O['worktree_snapshot'](repo)}
    def check(repo,name,args,cwd=None):
        before=state(repo)
        outputs=[]
        for tool in (git,den):
            p=subprocess.run([tool,*args],cwd=cwd or repo,capture_output=True,timeout=30)
            outputs.append({'stdout':p.stdout.hex(),'stderr':p.stderr.hex(),'status':p.returncode})
            assert state(repo)==before,('read-only mutation',name,tool)
        rows.append({'name':name,'args':args,'cwd':str((cwd or repo).relative_to(repo)),
                     'git':outputs[0],'den':outputs[1],'ok':outputs[0]==outputs[1],
                     'unchanged_state_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()})
    repo=base/'mixed';repo.mkdir();g(repo,'init','-q')
    originals={'nested/a.txt':b'alpha\nbeta\ngamma\n','nested/deep/b.txt':b'nested\n','UP.txt':b'upper\n',
               'other.md':b'old markdown\n','literal*.txt':b'literal\n','empty':b'',
               'mode':b'mode\n','type':b'target','binary':b'\0old binary',
               '.gitignore':b'ignored*\n','copy-source':b'copy original\n','source':b''.join(f'line-{i:03}\n'.encode() for i in range(100))}
    for p,v in originals.items():write(repo,p,v)
    (repo/'link').symlink_to('nested/a.txt');g(repo,'add','-A');g(repo,'commit','-qm','before');first=g(repo,'rev-parse','HEAD')
    for p in ('nested/a.txt','nested/deep/b.txt','UP.txt','other.md','literal*.txt'):write(repo,p,originals[p]+b'added\n')
    (repo/'empty').unlink();(repo/'mode').chmod(0o755);(repo/'type').unlink();(repo/'type').symlink_to('target')
    (repo/'link').unlink();(repo/'link').symlink_to('other.md');write(repo,'binary',b'\0new binary')
    (repo/'source').rename(repo/'moved');write(repo,'moved',b''.join(f'line-{i:03}\n'.encode() for i in range(51))+b''.join(f'EDIT-{i:03}\n'.encode() for i in range(49)))
    write(repo,'copy-source',b'copy changed\n');write(repo,'copy-target',b'copy original\n')
    write(repo,'space file',b'space\n');write(repo,'tab\tfile',b'tab\n');write(repo,'new-empty',b'')
    g(repo,'add','-A');g(repo,'commit','-qm','after');second=g(repo,'rev-parse','HEAD')
    write(repo,'nested/a.txt',b'index\n');g(repo,'add','nested/a.txt');write(repo,'nested/a.txt',b'worktree\n')
    write(repo,'untracked',b'must not appear\n');write(repo,'ignored-data',b'must not appear\n')
    endpoints=[('worktree',[]),('cached',['--cached']),('head',['HEAD']),('commits',[first,second]),('ancestry',['HEAD~1','HEAD'])]
    displays=[[],['-U0'],['-U1'],['-U10'],['--no-indent-heuristic'],['--name-only'],['--name-status'],
              ['--name-status','-z'],['--numstat'],['--numstat','-z'],['--stat'],['--stat=40,15'],
              ['--stat','--stat-count=3'],['--stat','--stat-graph-width=10'],['--shortstat'],['--stat','-p'],
              ['--no-renames'],['-M100%'],['-M49%'],['--abbrev=12'],['--full-index'],['-R'],['-C'],['--find-copies=50%'],['--text']]
    selectors=[[],['--','nested'],['--','*.txt'],['--',':(literal)literal*.txt'],['--',':(top)nested/*'],
               ['--',':(glob)nested/*.txt'],['--',':(glob)**/*.txt'],['--',':(icase)up.txt'],
               ['--',':(exclude)*.md'],['--',':'],['--',':/'],['--',':!nested'],['--','source'],
               ['--','moved'],['--','source','moved'],['--','[Uu][Pp].txt']]
    for en,ep in endpoints:
        for i,display in enumerate(displays):check(repo,f'{en}-display-{i}',['diff',*display,*ep])
        for i,select in enumerate(selectors):check(repo,f'{en}-pathspec-{i}',['diff','--name-status',*ep,*select])
    for i,select in enumerate(selectors):check(repo,f'subdir-pathspec-{i}',['diff','--name-status',first,second,*select],repo/'nested')
    blobs=[g(repo,'hash-object','-w','--stdin',data=s) for s in (b'old\nline',b'new\nline')]
    for i,display in enumerate(displays):check(repo,f'blobs-{i}',['diff',*display,*blobs])
    rng=random.Random(0x76633034)
    for percentage in range(46,55):
        repo=base/f'rename-{percentage}';repo.mkdir();g(repo,'init','-q')
        before=b''.join(f'line-{i:03}\n'.encode() for i in range(100))
        write(repo,'old',before);g(repo,'add','old');g(repo,'commit','-qm','base')
        (repo/'old').unlink();shared=set(rng.sample(range(100),percentage))
        write(repo,'new',b''.join((f'line-{i:03}\n' if i in shared else f'EDIT-{i:03}\n').encode() for i in range(100)))
        g(repo,'add','-A')
        for i,display in enumerate(displays):check(repo,f'rename-{percentage}-{i}',['diff','--cached',*display])
    repo=base/'stat-widths';repo.mkdir();g(repo,'init','-q')
    for path,body in [('a',b'old\n'),('directory/'+'long-name-'*8,b'old\n'*45),('z',b'old\n'*80)]:write(repo,path,body)
    g(repo,'add','-A');g(repo,'commit','-qm','base')
    write(repo,'a',b'new\n'*10);write(repo,'directory/'+'long-name-'*8,b'new\n'*55);write(repo,'z',b'new\n'*20)
    for width in (1,20,25,26,39,40,79,80,81,120):
        for count in (0,1,2):
            for name_width in (0,3,15):
                display=['--stat',f'--stat-width={width}',f'--stat-count={count}',f'--stat-name-width={name_width}']
                check(repo,f'stat-width-{width}-{count}-{name_width}',['diff',*display])
    for graph in (1,2,3,10,100):check(repo,f'graph-width-{graph}',['diff','--stat',f'--stat-graph-width={graph}'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'rows':rows},indent=2)+'\n')
    failed=[r['name'] for r in rows if not r['ok']]
    print('diff endpoints',len(rows)-len(failed),'/',len(rows),'failures',failed[:45],flush=True)
    assert not failed

if __name__=='__main__':main()
