"""Verify the detached signature of the UNCOMPRESSED tar, build default git.
Only build tools access the implementation. This script never opens a source
file. Cache identity includes archive, signature, key, image and make args.
"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, tarfile, tomllib
R = pathlib.Path(__file__).resolve().parent.parent
pin = tomllib.loads((R / 'den-oracle.toml').read_text())['oracle']
def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
key = hashlib.sha256(json.dumps(pin, sort_keys=True).encode()).hexdigest()
cache = R / 'target/oracle' / key
binary = cache / 'root/opt/git/bin/git'
if binary.exists() and '--rebuild' not in sys.argv:
    run(str(binary), 'version', '--build-options')
    print(binary)
    sys.exit(0)
if os.environ.get('DEN_IN_CONTAINER') != '1':
    sys.exit('fetch-oracle: build requires the pinned container')
cache.mkdir(parents=True, exist_ok=True)
download = cache / 'download'; download.mkdir(exist_ok=True)
for name, urlkey, digestkey in [('git.tar.xz','url','sha256'),('git.tar.sign','sig_url','sig_sha256'),('key.asc','key_url','key_sha256')]:
    p = download / name
    if not p.exists():
        run('curl','-fsSL','--retry','3',pin[urlkey],'-o',str(p))
    for read in (1,2):
        have = sha(p); print(f'{name} read {read}: {have}', flush=True)
        if have != pin[digestkey]: sys.exit(f'REFUSED: {name} digest')
keys = cache / 'keys'; keys.mkdir(mode=0o700, exist_ok=True)
run('gpg','--homedir',str(keys),'--batch','--import',str(download/'key.asc'))
with (download/'git.tar').open('wb') as out:
    run('xz','-dc',str(download/'git.tar.xz'),stdout=out)
r = run('gpg','--homedir',str(keys),'--batch','--status-fd=1','--verify',str(download/'git.tar.sign'),str(download/'git.tar'),capture_output=True,text=True)
print(r.stdout, end=''); print(r.stderr,end='')
assert '[GNUPG:] VALIDSIG '+pin['signing_fingerprint']+' ' in r.stdout
assert pin['primary_fingerprint'] in r.stdout
# Extract into a new empty directory; do not run Python from the tarball.
source = cache/'source'
if source.exists(): shutil.rmtree(source)
source.mkdir()
run('tar','-xf',str(download/'git.tar'),'-C',str(source))
build = source/'git-2.56.0'
run('make','-C',str(build),'-j4','prefix=/opt/git')
run('make','-C',str(build),'prefix=/opt/git','DESTDIR='+str(cache/'root'),'install')
run(str(binary),'version','--build-options')
print('oracle binary sha256',sha(binary))
print(binary)
