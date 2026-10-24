"""Generate actual format bytes using the pinned oracle, never type examples."""
import hashlib,json,os,pathlib,shutil,subprocess,zlib
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];O=R/'target/formats';O.mkdir(parents=True,exist_ok=True)
repo=R/'target/corpus/two'
def git(*args,data=None,cwd=repo):
 p=subprocess.run([G,*args],cwd=cwd,input=data,capture_output=True,check=True);return p.stdout
def save(name,data):
 (O/name).write_bytes(data)
 (O/(name+'.hex')).write_text('\n'.join(f'{i:08x}  '+data[i:i+16].hex(' ') for i in range(0,len(data),16))+'\n')
ids={}
ids['empty-blob']=git('hash-object','-w','--stdin',data=b'').decode().strip()
ids['empty-tree']=git('mktree',data=b'').decode().strip()
ids['minimal-commit']=git('commit-tree',ids['empty-tree'],'-m','').decode().strip()
ids['blob']=git('rev-parse','HEAD:a.txt').decode().strip()
ids['tree']=git('rev-parse','HEAD^{tree}').decode().strip()
ids['commit']=git('rev-parse','HEAD').decode().strip()
for name,oid in ids.items():
 wire=(repo/'.git/objects'/oid[:2]/oid[2:]).read_bytes()
 save(name+'.loose',wire);save(name+'.raw',zlib.decompress(wire))
save('two-file.index',(repo/'.git/index').read_bytes())
# Two objects exactly (two blobs), no implicit traversal from a commit.
oids=[git('rev-parse','HEAD:a.txt').strip(),git('rev-parse','HEAD:b.txt').strip()]
pack=git('pack-objects','--stdout',data=b'\n'.join(oids)+b'\n')
save('two-object.pack',pack)
(O/'two-object.pack').write_bytes(pack)
git('index-pack','--index-version=2',str(O/'two-object.pack'))
save('two-object.idx',(O/'two-object.idx').read_bytes())
# Ordering witness: directory 'a' sorts as if terminated by '/', after 'a.c'.
empty=ids['empty-tree'];blob=ids['blob']
order=git('mktree',data=f'040000 tree {empty}\ta\n100644 blob {blob}\ta.c\n100644 blob {blob}\ta0\n'.encode()).decode().strip()
save('tree-order.raw',git('cat-file','tree',order))
# Porcelain bytes come from the exact differential outputs, including stderr/status.
for name in ('log-default','log-oneline','status-short','status-long','diff','diff-renames','blame'):
 p=R/'target/runs'/name/'git.json';row=json.loads(p.read_text())
 for field in ('stdout','stderr'):save(name+'.'+field,bytes.fromhex(row[field]))
 (O/(name+'.status')).write_text(str(row['status'])+'\n')
# Default loose compression vs levels. Every probe uses an independent repository.
data=(b'line of repeated text\n'*4096)+bytes(range(256))*20
header=f'blob {len(data)}\0'.encode();levels={}
for label,opts in [('default',[]),('core.compression=9',['-c','core.compression=9']),('core.looseCompression=0',['-c','core.looseCompression=0'])]:
 p=O/label
 if p.exists():shutil.rmtree(p)
 p.mkdir();git('init','-q','--template='+os.environ['DEN_EMPTY_TEMPLATE'],cwd=p)
 oid=git(*opts,'hash-object','-w','--stdin',data=data,cwd=p).decode().strip()
 wire=(p/'.git/objects'/oid[:2]/oid[2:]).read_bytes()
 levels[label]={'size':len(wire),'matching_zlib_levels':[i for i in range(10) if zlib.compress(header+data,i)==wire],'sha256':hashlib.sha256(wire).hexdigest()}
summary={'oids':ids,'sizes':{p.name:p.stat().st_size for p in O.glob('*.loose')},'pack_objects':int.from_bytes(pack[8:12],'big'),'compression':levels}
(O/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps(summary,indent=2,sort_keys=True))
