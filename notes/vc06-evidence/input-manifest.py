import hashlib,json,pathlib,subprocess,sys
mode,root,manifest=sys.argv[1:];root=pathlib.Path(root);manifest=pathlib.Path(manifest)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
if mode=='create':
    paths=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
    selected=[p for p in paths if p and (p.startswith(('src/','probes/','tools/','tests/','ci/','.github/')) or p.endswith('.toml'))]
    rows={p:sha(root/p) for p in sorted(selected)}
    manifest.write_text(json.dumps(rows,indent=2)+'\n')
    print('RECORDED FUNCTIONAL INPUTS',len(rows))
else:
    rows=json.loads(manifest.read_text())
    for name,digest in rows.items():assert sha(root/name)==digest,name
    print('FUNCTIONAL INPUT MANIFEST UNCHANGED',len(rows),flush=True)
