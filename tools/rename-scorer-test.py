"""The six inherited oracle reports, plus fresh isolated projection collisions.

Runs the public wolf client. Never calls a Python implementation as the tool
under test, never substitutes a predicted score for an observed oracle score.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tier',choices=('native','release'),required=True)
    args=parser.parse_args()
    driver=ROOT/f'target/{args.tier}/delta-client'
    base=ROOT/f'target/rename-scorer-{args.tier}'
    base.mkdir(parents=True,exist_ok=True)
    results=[]
    for suite in ('initial','random','hash','structural','equivalence','wrap','collisions'):
        path=ROOT/f'notes/vc03-evidence/rename-measure-{suite}.json'
        if suite=='collisions':
            path=ROOT/'notes/vc04-evidence/collisions.json'
            cases=[{**r,'name':f'isolated-{i}','score_at_1pct':100,'default_rename':True} for i,r in enumerate(json.loads(path.read_text())['collisions'])]
        else:
            cases=json.loads(path.read_text())['cases']
        suite_results=[]
        for row in cases:
            old,new=base/'old',base/'new'
            old.write_bytes(bytes.fromhex(row['old_hex']))
            new.write_bytes(bytes.fromhex(row['new_hex']))
            p=subprocess.run([str(driver),'similarity',str(old),str(new)],capture_output=True,timeout=10)
            assert p.returncode==0 and not p.stderr,(suite,row['name'],p.returncode,p.stdout,p.stderr)
            common,maximum,units,percent=map(int,p.stdout.split())
            ok=percent==(row['score_at_1pct'] or 0) and (units>=30000)==row['default_rename']
            suite_results.append({'name':row['name'],'common':common,'maximum':maximum,'units':units,
                                  'percent':percent,'oracle':row['score_at_1pct'],'default_rename':row['default_rename'],'ok':ok})
        results.append({'suite':suite,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':suite_results})
        print(suite, sum(r['ok'] for r in suite_results),'/',len(suite_results),flush=True)
    output=ROOT/f'target/rename-scorer-{args.tier}.json'
    output.write_text(json.dumps({'tier':args.tier,'driver_sha256':hashlib.sha256(driver.read_bytes()).hexdigest(),'suites':results},indent=2)+'\n')
    failed=[(s['suite'],r['name']) for s in results for r in s['rows'] if not r['ok']]
    assert not failed,failed
    assert sum(len(s['rows']) for s in results)==1534
    print('PASS 1510 inherited pairs plus 24 independent collisions; zero skips')

if __name__=='__main__':main()
