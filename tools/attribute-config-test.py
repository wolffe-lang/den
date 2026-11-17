#!/usr/bin/env python3
"""Pinned Git disabled fields, filter configuration and merge-only effects."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--tier',default='native');p.add_argument('--den');p.add_argument('--dev-oracle',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[1];git=os.environ['DEN_GIT'];den=a.den or str(root/'target'/a.tier/'den')
    digest=hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname=='Darwin';print('DEV ORACLE (not pinned Linux evidence):',digest,flush=True)
    else:assert digest=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    out=root/'target/runs'/('attribute-config-'+a.tier)
    if out.exists():shutil.rmtree(out)
    out.mkdir(parents=True)
    def run(tool,args,cwd,check=True):
        q=subprocess.run([str(tool),*map(str,args)],cwd=cwd,capture_output=True)
        if check:assert q.returncode==0,(args,q.returncode,q.stderr)
        return q
    def g(cwd,*args):return run(git,args,cwd).stdout
    def state(cwd):return dict(head=g(cwd,'rev-parse','HEAD').hex(),index=g(cwd,'ls-files','-s').hex(),files={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in cwd.iterdir() if x.is_file()})
    rows=[]
    def save(name,results,ok,extra=None):
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        row=dict(name=name,passed=ok,**results,**(extra or {}))
        if not ok:print(json.dumps(row),flush=True)
        rows.append(row)
    filters=[('unconfigured','sample.dat filter=lfs\n',[],False),
             ('required-false','sample.dat filter=lfs\n',[('filter.lfs.required','false')],True),
             ('required-true','sample.dat filter=lfs\n',[('filter.lfs.required','true')],True),
             ('clean','sample.dat filter=lfs\n',[('filter.lfs.clean','cat')],True),
             ('smudge','sample.dat filter=lfs\n',[('filter.lfs.smudge','cat')],True),
             ('process','sample.dat filter=lfs\n',[('filter.lfs.process','false')],True),
             ('disabled-configured','sample.dat filter=lfs -filter\n',[('filter.lfs.required','true'),('filter.lfs.clean','false')],False),
             ('disabled-eol','sample.dat -eol\n',[],False),
             ('disabled-eol-override','sample.dat eol=crlf -eol\n',[],False)]
    for kind,attrs,config,refuse in filters:
        case=out/kind;case.mkdir();seed=case/'seed';run(git,['init','-q','-b','main',seed],root)
        (seed/'.gitattributes').write_text(attrs);(seed/'sample.dat').write_bytes(b'base\n');g(seed,'add','.');g(seed,'commit','-qm','base')
        for key,value in config:g(seed,'config',key,value)
        (seed/'sample.dat').write_bytes(b'changed\n')
        for command,args in [('status',['status','--porcelain']),('add',['add','sample.dat']),('checkout',['checkout','--','sample.dat'])]:
            results={}
            for label,tool in [('git',git),('den',den)]:
                work=case/'work'
                if work.exists():shutil.rmtree(work)
                shutil.copytree(seed,work);before=state(work);q=run(tool,args,work,False)
                results[label]=dict(status=q.returncode,stdout=q.stdout.hex(),stderr=q.stderr.hex(),state=state(work),preserved=state(work)==before)
            d=results['den'];err=bytes.fromhex(d['stderr'])
            ok=(d['status']==2 and b'filter' in err and b'lfs' in err and b'sample.dat' in err and d['preserved']) if refuse else results['git']==results['den']
            save('attribute-config-'+kind+'-'+command,results,ok,dict(config=config,attributes=attrs))
    merges=[('negative','-merge'),('binary','binary'),('ours-unconfigured','merge=ours'),('custom-unconfigured','merge=libcxx-reformat'),('lfs-unconfigured','merge=lfs'),('markers','conflict-marker-size=32')]
    for kind,attrs in merges:
        for operation in ('merge','cherry-pick','revert','rebase','stash'):
            name='attribute-merge-'+kind+'-'+operation;case=out/name;case.mkdir();seed=case/'seed';run(git,['init','-q','-b','main',seed],root)
            (seed/'.gitattributes').write_text('sample.dat '+attrs+'\n');(seed/'sample.dat').write_text('first\nbase\nlast\n');g(seed,'add','.');g(seed,'commit','-qm','base');base=g(seed,'rev-parse','HEAD').decode().strip()
            g(seed,'checkout','-qb','side');(seed/'sample.dat').write_text('first\ntheirs\nlast\n');g(seed,'commit','-qam','theirs');target=g(seed,'rev-parse','HEAD').decode().strip()
            g(seed,'checkout','-q','main');(seed/'sample.dat').write_text('first\nours\nlast\n');g(seed,'commit','-qam','ours')
            if operation=='stash':
                g(seed,'checkout','-q','--detach',base);(seed/'sample.dat').write_text('first\ntheirs\nlast\n');g(seed,'stash','push','-q');g(seed,'checkout','-q','main')
            args={'merge':['merge','--no-edit','-m','merge','side'],'cherry-pick':['cherry-pick',target],'revert':['revert','--no-edit',target],'rebase':['rebase','side'],'stash':['stash','apply']}[operation]
            results={}
            for label,tool in [('git',git),('den',den)]:
                work=case/'work'
                if work.exists():shutil.rmtree(work)
                shutil.copytree(seed,work);q=run(tool,args,work,False);results[label]=dict(status=q.returncode,stdout=q.stdout.hex(),stderr=q.stderr.hex(),state=state(work))
            d=results['den'];err=bytes.fromhex(d['stderr']);spelling=attrs.split('=',1)[-1] if '=' in attrs else 'merge'
            ok=d['status']==2 and b'merge' in err and b'sample.dat' in err
            if '=' in attrs and not attrs.startswith('conflict-marker-size'):ok=ok and spelling.encode() in err
            if attrs.startswith('conflict-marker-size'):ok=d['status']==2 and b'conflict-marker-size' in err and b'sample.dat' in err
            save(name,results,ok,dict(attributes=attrs))
    (out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n');failed=sum(not x['passed'] for x in rows)
    print(f'attribute-config: {len(rows)} rows, {failed} failures; zero skips',flush=True);return int(bool(failed))


if __name__=='__main__':raise SystemExit(main())
