#!/usr/bin/env python3
"""den#145: every package manifest names the den modules its files use.

den's own build resolves a sibling directory of src/ as a module, so a
module that starts to `use` another one still compiles from the root while
its src/<module>/wolf.pkg does not list the new dependency. A probe builds
that module as a path dependency, where only the manifest's deps resolve,
and the probe is then the first to fail (E0301). This row finds the gap
before any build:

  1. each wolf.pkg under src/ and probes/ lists, by name, every den module
     (a directory of src/) that a `use` line in its .lu files names;
  2. a den module that some wolf.pkg names as a path dependency and that has
     no wolf.pkg of its own uses no other den module (nothing would resolve
     it there).

`std` and names that are not directories of src/ are not den modules.
Before the tree, a self-test plants both gaps in a scratch tree and requires
each to be found by name, and a clean scratch tree to pass.
"""
import re
import sys
import tempfile
from pathlib import Path

USE = re.compile(r'\s*(?:pub\s+)?use\s+([A-Za-z_]\w*)')
DEP = re.compile(r'(\w+)\s*:\s*\{\s*path\s*:\s*"([^"]+)"')


def uses(directory):
    """(module name, 'file:line') for each `use` of a name, first site kept."""
    found = {}
    for path in sorted(directory.glob('*.lu')):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = USE.match(line)
            if match:
                found.setdefault(match.group(1), f'{path.name}:{number}')
    return found


def check(root):
    src = root / 'src'
    modules = {path.name for path in src.iterdir() if path.is_dir()}
    failures, manifests, edges = [], 0, 0
    bare = {}
    for manifest in sorted(list(src.glob('*/wolf.pkg')) + list((root / 'probes').glob('*/wolf.pkg'))):
        manifests += 1
        package = manifest.parent
        rel = manifest.relative_to(root)
        deps = {}
        for name, target in DEP.findall(manifest.read_text()):
            deps[name] = target
            resolved = (package / target).resolve()
            if resolved.parent == src.resolve() and not (resolved / 'wolf.pkg').exists():
                bare.setdefault(resolved.name, rel)
        for name, site in sorted(uses(package).items()):
            if name in modules and not (package.parent == src and name == package.name):
                edges += 1
                if name not in deps:
                    failures.append(f'{package.relative_to(root)}/{site} uses {name}, which {rel} does not list')
    for name, named_by in sorted(bare.items()):
        for used, site in sorted(uses(src / name).items()):
            if used in modules and used != name:
                failures.append(f'src/{name}/{site} uses {used}, but src/{name} has no wolf.pkg '
                                f'and {named_by} names it as a path dependency')
    return failures, manifests, edges


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def self_test():
    with tempfile.TemporaryDirectory(prefix='module-deps-') as scratch:
        root = Path(scratch)
        write(root / 'src/leaf/leaf.lu', 'use std.io\n')
        write(root / 'src/mid/mid.lu', 'use leaf\n')
        write(root / 'src/top/wolf.pkg', 'pkg {\n    deps: {mid: {path: "../mid"}},\n}\n')
        write(root / 'src/top/top.lu', 'use mid\nuse std.fs\n')
        write(root / 'probes/client/wolf.pkg', 'pkg {\n    deps: {top: {path: "../../src/top"}},\n}\n')
        write(root / 'probes/client/main.lu', 'use top\n')
        write(root / 'src/mid/wolf.pkg', 'pkg {\n    deps: {leaf: {path: "../leaf"}},\n}\n')
        failures, _, _ = check(root)
        assert failures == [], failures
        (root / 'src/mid/wolf.pkg').write_text('pkg {\n    deps: {},\n}\n')
        failures, _, _ = check(root)
        assert failures == ['src/mid/mid.lu:1 uses leaf, which src/mid/wolf.pkg does not list'], failures
        (root / 'src/mid/wolf.pkg').unlink()
        failures, _, _ = check(root)
        assert failures == ['src/mid/mid.lu:1 uses leaf, but src/mid has no wolf.pkg '
                            'and src/top/wolf.pkg names it as a path dependency'], failures
        write(root / 'src/mid/wolf.pkg', 'pkg {\n    deps: {leaf: {path: "../leaf"}},\n}\n')
        write(root / 'probes/client/main.lu', 'use top\nuse leaf\n')
        failures, _, _ = check(root)
        assert failures == ['probes/client/main.lu:2 uses leaf, which probes/client/wolf.pkg does not list'], failures


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    self_test()
    failures, manifests, edges = check(root)
    for failure in failures:
        print(f'FAIL module-deps: {failure}')
    if failures:
        print(f'module-deps: {len(failures)} unlisted of {edges} uses in {manifests} manifests')
        return 1
    print(f'PASS module-deps: {edges} uses of den modules in {manifests} manifests, every one listed; self-test caught both planted gaps')
    return 0


if __name__ == '__main__':
    sys.exit(main())
