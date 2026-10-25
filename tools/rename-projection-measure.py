"""Infer a modular projection from independently isolated oracle collisions.

Fit each small integer coefficient in both word orders with full-precision,
32-bit and 64-bit arithmetic. A modulus must divide every projected pair's
nonzero difference, so a GCD exposes admissible moduli without searching one.
The first 16 collisions fit; remaining collisions validate the selected model.
"""
import argparse
import hashlib
import json
import math
import pathlib
import runpy

ROOT = pathlib.Path(__file__).resolve().parent.parent
FP = runpy.run_path(str(ROOT/'tools/rename-fingerprint-measure.py'))['fingerprint']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('report',type=pathlib.Path)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    raw=args.report.read_bytes()
    rows=json.loads(raw)['collisions']
    pairs=[tuple(FP(bytes.fromhex(r[key]),64,7,'add',False) for key in ('old_hex','new_hex')) for r in rows]
    assert len(pairs)>=24 and all(a!=b for a,b in pairs)
    models=[]
    def project(v,k,reverse,bits):
        a,b=v&0xffffffff,v>>32
        if reverse:a,b=b,a
        n=a+k*b
        return n if bits==0 else n&((1<<bits)-1)
    for reverse in (False,True):
        for bits in (0,32,64):
            for k in range(65536):
                modulus=0
                for a,b in pairs[:16]:
                    modulus=math.gcd(modulus,abs(project(a,k,reverse,bits)-project(b,k,reverse,bits)))
                    if modulus==1:break
                if modulus>1:
                    validation=[i for i,(a,b) in enumerate(pairs[16:],16) if (project(a,k,reverse,bits)-project(b,k,reverse,bits))%modulus]
                    models.append({'coefficient':k,'reverse':reverse,'bits':bits,'gcd':modulus,'validation_failures':validation})
            print('searched reverse',reverse,'bits',bits,'survivors',models,flush=True)
    args.output.write_text(json.dumps({'collision_report_sha256':hashlib.sha256(raw).hexdigest(),
        'fit_pairs':16,'validation_pairs':len(pairs)-16,'coefficient_range':[0,65535],'models':models},indent=2)+'\n')

if __name__=='__main__':main()
