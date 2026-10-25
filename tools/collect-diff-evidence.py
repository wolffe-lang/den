"""Keep new gate witnesses under the workflow's existing target/runs artifact.
No CI plan/pin change. Called on gate exit, including intentional plants.
"""
import json,pathlib,shutil,tarfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/'target/runs/vc04-evidence';OUT.mkdir(parents=True,exist_ok=True)
for pattern in ('diff*.json','rename-*.json','*checked.json'):
    for source in (ROOT/'target').glob(pattern):shutil.copyfile(source,OUT/source.name)
for tier in ('native','release'):
    base=ROOT/f'target/diffbinary-{tier}'
    if not base.exists():continue
    with tarfile.open(OUT/f'binary-{tier}.tar.gz','w:gz') as archive:
        for source in sorted(base.glob('summary*.json')):archive.add(source,arcname=source.name,recursive=False)
        for case in sorted(base.iterdir()):
            if not case.is_dir() or not (case/'old.bin').exists():continue
            for source in sorted(case.iterdir()):
                if source.is_file():archive.add(source,arcname=str(source.relative_to(base)),recursive=False)
print('vc04 evidence collected under target/runs/vc04-evidence',flush=True)
