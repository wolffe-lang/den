#!/usr/bin/env python3
"""Pinned Git attribute effects: non-diff commands, binary display and drivers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

PIN = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    p.add_argument('--den')
    p.add_argument('--dev-oracle', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    git = os.environ['DEN_GIT']
    sha = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin'
        print('DEV ORACLE (not pinned Linux evidence):', sha, flush=True)
    else:
        assert sha == PIN
    den = a.den or str(root / 'target' / a.tier / 'den')
    out = root / 'target/runs' / ('attribute-effects-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    def run(tool, argv, cwd, check=True):
        q = subprocess.run([str(tool), *map(str, argv)], cwd=cwd, capture_output=True)
        if check:
            assert q.returncode == 0, (argv, q.returncode, q.stderr)
        return q

    def g(cwd, *argv):
        return run(git, argv, cwd).stdout

    def state(cwd):
        return dict(head=g(cwd, 'rev-parse', 'HEAD').hex(), index=g(cwd, 'ls-files', '-s').hex(),
                    files={str(x.relative_to(cwd)): hashlib.sha256(x.read_bytes()).hexdigest()
                           for x in sorted(cwd.rglob('*')) if '.git' not in x.relative_to(cwd).parts and x.is_file()})

    cases = [('binary', 'binary', ''), ('binary-crlf', 'binary', ''), ('negative-diff', '-diff', ''),
             ('negative-merge', '-merge', ''), ('merge-unconfigured', 'merge=lockb', ''),
             ('driver-unconfigured', 'diff=lockb', ''), ('binary-driver-override', 'binary diff=lockb', ''),
             ('binary-driver-override-crlf', 'binary diff=lockb', ''),
             ('cpp', 'diff=cpp', 'cpp'), ('rust', 'diff=rust', 'rust'), ('dts', 'diff=dts', 'dts'),
             ('perl', 'diff=perl', 'perl'), ('python', 'diff=python', 'python'),
             ('diff-set', 'diff', ''), ('diff-lfs-unconfigured', 'diff=lfs', ''),
             ('merge-ours', 'merge=ours', ''), ('merge-lfs-unconfigured', 'merge=lfs', ''),
             ('merge-libcxx-unconfigured', 'merge=libcxx-reformat', ''),
             ('marker-size', 'conflict-marker-size=32', ''),
             ('negative-eol', '-eol', ''), ('negative-filter', '-filter', ''),
             ('filter-lfs-unconfigured', 'filter=lfs', ''),
             ('filter-gettext-unconfigured', 'filter=gettext-no-location', ''),
             ('filter-gettext-number-unconfigured', 'filter=gettext-no-line-number', ''),
             ('linguist', 'linguist-generated linguist-vendored linguist-documentation linguist-language=JSON-with-Comments', ''),
             ('whitespace', '-whitespace', ''),
             ('whitespace-value', 'whitespace=blank-at-eol,-blank-at-eof,-space-before-tab,tab-in-indent,tabwidth=2', '')]
    rows = []
    for kind, attributes, driver in cases:
        case = out / kind
        case.mkdir()
        seed = case / 'seed'
        run(git, ['init', '-q', '-b', 'main', seed], root)
        (seed / '.gitattributes').write_text('sample.dat ' + attributes + '\n')
        def payload(lines):
            data = ''.join(lines).encode()
            return data.replace(b'\n', b'\r\n') if kind.endswith('-crlf') else data
        if driver == 'python':
            prefix, suffix = ['class X:\n', '    def important(self):\n'], ['        return 0\n']
        elif driver == 'perl':
            prefix, suffix = ['package X;\n', 'sub important {\n', 'my $noise = 0;\n'], ['}\n']
        elif driver == 'rust':
            prefix, suffix = ['struct X;\n', 'impl X {\n', '    fn important(&self) {\n'], ['    }\n', '}\n']
        elif driver == 'dts':
            prefix, suffix = ['/dts-v1/;\n', '/ {\n', '\timportant {\n'], ['\t};\n', '};\n']
        else:
            prefix, suffix = ['class X {\n', 'public:\n', '    void important() {\n'], ['    }\n', '};\n']
        lines = prefix + [f'        value_{i} = {i};\n' for i in range(24)] + suffix
        (seed / 'sample.dat').write_bytes(payload(lines))
        g(seed, 'add', '.')
        g(seed, 'commit', '-qm', 'base')
        lines[14] = '        value_11 = 100;\n'
        (seed / 'sample.dat').write_bytes(payload(lines))
        g(seed, 'commit', '-qam', 'next')
        target = g(seed, 'rev-parse', 'HEAD').decode().strip()
        lines[17] = '        value_14 = 200;\n'
        changed = payload(lines)
        remote = case / 'remote.git'
        run(git, ['clone', '-q', '--bare', seed, remote], root)
        g(seed, 'remote', 'add', 'origin', remote.as_uri())
        commands = {
            'status': ['status', '--porcelain'], 'add': ['add', 'sample.dat'],
            'commit-quiet': ['commit', '-qam', 'edit'], 'commit-summary': ['commit', '-am', 'edit'],
            'checkout-path': ['checkout', '--', 'sample.dat'], 'restore': ['restore', 'sample.dat'],
            'checkout-branch': ['checkout', '-q', '--detach', 'HEAD~'],
            'reset': ['reset', '--hard', '-q', 'HEAD~'], 'revert-trivial': ['revert', '--no-edit', target],
            'fetch': ['fetch', '-q', 'origin'], 'push': ['push', '-q', 'origin', 'HEAD:refs/heads/census'],
            'log': ['log', '-1'], 'diff': ['diff', '--', 'sample.dat'],
            'diff-binary': ['diff', '--binary', '--', 'sample.dat'],
            'diff-stat': ['diff', '--stat', '--', 'sample.dat'],
            'log-p': ['log', '-p', '-1'], 'log-stat': ['log', '--stat', '-1'],
            'clone': ['clone', '-q', remote.as_uri(), 'work'],
        }
        for command, argv in commands.items():
            results = {}
            oracle_changes_header = False
            for label, tool in (('git', git), ('den', den)):
                work = case / 'work'
                if work.exists():
                    shutil.rmtree(work)
                if command != 'clone':
                    shutil.copytree(seed, work)
                    if command in ('status', 'add', 'commit-quiet', 'commit-summary', 'checkout-path', 'restore', 'diff', 'diff-binary', 'diff-stat'):
                        (work / 'sample.dat').write_bytes(changed)
                if command == 'push':
                    g(remote, 'update-ref', '-d', 'refs/heads/census')
                q = run(tool, argv, case if command == 'clone' else work, check=False)
                s = state(work) if work.exists() and (work / '.git/HEAD').exists() else None
                results[label] = dict(status=q.returncode, stdout=q.stdout.hex(), stderr=q.stderr.hex(), state=s)
                if label == 'git' and driver and command in ('diff', 'diff-binary', 'log-p'):
                    (work / '.gitattributes').write_text('sample.dat !diff\n')
                    default = run(git, argv, work)
                    oracle_changes_header = (q.stdout != default.stdout)
                    results[label]['without_driver_stdout'] = default.stdout.hex()
            if driver and command in ('diff', 'diff-binary', 'log-p'):
                d = results['den'];err = bytes.fromhex(d['stderr'])
                ok = d['status'] == 2 and b'diff' in err and driver.encode() in err and b'sample.dat' in err
            else:
                left = {k:v for k,v in results['git'].items() if k != 'without_driver_stdout'}
                ok = left == results['den']
            name = f'attribute-effects-{kind}-{command}'
            print(('PASS ' if ok else 'FAIL ') + name, flush=True)
            row = dict(name=name, passed=ok, attributes=attributes, builtin_changes_header=oracle_changes_header, **results)
            if not ok:
                print(json.dumps(row), flush=True)
            rows.append(row)
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failed = sum(not x['passed'] for x in rows)
    print(f'attribute-effects: {len(rows)} rows, {failed} failures; zero skips', flush=True)
    return int(failed != 0)


if __name__ == '__main__':
    raise SystemExit(main())
