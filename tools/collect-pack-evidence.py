"""Keep all new gate records in the existing CI artifact tree, including reds."""
import pathlib, shutil
r=pathlib.Path(__file__).resolve().parents[1]
out=r/'target/runs/vc09-evidence'; out.mkdir(parents=True,exist_ok=True)
for pattern in ('pack-*/results.json','*-packed.json','pack-checked.json'):
    for path in (r/'target').glob(pattern):
        shutil.copyfile(path,out/str(path.relative_to(r/'target')).replace('/','_'))
