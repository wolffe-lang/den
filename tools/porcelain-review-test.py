#!/usr/bin/env python3
"""Every leaf in the approved review input/output/state binding is significant."""
import copy
import hashlib
import json
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent.parent
accept = runpy.run_path(str(root / 'tools/configured-wire-test.py'))['accepted_review']
reviews = json.loads((root / 'tests/review/vc16-push-service-stderr.json').read_text())
assert reviews['schema'] == 1 and set(reviews['records']) == {'native', 'release'}

def paths(value, prefix=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from paths(child, (*prefix, key))
    elif isinstance(value, list):
        for key, child in enumerate(value):
            yield from paths(child, (*prefix, key))
    else:
        yield prefix

count = 0
for tier, record in reviews['records'].items():
    name, fingerprint = record['name'], record['input_sha256']
    actual_hash = hashlib.sha256(json.dumps(record['input'], sort_keys=True).encode()).hexdigest()
    assert fingerprint == actual_hash
    assert accept(record, name, [fingerprint, fingerprint], record['input'], record['outcomes'])
    assert not accept(record, name + '-other', [fingerprint, fingerprint], record['input'], record['outcomes'])
    assert not accept(record, name, [fingerprint, 'wrong'], record['input'], record['outcomes'])
    for field in ('input', 'outcomes'):
        for path in paths(record[field]):
            changed = copy.deepcopy(record[field])
            parent = changed
            for key in path[:-1]:
                parent = parent[key]
            key = path[-1]
            old = parent[key]
            parent[key] = old ^ 1 if isinstance(old, int) else str(old) + '!'
            inputs = changed if field == 'input' else record['input']
            outcomes = changed if field == 'outcomes' else record['outcomes']
            assert not accept(record, name, [fingerprint, fingerprint], inputs, outcomes), (tier, field, path)
            count += 1
    extra = copy.deepcopy(record['outcomes'])
    extra[0]['unexpected'] = 'new output/state field'
    assert not accept(record, name, [fingerprint, fingerprint], record['input'], extra)
print(f'review binding: {count} individual input/output/status/state mutations refused; both exact records accepted')
