"""Independent Git 2.56.0 black-box index/commit contract measurements.
Reads documented index records, never implementation files or sample templates.
"""
import hashlib, json, os, pathlib, shutil, struct, subprocess, time
R = pathlib.Path(__file__).resolve().parent.parent
G = os.environ['DEN_GIT']
base = R / 'target/vc03-measure'
if base.exists():
    shutil.rmtree(base)
base.mkdir(parents=True)
commands = []
def git(repo, *args, **kwargs):
    p = subprocess.run([G, *args], cwd=repo, capture_output=True, **kwargs)
    commands.append(dict(repo=repo.name, args=args, status=p.returncode,
                         stdout=p.stdout.hex(), stderr=p.stderr.hex()))
    assert p.returncode == 0, commands[-1]
    return p.stdout

def fresh(name):
    p = base / name
    p.mkdir()
    git(p, 'init', '-q', '--template=' + os.environ['DEN_EMPTY_TEMPLATE'])
    return p

def index(repo):
    raw = (repo / '.git/index').read_bytes()
    assert raw[:4] == b'DIRC' and raw[-20:] == hashlib.sha1(raw[:-20]).digest()
    version, count = struct.unpack_from('>II', raw, 4)
    assert version == 2
    pos = 12
    entries = []
    for _ in range(count):
        start = pos
        words = struct.unpack_from('>10I', raw, pos)
        flags = struct.unpack_from('>H', raw, pos + 60)[0]
        assert not flags & 0x4000
        end = raw.index(b'\0', pos + 62)
        name = raw[pos + 62:end]
        pos = start + ((end + 1 - start + 7) // 8) * 8
        st = (repo / os.fsdecode(name)).lstat()
        observed = [st.st_ctime_ns // 10**9, st.st_ctime_ns % 10**9,
                    st.st_mtime_ns // 10**9, st.st_mtime_ns % 10**9,
                    st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid, st.st_size]
        observed = [v & 0xffffffff for v in observed]
        entries.append(dict(name_hex=name.hex(), index_stat=words,
                            own_worktree_stat=observed, equal=list(words) == observed))
    extensions = []
    while pos < len(raw) - 20:
        name = raw[pos:pos+4].decode('ascii')
        n = struct.unpack_from('>I', raw, pos+4)[0]
        extensions.append(dict(name=name, payload_hex=raw[pos+8:pos+8+n].hex()))
        pos += 8+n
    assert pos == len(raw)-20
    return dict(version=version, entries=entries, extensions=extensions, raw_hex=raw.hex())

repo = fresh('two')
(repo/'a').write_bytes(b'alpha\n')
(repo/'b').write_bytes(b'beta\n')
git(repo, 'add', '.')
observations = {'after_add': index(repo)}
git(repo, 'write-tree')
observations['after_write_tree'] = index(repo)
git(repo, 'commit', '-qm', 'root')
observations['after_commit'] = index(repo)
(repo/'c').write_bytes(b'gamma\n')
git(repo, 'add', 'c')
observations['after_add_new_file'] = index(repo)
old = git(repo, 'rev-parse', 'HEAD').decode().strip()
assert not (repo/'.git/ORIG_HEAD').exists()
git(repo, 'commit', '--amend', '-qm', 'amended')
observations['amend_without_orig_head'] = dict(old_head=old,
    new_head=git(repo, 'rev-parse', 'HEAD').decode().strip(),
    orig_head_exists=(repo/'.git/ORIG_HEAD').exists())
(repo/'.git/ORIG_HEAD').write_text(old+'\n')
git(repo, 'commit', '--amend', '--allow-empty', '-qm', 'amended again')
observations['amend_existing_orig_head'] = dict(before=old+'\n',
    after=(repo/'.git/ORIG_HEAD').read_text())
now = fresh('date-now')
for iteration in range(2):
    git(now, 'commit', '--allow-empty', '-qm', 'now', '--date=now')
    observations['date_now_'+str(iteration)] = git(now, 'show', '-s', '--format=%at %ct').decode()
    if iteration == 0:
        time.sleep(2)
observations['commands'] = commands
observations['oracle_sha256'] = hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()
out = R / 'target/vc03-measure.json'
out.write_text(json.dumps(observations, indent=2)+'\n')
print(json.dumps({k: v for k, v in observations.items() if k.startswith(('amend_', 'date_'))}, indent=2))
for k in ('after_add', 'after_write_tree', 'after_commit', 'after_add_new_file'):
    print(k, observations[k]['extensions'])
print(out)
