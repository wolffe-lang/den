"""Generate actual format bytes using the pinned oracle, never type examples."""
import hashlib,json,os,pathlib,shutil,subprocess,zlib
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];O=R/'target/formats';O.mkdir(parents=True,exist_ok=True)
repo=O/'repo'
if repo.exists():shutil.rmtree(repo)
shutil.copytree(R/'target/corpus/two',repo,symlinks=True)
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
# Additional format bodies and documentary skip examples, all from the oracle.
commit=ids['commit']
tag=f'object {commit}\ntype commit\ntag sample\ntagger Den Tester <den@example.invalid> 1700000000 +0000\n\nsample tag\n'.encode()
tagid=git('mktag',data=tag).decode().strip()
save('tag.raw',git('cat-file','tag',tagid))
save('HEAD',(repo/'.git/HEAD').read_bytes())
save('config',(repo/'.git/config').read_bytes())
save('reflog',(repo/'.git/logs/HEAD').read_bytes())
save('ref-main',(repo/'.git/refs/heads/main').read_bytes())
e={**os.environ,'GIT_PROTOCOL':'version=2'}
pkt=subprocess.run([G,'upload-pack','--advertise-refs',str(repo)],env=e,capture_output=True,check=True).stdout
save('v2-advertisement',pkt)
git('commit-graph','write','--reachable')
save('commit-graph',(repo/'.git/objects/info/commit-graph').read_bytes())
git('bundle','create',str(O/'sample.bundle'),'--all')
save('bundle',(O/'sample.bundle').read_bytes())
(repo/'a.txt').chmod(0o755)
save('diff-mode.stdout',git('diff'))
(repo/'a.txt').chmod(0o644)
(repo/'b.txt').write_bytes(b'beta\x00changed\n')
save('diff-binary.stdout',git('diff'))
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
