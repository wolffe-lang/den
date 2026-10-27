"""Pack fixture objects with the pinned executable, never a host Git."""
import pathlib, subprocess

def pack_fixture(git, repo):
    repo = pathlib.Path(repo)
    def run(*args, data=None):
        p = subprocess.run([git, *args], cwd=repo, input=data, capture_output=True)
        assert p.returncode == 0, (args, p.stdout, p.stderr)
        return p.stdout
    # Repack normal reachable/reflog objects using the command the contract names.
    before = set(run('cat-file', '--batch-all-objects', '--batch-check=%(objectname)').splitlines())
    run('-c', 'repack.writeBitmaps=false', 'repack', '-a', '-d', '--keep-unreachable')
    # Raw-object history fixtures also contain deliberately unreferenced objects.
    # Pack their complete namespace, then prune only duplicates, never prune data.
    loose = [p for p in (repo/'.git/objects').glob('[0-9a-f][0-9a-f]/*') if p.is_file() and len(p.name)==38]
    if loose:
        names = b''.join((p.parent.name+p.name+'\n').encode() for p in loose)
        run('pack-objects', '--delta-base-offset', '.git/objects/pack/pack', data=names)
        run('prune-packed')
    packs = list((repo/'.git/objects/pack').glob('*.pack'))
    if not packs and not before:
        run('pack-objects', '.git/objects/pack/pack', data=b'')
        packs = list((repo/'.git/objects/pack').glob('*.pack'))
    assert packs, 'packed fixture has no pack'
    assert not list((repo/'.git/objects').glob('[0-9a-f][0-9a-f]/*')), 'loose fixture object remained'
    after = set(run('cat-file', '--batch-all-objects', '--batch-check=%(objectname)').splitlines())
    assert before == after, ('pack fixture namespace changed', before-after, after-before)
    return len(packs)
