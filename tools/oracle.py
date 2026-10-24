"""Compare stdout, stderr, status and EVERY .git file.
Only named loose-object-raw mode compares verified inflated bytes/oid (R4a).
Reviewed rows bind both whole results AND the case identity. A refusal is a
separate not-yet class, never counted as parity. No outputs are normalized.
"""
import argparse, hashlib, json, os, pathlib, re, shutil, stat, subprocess, sys, zlib
R=pathlib.Path(__file__).resolve().parent.parent

def snapshot(repo):
    result={}
    for p in sorted((repo/'.git').rglob('*')):
        key=p.relative_to(repo).as_posix()
        if p.is_symlink(): result[key]={'link':os.readlink(p)}
        elif p.is_file():result[key]={'mode':stat.S_IMODE(p.stat().st_mode),'hex':p.read_bytes().hex()}
    return result

def capture(command,repo,stdin=b''):
    p=subprocess.run(command,cwd=repo,input=stdin,capture_output=True,timeout=60)
    return {'stdout':p.stdout.hex(),'stderr':p.stderr.hex(),'status':p.returncode,'repository':snapshot(repo)}

def comparable(result, mode):
    """Named R4a loose-object comparison; every other byte/mode stays exact.
    Preserve original compressed bytes in evidence/review records. A corrupt
    checksum, trailing garbage, wrong oid or malformed raw header never equals.
    """
    if mode == 'exact': return result
    if mode != 'loose-object-raw': raise ValueError('unknown comparison mode '+mode)
    normalized = {**result, 'repository': dict(result['repository'])}
    for path, entry in result['repository'].items():
        if not re.fullmatch(r'\.git/objects/[0-9a-f]{2}/[0-9a-f]{38}', path): continue
        encoded = bytes.fromhex(entry['hex'])
        decoder = zlib.decompressobj()
        raw = decoder.decompress(encoded, 256_000_001)
        if len(raw) > 256_000_000 or not decoder.eof or decoder.unused_data:
            raise ValueError('invalid or oversized loose stream '+path)
        header, body = raw.split(b'\0', 1)
        kind, size = header.split(b' ')
        if kind not in (b'blob', b'tree', b'commit', b'tag') or size != str(len(body)).encode():
            raise ValueError('invalid loose header '+path)
        oid = path.split('/')[-2]+path.split('/')[-1]
        if hashlib.sha1(raw).hexdigest() != oid: raise ValueError('loose oid mismatch '+path)
        normalized['repository'][path] = {**entry, 'hex': raw.hex(), 'comparison': mode}
    return normalized

def equivalent(expected, actual, mode='loose-object-raw'):
    try: return comparable(expected, mode) == comparable(actual, mode)
    except (ValueError, KeyError, zlib.error): return False

def case_hash(case):return hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest()

def reviewed(row,case,git,den):
    return (git!=den and row.get('case_sha256')==case_hash(case) and row.get('git')==git
            and row.get('den')==den and bool(row.get('reason')) and bool(row.get('issue_or_ruling')))

def one(case,base,den,git):
    root=R/'target/runs'/case['name'];root.mkdir(parents=True,exist_ok=True)
    repo=root/'repo'
    def restore():
        if repo.exists():shutil.rmtree(repo)
        shutil.copytree(base/case['repo'],repo,symlinks=True)
        if case.get('prepare')=='dirty':
            (repo/'a.txt').write_bytes(b'alpha changed\n')
            (repo/'untracked').write_bytes(b'untracked\n')
        if case.get('config_append'):
            with (repo/'.git/config').open('ab') as f:f.write(case['config_append'].encode())
    args=[a.replace('{template}',os.environ['DEN_EMPTY_TEMPLATE']) for a in case['args']]
    replacements={}
    for key,rev in [('tree','HEAD^{tree}'),('commit','HEAD'),('blob','HEAD:a.txt')]:
        if any('{'+key+'}' in arg for arg in args):
            replacements[key]=subprocess.check_output([git,'rev-parse',rev],cwd=base/case['repo']).decode().strip()
    for key,value in replacements.items():args=[arg.replace('{'+key+'}',value) for arg in args]
    stdin=bytes.fromhex(case.get('stdin_hex',''))
    restore(); expected=capture([git,*args],repo,stdin)
    restore(); before=snapshot(repo); actual=capture([den,*args],repo,stdin)
    (root/'git.json').write_text(json.dumps(expected,sort_keys=True)+'\n')
    (root/'den.json').write_text(json.dumps(actual,sort_keys=True)+'\n')
    if case.get('kind')=='version':
        ok=(bytes.fromhex(actual['stdout'])==b'den 0.0.0 (built with wolf 0.2.35)\n'
            and actual['stderr']=='' and actual['status']==0 and actual['repository']==before
            and bytes.fromhex(expected['stdout']).startswith(b'git version ') and expected['status']==0)
        return 'shape-pass' if ok else 'FAIL'
    if equivalent(expected,actual,case.get('comparison','loose-object-raw')):return 'parity'
    refusal=f"den: not yet implemented: {case.get('refusal_feature',args[0])} ({case['lane']})\n".encode().hex()
    if (actual['status']==2 and actual['stdout']=='' and actual['stderr']==refusal
            and actual['repository']==before):return 'not-yet'
    p=R/'tests/review'/f"{case['name']}.json"
    if p.exists() and reviewed(json.loads(p.read_text()),case,expected,actual):return 'reviewed'
    return 'FAIL'

