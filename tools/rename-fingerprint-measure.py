"""Fit explicitly labelled rolling-fingerprint hypotheses to black-box evidence.

No implementation source input. The 64-byte offset equivalences and failures
at repeated 127/254 motivate testing bit-position rotations and carry policy.
This is research, not a production scorer or a declaration of compatibility.
"""
import argparse
import collections
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def fingerprint(data, width, shift, operation, carry):
    mask = (1 << width) - 1
    lowmask = (1 << (width // 2)) - 1
    state = 0
    for value in data:
        state = ((state << shift) | (state >> (width - shift))) & mask
        if operation == 'xor':
            state ^= value
        elif carry:
            state = (state + value) & mask
        else:
            state = (state & ~lowmask) | ((state + value) & lowmask)
    return state


def chunks(data):
    text = b'\0' not in data[:8000]
    if text:
        data = data.replace(b'\r\n', b'\n')
    start = 0
    result = []
    for i, value in enumerate(data):
        if value == 10 or i + 1 - start == 64:
            result.append(data[start:i + 1])
            start = i + 1
    if start < len(data):
        result.append(data[start:])
    return result


def score(old, new, key):
    if old == new:
        return 100
    def counts(data):
        result = collections.Counter()
        for span in chunks(data):
            result[key(span)] += len(span)
        return result
    a, b = counts(old), counts(new)
    common = sum(min(n, b[k]) for k, n in a.items())
    return 100 * common // max(len(old), len(new), 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    rows = []
    inputs = {}
    for suite in ('initial', 'random', 'hash', 'structural', 'equivalence', 'wrap'):
        path = ROOT / f'notes/vc03-evidence/rename-measure-{suite}.json'
        inputs[suite] = hashlib.sha256(path.read_bytes()).hexdigest()
        for r in json.loads(path.read_text())['cases']:
            rows.append((suite, r, bytes.fromhex(r['old_hex']), bytes.fromhex(r['new_hex'])))
    assert len(rows) == 1510
    # All <=128-byte witnesses: avoid weighting huge CRLF repetitions while
    # screening. Survivors are checked on the full six reports separately.
    screen = [r for r in rows if max(len(r[2]), len(r[3])) <= 128]
    spans = {c for _, _, a, b in screen for d in (a,b) for c in chunks(d)}
    best = []
    for width in (8,16,32,64):
        for shift in range(1,width):
            for operation, carry in (('xor',True),('add',True),('add',False)):
                table = {c:fingerprint(c,width,shift,operation,carry) for c in spans}
                failures = [r['name'] for _, r,a,b in screen if score(a,b,table.__getitem__) != (r['score_at_1pct'] or 0)]
                best.append({'width':width,'shift':shift,'operation':operation,'carry':carry,
                             'mismatches':len(failures),'examples':failures[:10]})
        print('screen width',width,'complete; best',min(x['mismatches'] for x in best),flush=True)
    best.sort(key=lambda x:x['mismatches'])
    finalists = []
    for h in best[:12]:
        allspans = {c for _, _, a, b in rows for d in (a,b) for c in chunks(d)}
        table = {c:fingerprint(c,h['width'],h['shift'],h['operation'],h['carry']) for c in allspans}
        failed = []
        counts = collections.Counter()
        for suite,r,a,b in rows:
            actual = score(a,b,table.__getitem__)
            ok = actual == (r['score_at_1pct'] or 0) and (actual >= 50) == r['default_rename']
            counts[(suite,ok)] += 1
            if not ok:
                failed.append({'suite':suite,'name':r['name'],'predicted':actual,
                               'oracle':r['score_at_1pct'],'rename':r['default_rename']})
        finalists.append({**h,'full_mismatches':len(failed),'failures':failed,
                           'counts':{suite:{str(ok):counts[(suite,ok)] for ok in (True,False)} for suite in inputs}})
        print('full',h,'mismatches',len(failed),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'inputs':inputs,'rows':len(rows),'screen_rows':len(screen),
                                      'candidates':best,'finalists':finalists},indent=2)+'\n')

if __name__ == '__main__':
    main()
