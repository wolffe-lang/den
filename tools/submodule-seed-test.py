"""The retained seed must hold the inodes referenced by its original index.

Load only seed/settle from the command harness, without running its CLI. The
comparison worlds must be independent copies, never hard-linked to the seed.
"""
import ast
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent
(ROOT / 'target').mkdir(exist_ok=True)
source = ast.parse((ROOT / 'tools/submodule-test.py').read_text())
functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in ('seed', 'settle')]
assert len(functions) == 2
with tempfile.TemporaryDirectory(prefix='seed-inodes-', dir=ROOT / 'target') as tmp:
    root = Path(tmp)
    world = root / 'world'
    context = dict(root=root, world=world, seeds={}, shutil=shutil, os=os)
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'submodule-seed-functions', 'exec'), context)
    original = {}

    def build(base):
        (base / 'c/.git').mkdir(parents=True)
        (base / 'c/file').write_bytes(b'original\n')
        (base / 'c/.git/index').write_bytes(b'original index\n')
        (base / 'c/link').symlink_to('file')
        original['file'] = (base / 'c/file').stat().st_ino
        original['index'] = (base / 'c/.git/index').stat().st_ino

    kept = context['seed']('probe', build)
    try:
        assert (kept / 'c/file').stat().st_ino == original['file'], 'seed released the original file inode'
        assert (kept / 'c/.git/index').stat().st_ino == original['index'], 'seed released the original index inode'
        shutil.rmtree(world)
        assert (kept / 'c/file').stat().st_nlink == 1, 'seed does not own the last link'
        shutil.copytree(kept, world, symlinks=True)
        assert (world / 'c/file').stat().st_ino != original['file'], 'comparison reused the seed inode'
        assert (world / 'c/.git/index').stat().st_ino != original['index'], 'comparison shares its index'
        (world / 'c/file').write_bytes(b'changed\n')
        (world / 'c/.git/index').write_bytes(b'changed index\n')
        assert (kept / 'c/file').read_bytes() == b'original\n'
        assert (kept / 'c/.git/index').read_bytes() == b'original index\n'
        assert (world / 'c/link').is_symlink() and os.readlink(world / 'c/link') == 'file'
    except AssertionError as e:
        print('FAIL submodule-seed-inodes ' + str(e), flush=True)
        raise SystemExit(1)
print('PASS submodule-seed-inodes original inodes held; comparison files/index independent', flush=True)