def selftest():
    case={'name':'one-byte'};a={'stdout':'61','stderr':'','status':0,'repository':{}}
    b={**a,'stdout':'62'}
    row={'case_sha256':case_hash(case),'git':a,'den':b,'reason':'plant','issue_or_ruling':'vc00 selftest'}
    assert reviewed(row,case,a,b)
    assert not reviewed(row,case,a,{**b,'stdout':'63'})
    assert not reviewed(row,{'name':'other'},a,b)
    assert not reviewed(row,case,a,a)
    # Exercise the real subprocess capture, including repository-only mutation.
    root=R/'target/selftest';(root/'.git').mkdir(parents=True,exist_ok=True)
    (root/'.git'/'HEAD').write_bytes(b'a')
    before=capture([sys.executable,'-I','-c','print("a",end="")'],root)
    after=capture([sys.executable,'-I','-c','print("b",end="")'],root)
    assert before!=after
    mutated=capture([sys.executable,'-I','-c','from pathlib import Path;Path(".git/HEAD").write_bytes(b"b");print("a",end="")'],root)
    assert before['stdout']==mutated['stdout'] and before!=mutated
    fixture=R/'target/corpus'
    fake=root/'den'
    fake.write_text('#!/bin/sh\nprintf "den 0.0.1 (built with wolf 0.2.35)\\n"\n')
    fake.chmod(0o755)
    version={'name':'selftest-version','repo':'two','args':['--version'],'kind':'version'}
    assert one(version,fixture,str(fake),os.environ['DEN_GIT'])=='FAIL'
    raw=b'blob 3\0abc';oid=hashlib.sha1(raw).hexdigest();key='.git/objects/'+oid[:2]+'/'+oid[2:]
    def object_result(encoded):
        return {**a,'repository':{key:{'mode':0o444,'hex':encoded.hex()}}}
    x=object_result(zlib.compress(raw,0));y=object_result(zlib.compress(raw,1))
    assert x!=y and equivalent(x,y) and not equivalent(x,y,'exact')
    bad=bytearray(zlib.compress(raw));bad[-1]^=1
    assert not equivalent(x,object_result(bad))
    assert not equivalent(x,object_result(zlib.compress(b'blob 3\0abd')))
    assert not equivalent(x,object_result(zlib.compress(raw)+b'junk'))
    assert not equivalent(x,{**y,'repository':{**y['repository'],'.git/HEAD':{'hex':'61','mode':0o644}}})
    print('selftest: loose-object-raw accepts representation changes; checksum/oid/trailing and non-object bytes remain gated')
    print('selftest: actual classifier rejects planted one-byte version; stdout/repository plants rejected; exact review binding passes')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--filter',default='');ap.add_argument('--selftest',action='store_true')
    ap.add_argument('--strict',action='store_true');ap.add_argument('--den',default=os.environ.get('DEN_BIN',str(R/'target/native/den')))
    ap.add_argument('--corpus',default=str(R/'target/corpus'));a=ap.parse_args()
    if a.selftest:selftest();return
    cases=[c for c in json.loads((R/'tests/cases.json').read_text()) if a.filter in c['name']]
    if not cases:sys.exit('oracle: filter selected no cases')
    counts={}
    for c in cases:
        result=one(c,pathlib.Path(a.corpus),str(pathlib.Path(a.den).resolve()),os.environ['DEN_GIT'])
        counts[result]=counts.get(result,0)+1;print(f"{result}: {c['name']}",flush=True)
    print(json.dumps(counts,sort_keys=True))
    sys.exit(1 if counts.get('FAIL') or (a.strict and counts.get('not-yet')) else 0)
if __name__=='__main__':main()
