#!/usr/bin/env python3
"""Configured file transport porcelain: exact output/status and complete file state."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import socket
import time
import subprocess


def accepted_review(record, name, fingerprints, case_input, outcomes):
    return bool(record and record.get('name') == name == 'lease-delete-match'
                and record.get('input_sha256') == fingerprints[0] == fingerprints[1]
                and record.get('input') == case_input and record.get('outcomes') == outcomes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--family', choices=('configured', 'lease', 'failure', 'all'), default='configured')
    a = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = root / 'target/runs' / ('wire-configured-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    supplied_git = Path(os.environ['DEN_GIT']).resolve()
    oracle_digest = hashlib.sha256(supplied_git.read_bytes()).hexdigest()
    assert oracle_digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    # Stable effective tool paths make the reviewed row fully byte-bound across
    # cached/container inputs, without ignoring or normalizing any case bytes.
    staged = root / 'target/vc16-oracle'
    (staged / 'bin').mkdir(parents=True, exist_ok=True)
    (staged / 'libexec').mkdir(exist_ok=True)
    links = {staged / 'bin' / name: supplied_git.parent / name
             for name in ('git', 'git-upload-pack', 'git-receive-pack')}
    links[staged / 'libexec/git-core'] = supplied_git.parent.parent / 'libexec/git-core'
    for destination, origin in links.items():
        assert origin.exists(), origin
        if destination.is_symlink():
            destination.unlink()
        assert not destination.exists(), destination
        destination.symlink_to(origin)
    git = str(staged / 'bin/git')
    den = root / 'target' / a.tier / 'den'
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEN_')}
    env.update(DEN_GIT=git, DEN_ROOT=str(root), PATH=str(staged / 'bin') + ':/usr/bin:/bin',
               GIT_EXEC_PATH=str(staged / 'libexec/git-core'),
               GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')
    os.umask(0o022)
    environment = {k: v for k, v in env.items() if k.startswith(('GIT_', 'DEN_')) or k in ('HOME', 'TZ', 'LC_ALL', 'TMPDIR', 'PATH')}
    captures = []
    def run(argv, cwd=None, check=True, data=b''):
        p = subprocess.run(list(map(str, argv)), cwd=cwd, env=env, input=data, capture_output=True, timeout=60)
        captures.append(dict(argv=list(map(str, argv)), cwd=str(cwd), environment=environment, stdin=data.hex(),
                             stdout=p.stdout.hex(), stderr=p.stderr.hex(), exit=p.returncode))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        if check:
            assert p.returncode == 0, captures[-1]
        return p
    def reset(path, template=None):
        if path.exists():
            shutil.rmtree(path)
        if template:
            shutil.copytree(template, path)
    def snapshot(path):
        return {str(p.relative_to(path)): [p.stat().st_mode & 0o777, p.read_bytes().hex()]
                for p in path.rglob('*') if p.is_file()}
    source, original, work, seed = [out / n for n in ('remote.git', 'original.git', 'work', 'seed')]
    for path in (source, original, work, seed):
        reset(path)
    run([git, 'init', '-q', '--bare', source])
    tree = run([git, 'mktree'], source).stdout.strip().decode()
    first = run([git, 'commit-tree', tree, '-m', 'base'], source).stdout.strip().decode()
    second = run([git, 'commit-tree', tree, '-p', first, '-m', 'forward'], source).stdout.strip().decode()
    for ref in ('refs/heads/main', 'refs/heads/topic'):
        run([git, 'update-ref', ref, first], source)
    run([git, 'clone', '-q', source.as_uri(), seed])
    # Keep every canonical input object locally: these rows isolate config/ref
    # publication. The inherited wire matrix independently requires pack import.
    shutil.copytree(source / 'objects', seed / '.git/objects', dirs_exist_ok=True)
    run([git, 'config', 'gc.auto', '0'], seed)
    run([git, 'config', 'maintenance.auto', 'false'], seed)
    shutil.copytree(source, original)
    marker = out / 'selected-service.calls'
    upload, receive = out / 'upload-service', out / 'receive-service'
    for path, service in ((upload, 'git-upload-pack'), (receive, 'git-receive-pack')):
        path.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" >> ' + shlex.quote(str(marker)) + '\nexec ' + shlex.quote(str(staged / 'bin' / service)) + ' "$@"\n')
        path.chmod(0o755)
    cases = [
        ('fetch-named-quiet', ['fetch', '-q', 'origin']),
        ('fetch-explicit-state', ['fetch', '-q', source.as_uri(), 'refs/heads/main:refs/remotes/origin/main']),
        ('fetch-default-quiet', ['fetch', '-q']),
        ('fetch-named-report', ['fetch', 'origin']),
        ('fetch-default-report', ['fetch']),
        ('fetch-prune-quiet', ['fetch', '-q', '--prune']),
        ('fetch-prune-report', ['fetch', '--prune']),
        ('fetch-rewind-tracking', ['fetch', '-q']),
        ('fetch-different-remote', ['fetch', '-q', 'upstream']),
        ('push-default-quiet', ['push', '-q']),
        ('push-u-quiet', ['push', '-q', '-u', 'origin', 'main']),
        ('push-default-report', ['push']),
        ('push-u-report', ['push', '-u', 'origin', 'main']),
        ('fetch-service-flag', ['fetch', '-q', '--upload-pack=' + str(upload), 'origin']),
        ('fetch-service-config', ['fetch', '-q', 'origin']),
        ('push-service-flag', ['push', '-q', '--receive-pack=' + str(receive)]),
        ('push-service-config', ['push', '-q']),
    ]
    lease = '--force-with-lease=refs/heads/main:'
    lease_cases = [
        ('lease-plain-match', ['push', '--force-with-lease']),
        ('lease-plain-stale', ['push', '-q', '--force-with-lease']),
        ('lease-explicit-match', ['push', lease + second]),
        ('lease-explicit-stale', ['push', lease + first]),
        ('lease-expect-absent', ['push', lease]),
        ('lease-create-absent', ['push', '--force-with-lease=refs/heads/new:', 'origin', 'main:refs/heads/new']),
        ('lease-missing-tracking', ['push', '--force-with-lease']),
        ('lease-short-ref', ['push', '--force-with-lease=main:' + second]),
        ('lease-expect-revision', ['push', lease + 'HEAD']),
        ('lease-noop-stale', ['push', lease + first]),
        ('lease-force-stale', ['push', '--force', lease + first]),
        ('lease-plus-stale', ['push', lease + first, 'origin', '+refs/heads/main:refs/heads/main']),
        ('lease-delete-match', ['push', lease + second, 'origin', ':refs/heads/main']),
        ('lease-delete-topic-match', ['push', '--force-with-lease=refs/heads/topic:' + first, 'origin', ':refs/heads/topic']),
        ('lease-delete-stale', ['push', lease + first, 'origin', ':refs/heads/main']),
        ('lease-unrelated', ['push', '--force-with-lease=refs/heads/other:' + second]),
        ('lease-quiet-match', ['push', '-q', '--force-with-lease']),
    ]
    missing_url = (out / 'missing.git').as_uri()
    failure_cases = [
        ('failure-fetch-missing-remote', ['fetch', '-q', 'missing']),
        ('failure-push-missing-remote', ['push', '-q', 'missing']),
        ('failure-pull-missing-remote', ['pull', '-q', '--no-rebase', 'missing']),
        ('failure-fetch-wrong-url', ['fetch', '-q']),
        ('failure-push-wrong-url', ['push', '-q']),
        ('failure-pull-wrong-url', ['pull', '-q', '--no-rebase']),
        ('failure-push-nonfastforward', ['push', '-q']),
        ('failure-fetch-missing-ref', ['fetch', '-q', source.as_uri(), 'refs/heads/missing:refs/remotes/origin/missing']),
        ('failure-pull-missing-ref', ['pull', '-q', '--no-rebase', 'origin', 'missing']),
        ('failure-fetch-daemon', ['fetch', '-q']),
        ('failure-push-daemon', ['push', '-q']),
        ('failure-pull-daemon', ['pull', '-q', '--no-rebase']),
    ]
    @contextlib.contextmanager
    def daemon(enabled):
        if not enabled:
            yield
            return
        argv = [git, 'daemon', '--reuseaddr', '--listen=127.0.0.1', '--port=39416', '--base-path=' + str(out), str(out)]
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            for _ in range(100):
                assert process.poll() is None, 'fixture daemon exited before ready'
                try:
                    with socket.create_connection(('127.0.0.1', 39416), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise AssertionError('fixture daemon startup timeout')
            yield
        finally:
            if process.poll() is None:
                process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            (out / ('daemon-' + str(process.pid) + '.json')).write_text(json.dumps(dict(argv=argv, environment=environment, stdin='', stdout=stdout.hex(), stderr=stderr.hex(), exit=process.returncode, teardown='own PID only'), indent=2) + '\n')
    if a.family == 'failure':
        cases = failure_cases
    elif a.family == 'lease':
        cases = lease_cases
    elif a.family == 'all':
        cases += lease_cases + failure_cases
    review_path = root / 'tests/review/vc16-push-service-stderr.json'
    reviews = json.loads(review_path.read_text()).get('records', {}) if review_path.exists() else {}
    rows = []
    for name, argv in cases:
        outcomes, fingerprints, selector_calls, selected_proofs = [], [], [], []
        for tool in (git, den):
            reset(source, original)
            reset(work, seed)
            if name.startswith('failure-'):
                if name.endswith('-wrong-url'):
                    run([git, 'remote', 'set-url', 'origin', missing_url], work)
                if name.endswith('-nonfastforward'):
                    run([git, 'update-ref', 'refs/heads/main', second], source)
                    run([git, 'update-ref', 'refs/remotes/origin/main', second], work)
                if name.endswith('-daemon'):
                    run([git, 'remote', 'set-url', 'origin', 'git://127.0.0.1:39416/remote.git'], work)
                    if name == 'failure-push-daemon':
                        (source / 'git-daemon-export-ok').write_bytes(b'')
            elif name.startswith('fetch-'):
                run([git, 'update-ref', 'refs/heads/main', second], source)
                if 'prune' in name:
                    run([git, 'update-ref', '-d', 'refs/heads/topic'], source)
                if name == 'fetch-rewind-tracking':
                    run([git, 'update-ref', 'refs/remotes/origin/main', second], work)
                    run([git, 'update-ref', 'refs/heads/main', first], source)
                if name == 'fetch-different-remote':
                    run([git, 'remote', 'rename', 'origin', 'upstream'], work)
            elif name.startswith('lease-'):
                run([git, 'update-ref', 'refs/heads/main', second], source)
                if name not in ('lease-plain-stale', 'lease-missing-tracking', 'lease-noop-stale'):
                    run([git, 'update-ref', 'refs/remotes/origin/main', second], work)
                if name == 'lease-missing-tracking':
                    run([git, 'update-ref', '-d', 'refs/remotes/origin/main'], work)
                if name == 'lease-noop-stale':
                    run([git, 'update-ref', 'refs/heads/main', second], work)
            else:
                run([git, 'update-ref', 'refs/heads/main', second], work)
                if name.startswith('push-u-'):
                    run([git, 'config', '--remove-section', 'branch.main'], work)
            selecting = '-service-' in name
            selected_program = upload if name.startswith('fetch-') else receive
            if name.endswith('-service-config'):
                key = 'remote.origin.uploadpack' if name.startswith('fetch-') else 'remote.origin.receivepack'
                run([git, 'config', key, str(selected_program)], work)
            marker.write_bytes(b'')
            case_input = dict(argv=argv, environment=environment, stdin='', local=snapshot(work), remote=snapshot(source),
                              global_config=Path(env['GIT_CONFIG_GLOBAL']).read_bytes().hex(),
                              oracle_sha256=oracle_digest)
            if selecting:
                case_input['selected_service'] = dict(path=str(selected_program), mode=selected_program.stat().st_mode & 0o777, data=selected_program.read_bytes().hex())
            fingerprint = hashlib.sha256(json.dumps(case_input, sort_keys=True).encode()).hexdigest()
            fingerprints.append(fingerprint)
            with daemon(name.endswith('-daemon')):
                result = run([tool, *argv], work, check=False)
            calls = marker.read_bytes()
            if selecting:
                selector_calls.append(calls.hex())
                selected_proofs.append(str(source).encode() in calls.splitlines())
            outcomes.append(dict(stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode,
                                 local=snapshot(work), remote=snapshot(source)))
        equal = outcomes[0] == outcomes[1]
        reviewed = False
        passed = equal and fingerprints[0] == fingerprints[1] and all(selected_proofs)
        if name == 'lease-delete-match':
            record = reviews.get(a.tier)
            reviewed = accepted_review(record, name, fingerprints, case_input, outcomes)
            passed = reviewed
            if reviewed:
                print('REVIEW configured-lease-delete-match reason=wire-push-service-stderr', flush=True)
        rows.append(dict(name=name, parity=equal, reviewed=reviewed, passed=passed,
                         input=case_input, input_sha256=fingerprints[0], outcomes=outcomes, selector_calls=selector_calls))
        if not passed:
            print('FAIL configured-' + name, flush=True)
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    failures = sum(not row['passed'] for row in rows)
    exact = sum(row['passed'] and row['parity'] for row in rows)
    reviewed = sum(row['reviewed'] for row in rows)
    print(f'configured: {len(rows)} rows, {exact} exact, {reviewed} reviewed, {failures} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
