"""Read-only diff commands: exact stdout/stderr/status plus unchanged files.
Original fixtures and expected results come from pinned Git, not den.
"""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,runpy
ROOT=pathlib.Path(__file__).resolve().parent.parent
ORACLE=runpy.run_path(str(ROOT/'tools/oracle.py'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tier',default='native',choices=('native','release'))
    parser.add_argument('--oracle-only',action='store_true')
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    git=os.environ['DEN_GIT'];den=str(ROOT/f'target/{args.tier}/den')
    base=ROOT/f'target/diff-{args.tier}';base.mkdir(parents=True,exist_ok=True)
    results=[]
    def command(repo,*words,data=None):
        p=subprocess.run([git,*words],cwd=repo,input=data,capture_output=True,timeout=30)
        assert p.returncode==0,(words,p.returncode,p.stdout,p.stderr)
        return p.stdout.strip().decode()
    def capture(repo,words):
        before={'repository':ORACLE['snapshot'](repo),'worktree':ORACLE['worktree_snapshot'](repo)}
        expected=ORACLE['capture']([git,*words],repo)
        assert expected['repository']==before['repository'] and expected['worktree']==before['worktree'],('oracle wrote',words)
        actual=None if args.oracle_only else ORACLE['capture']([den,*words],repo)
        return expected,actual
    scenarios=[
        ('modify','file',b'one\ntwo\nthree\n',b'one\nTWO\nthree\n',0o644),
        ('no-lf','file',b'one\ntwo',b'one\nTWO',0o644),
        ('add','file',None,b'new\n',0o644),('delete','file',b'old\n',None,0o644),
        ('empty-add','empty',None,b'',0o644),('empty-delete','empty',b'',None,0o644),
        ('mode','file',b'one\n',b'one\n',0o755),
        ('binary','file',b'a\0old',b'a\0new',0o644),
        ('space','a space',b'a\n',b'b\n',0o644),
        ('tab','a\ttab',b'a\n',b'b\n',0o644),
        ('long','long-directory/'+'name'*24,b'old\n'*40,b'new\n'*60,0o644),
        ('large-stat','f',b'old\n'*300,b'new\n'*500,0o644),
    ]
    flags=[[],['-U0'],['-U1'],['--full-index'],['--name-only'],['--name-status'],['--name-status','-z'],
           ['--stat'],['--stat=40'],['--stat=20,10'],['--numstat'],['--shortstat'],['--exit-code'],['--quiet']]
    for name,path,old,new,mode in scenarios:
        repo=base/name
        if repo.exists():shutil.rmtree(repo)
        repo.mkdir();command(repo,'init','-q')
        file=repo/path;file.parent.mkdir(parents=True,exist_ok=True)
        if old is not None:file.write_bytes(old);command(repo,'add','--',path)
        command(repo,'commit','--allow-empty','-qm','base')
        if new is None:file.unlink()
        else:file.write_bytes(new);file.chmod(mode)
        for cached in (False,True):
            if cached:command(repo,'add','-A')
            for flag in flags:
                words=['diff',*(['--cached'] if cached else []),*flag]
                expected,actual=capture(repo,words)
                results.append({'name':name+('-cached' if cached else '-worktree')+'-'+' '.join(flag),
                                'args':words,'git':expected,'den':actual,'ok':actual==expected})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'oracle_sha256':hashlib.sha256(pathlib.Path(git).read_bytes()).hexdigest(),
                                     'rows':results},indent=2)+'\n')
    if not args.oracle_only:
        failed=[r['name'] for r in results if not r['ok']]
        print('diff parity',len(results)-len(failed),'/',len(results),'failed',failed[:20],flush=True)
        assert not failed
    else:
        for r in results:
            if r['name'].endswith('-') or r['name'].endswith('--stat') or r['name'].endswith('--stat=20,10'):
                print(r['name'],bytes.fromhex(r['git']['stdout']).decode(errors='replace'),flush=True)

if __name__=='__main__':main()
