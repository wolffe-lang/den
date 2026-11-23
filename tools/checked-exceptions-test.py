#!/usr/bin/env python3
"""tools/pack-payload-test.py's checked-machine exceptions are narrow and expire.

An exception holds only for the compiler and machine it names, and only while
that machine prints what it records. One left behind when the pin moves, or one
whose row the compiler renders correctly, fails by name. The committed table
names only the pinned compiler.
"""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'tools/pack-payload-test.py'
failed = 0


def say(ok, name, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)
    failed += not ok


say(HARNESS.is_file(), 'checked-exceptions-harness-present')
if not HARNESS.is_file():
    sys.exit(1)
spec = importlib.util.spec_from_file_location('pack_payload_test', HARNESS)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

OLD = 'wolf 0.2.36 (wolfgang, pin 5adf3d9)'
NEW = 'wolf 0.2.41 (wolfgang, pin 0000000)'
ROW = 'received-scan-zlib'
WRONG = 'Unsupported(pack zlib <value>)'
table = [dict(compiler=OLD, machine='checked', row=ROW, prints=WRONG, reason='fixture')]
correct = dict(harness.EXPECTED)
rendered = dict(correct, **{ROW: WRONG})


def names(results, ok):
    return {name for good, name, _ in results if good == ok}


r = harness.judge(rendered, OLD, 'checked', table)
say(not names(r, False), 'checked-exception-holds-for-its-compiler')
r = harness.judge(correct, OLD, 'checked', table)
say(names(r, False) == {'checked-exception-needed-' + ROW}, 'checked-exception-fails-once-not-needed')
r = harness.judge_pin(table, NEW)
say(names(r, False) == {'checked-exception-pin'}, 'checked-exception-fails-when-the-pin-moves')
r = harness.judge_pin(table, OLD)
say(not names(r, False), 'checked-exception-pin-holds')
r = harness.judge(rendered, NEW, 'checked', table)
say(names(r, False) == {'pack-payload-checked-' + ROW}, 'checked-exception-not-for-another-compiler')
r = harness.judge(rendered, OLD, 'native', table)
say(names(r, False) == {'pack-payload-native-' + ROW}, 'checked-exception-not-for-another-machine')
r = harness.judge(dict(correct, extra='x'), OLD, 'native', [])
say(names(r, False) == {'pack-payload-native-rows'}, 'pack-payload-unknown-row-fails')
r = harness.judge({k: v for k, v in correct.items() if k != ROW}, OLD, 'native', [])
say(names(r, False) == {'pack-payload-native-' + ROW}, 'pack-payload-missing-row-fails')
committed = json.loads((ROOT / 'tools/checked-exceptions.json').read_text())['exceptions']
r = harness.judge_pin(committed, harness.pinned_version_line())
say(not names(r, False), 'checked-exceptions-committed-table-names-the-pin',
    '; '.join(d for _, _, d in r))
sys.exit(1 if failed else 0)
