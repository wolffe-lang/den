#!/usr/bin/env python3
"""The toolchain pins, read against each other (run by tools/check-newest-wolf).

wolf-toolchain.toml pins the wolf den is built with ([wolf], with [lupin] and [std]) and the newest wolf release
den must also build with ([wolf-newest]). candidate-wolf.toml, when present, pins a next wolf that has not been
released yet, whose leaf builds den with it in the record until it is released. Rows:

  toolchain-newest-not-older      [wolf-newest]'s version is at or above [wolf]'s: the newest release is never
                                  older than the pin
  toolchain-pin-line-names-rev    [wolf]'s version line names its version and its rev's first seven characters,
                                  as the released binary prints them
  toolchain-candidate-ahead       candidate-wolf.toml is absent, or its version is above [wolf]'s: a candidate the
                                  pin has caught up with is retired, not kept building den with an older compiler
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent


def sections(path):
    out, cur = {}, None
    for line in path.read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r'\[([^\]]+)\]', line)
        if m:
            cur = out.setdefault(m.group(1), {})
            continue
        k, _, v = line.partition('=')
        if cur is not None and _:
            cur[k.strip()] = v.strip().strip('"')
    return out


def version(text):
    """(major, minor, patch, dev) from '0.2.41' or a version line's 'wolf 0.2.40+dev.1add9bb'; dev sorts after."""
    m = re.search(r'(\d+)\.(\d+)\.(\d+)(\+dev\S*)?', text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 1 if m.group(4) else 0)


def main():
    pins = sections(ROOT / 'wolf-toolchain.toml')
    wolf, newest = pins.get('wolf', {}), pins.get('wolf-newest', {})
    pin = version(wolf.get('version', ''))
    rows = []

    def row(name, ok, detail):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail, flush=True)

    top = version(newest.get('version', ''))
    row('toolchain-newest-not-older', pin is not None and top is not None and top >= pin,
        f"[wolf] {wolf.get('version')} and [wolf-newest] {newest.get('version')}")
    line = wolf.get('version_line', '')
    row('toolchain-pin-line-names-rev',
        f"wolf {wolf.get('version')} " in line + ' ' and f"pin {wolf.get('rev', '')[:7]})" in line,
        f'{line!r} against version {wolf.get("version")} and rev {wolf.get("rev", "")[:7]}')
    cand_path = ROOT / 'candidate-wolf.toml'
    if cand_path.exists():
        cand = sections(cand_path).get('wolf-candidate', {})
        got = version(cand.get('version_line', ''))
        row('toolchain-candidate-ahead', pin is not None and got is not None and got > pin,
            f"candidate {cand.get('version_line')!r} against the pin {wolf.get('version')}")
    else:
        row('toolchain-candidate-ahead', True, 'no candidate-wolf.toml (no unreleased wolf is being built)')
    failures = rows.count(False)
    print(f'toolchain-pins: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
