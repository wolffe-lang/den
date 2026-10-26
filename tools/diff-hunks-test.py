"""Byte comparison of original wolf hunk output against pinned Git.

Two capture-bound equal-cost witnesses remain proposed R-vc04-3 differences.
--strict keeps the unmodified byte comparison as a visible red report.
Small deterministic edit cases include missing LF, duplicate lines, moved
blocks and indentation. Both default and disabled indent heuristics are
captured, never normalized into agreement. Every failed case retains inputs.
"""
import argparse
import hashlib
import json
import os
import pathlib
import random
import subprocess

ROOT=pathlib.Path(__file__).resolve().parent.parent


def fixtures():
    yield 'empty',b'',b''
    for old in (b'',b'one',b'one\n',b'one\ntwo',b'one\r\ntwo\r\n'):
        for new in (b'',b'one',b'one\n',b'one\ntwo',b'one\r\ntwo\r\n'):
            yield f'boundary-{old.hex()}-{new.hex()}',old,new
    base=[f'line{i:03}\n'.encode() for i in range(24)]
    for at in (0,1,3,8,20,23,24):
        yield f'insert-{at}',b''.join(base),b''.join(base[:at]+[b'new\n']+base[at:])
        yield f'delete-{at}',b''.join(base),b''.join(base[:at]+base[at+1:])
        yield f'replace-{at}',b''.join(base),b''.join(base[:at]+[b'new\n']+base[at+1:])
    rng=random.Random(0x76633034)
    for i in range(120):
        lines=[rng.choice((b'a\n',b'b\n',b'c\n',b'\n',b'  body\n',b'}\n')) for _ in range(rng.randrange(1,24))]
        after=list(lines)
        for _ in range(rng.randrange(1,5)):
            at=rng.randrange(len(after)+1)
            if rng.randrange(3)==0 and after:
                del after[min(at,len(after)-1)]
            else:
                after[at:at]=[rng.choice((b'a\n',b'b\n',b'new\n',b'\n',b'  body\n'))]
        yield f'seeded-{i}',b''.join(lines),b''.join(after)
    for count in (1,2,3,4):
        block=b'function() {\n  work();\n}\n\n'
        yield f'move-{count}',block*count+b'end\n',b'end\n'+block*count


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tier',choices=('native','release'),required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    parser.add_argument('--strict',action='store_true')
    args=parser.parse_args()
    base=ROOT/f'target/hunks-{args.tier}'
    base.mkdir(parents=True,exist_ok=True)
    old,new=base/'a',base/'b'
    apply=base/'apply';apply.mkdir(exist_ok=True)
    git=os.environ['DEN_GIT']
    driver=ROOT/f'target/{args.tier}/difftext-client'
    review=json.loads((ROOT/'tests/review/diff-hunks.json').read_text())
    results=[]
    for name,a,b in fixtures():
        old.write_bytes(a); new.write_bytes(b)
        for context in (0,1,3,10):
            p=subprocess.run([str(driver),'hunks',str(old),str(new),str(context)],capture_output=True,timeout=30)
            assert p.returncode==0 and not p.stderr,(name,context,p.returncode,p.stderr)
            # Independent semantic check, including each named alignment difference.
            if p.stdout:
                patch=b'diff --git a/file b/file\n--- a/file\n+++ b/file\n'+p.stdout
                (apply/'file').write_bytes(a)
                for reverse,expected_body in ((False,b),(True,a)):
                    command=[git,'apply','--unidiff-zero','--whitespace=nowarn',*(['-R'] if reverse else []),'-']
                    # This patch is intentionally relative to the scratch apply directory,
                    # not the enclosing den checkout. Git otherwise silently skips it
                    # when this harness runs from a clone rather than an exported tree.
                    applied=subprocess.run(command,cwd=apply,input=patch,capture_output=True,timeout=30,
                        env={**os.environ,'GIT_CEILING_DIRECTORIES':str(base.resolve())})
                    assert applied.returncode==0,(name,context,reverse,applied.stderr)
                    assert (apply/'file').read_bytes()==expected_body,(name,context,reverse,'wrong reconstruction')
            else:assert a==b,(name,'empty edit script')
            oracle={} 
            for option in ('--indent-heuristic','--no-indent-heuristic'):
                g=subprocess.run([git,'diff','--no-index',option,f'-U{context}',str(old),str(new)],capture_output=True,timeout=30)
                assert g.returncode in (0,1) and not g.stderr,(name,g.returncode,g.stderr)
                start=g.stdout.find(b'@@ ')
                expected=g.stdout[start:] if start>=0 else b''
                oracle[option]=expected
            results.append({'name':name,'context':context,'old_hex':a.hex(),'new_hex':b.hex(),
                'actual_hex':p.stdout.hex(),'oracle_hex':oracle['--indent-heuristic'].hex(),
                'no_indent_hex':oracle['--no-indent-heuristic'].hex(),
                'default_equal':p.stdout==oracle['--indent-heuristic'],
                'no_indent_equal':p.stdout==oracle['--no-indent-heuristic'],
                'oracle_heuristics_differ':oracle['--indent-heuristic']!=oracle['--no-indent-heuristic']})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'oracle_sha256':hashlib.sha256(pathlib.Path(git).read_bytes()).hexdigest(),
        'driver_sha256':hashlib.sha256(driver.read_bytes()).hexdigest(),'rows':results},indent=2)+'\n')
    for key in ('default_equal','no_indent_equal','oracle_heuristics_differ'):
        print(key,sum(r[key] for r in results),'/',len(results),flush=True)
    failures=[(r['name'],r['context']) for r in results if not r['default_equal']]
    print('failures',failures[:30],flush=True)
    unresolved=[];reviewed=0
    for row in results:
        if row['default_equal']:continue
        record=next((x for x in review['rows'] if x['name']==row['name'] and x['context']==row['context']),None)
        bound={k:row[k] for k in ('name','context','old_hex','new_hex','actual_hex','oracle_hex')}
        if record is None or record['capture']!=bound:unresolved.append((row['name'],row['context']))
        else:reviewed+=1
    print('hunks:',len(results)-len(failures),'byte-identical;',reviewed,'named proposed R-vc04-3 differences;',len(unresolved),'unreviewed',flush=True)
    assert not unresolved,unresolved
    if args.strict:assert not failures,failures

if __name__=='__main__':main()
