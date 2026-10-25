"""Original staged-rename experiments; pinned Git binary only, no source reads.

Run under tools/env inside the assigned container. One old/new path at a time
avoids candidate-pairing ambiguity. All files stay under target/rename-measure*.
Hypotheses are deliberately compared, not declared as Git's implementation.
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import random
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT = os.environ["DEN_GIT"]


def spans(data, maximum=64, crlf=False):
    """Candidate: bounded newline-terminated byte spans, counted as a multiset."""
    if crlf:
        data = data.replace(b"\r\n", b"\n")
    result = collections.Counter()
    start = 0
    for pos, byte in enumerate(data):
        if byte == 10 or pos + 1 - start == maximum:
            result[data[start:pos + 1]] += 1
            start = pos + 1
    if start < len(data):
        result[data[start:]] += 1
    return result


def prediction(old, new, maximum=64, crlf=False, byte_offset=False):
    a, b = spans(old, maximum, crlf), spans(new, maximum, crlf)
    if byte_offset:
        def shifted(counter):
            out = collections.Counter()
            for chunk, count in counter.items():
                key = bytes((x - chunk[0]) % 256 for x in chunk) if len(chunk) == maximum else chunk
                out[key] += count
            return out
        a, b = shifted(a), shifted(b)
    common = sum(len(span) * min(count, b[span]) for span, count in a.items())
    return 100 * common // max(len(old), len(new), 1)


def fixture_cases(suite):
    rng = random.Random(0x76633033)
    cases = []

    def add(name, old, new, family):
        assert old and new
        cases.append((name, old, new, family))

    def text(n):
        return bytes(rng.choice(b"abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))

    def binary(n):
        # Deliberately exclude LF/CR to separate span boundaries from content.
        return bytes(rng.choice([b for b in range(256) if b not in (10, 13)]) for _ in range(n))

    if suite in ("initial", "all"):
        for name, old, new in [
            ("two-of-three", b"a\nb\nc\n", b"a\nb\nX\n"),
            ("reorder", b"a\nb\nc\n", b"c\na\nb\n"),
            ("half", b"a" * 63 + b"\n" + b"b" * 63 + b"\n", b"a" * 63 + b"\n" + b"c" * 63 + b"\n"),
            ("long-half", b"a" * 64 + b"b" * 64, b"a" * 64 + b"c" * 64),
            ("long-shift", b"a" * 64 + b"b" * 64, b"x" + b"a" * 64 + b"b" * 63),
            ("crlf", b"a\r\nb\r\nc\r\n", b"a\nb\nc\n"),
            ("one-line", b"abcdef\n", b"abcdeg\n"),
            ("binary-half", b"\0" + b"a" * 63 + b"b" * 64, b"\0" + b"a" * 63 + b"c" * 64),
            ("duplicate", b"a\na\nb\n", b"a\nb\nb\n"),
            ("grow", b"a\nb\n", b"a\nb\nc\nd\n"),
        ]:
            add(name, old, new, "known")
        for n in [1, 2, 7, 8, 15, 16, 31, 32, 33, 47, 48, 62, 63, 64, 65, 66, 95, 96,
                  127, 128, 129, 191, 192, 193, 255, 256, 257]:
            add(f"uniform-{n}", b"a" * n, b"b" * n, "uniform-length")
        for n in [31, 32, 33, 62, 63, 64, 65, 66, 95, 127, 128, 129, 191]:
            old = text(n)
            for pos in sorted({0, n // 2, n - 1}):
                new = bytearray(old)
                new[pos] = ord("!")
                add(f"text-edit-{n}-{pos}", old, bytes(new), "boundary-edit")
        anchor = text(63) + b"\n"
        for period in [1, 2, 3, 4, 5, 7, 8, 16, 31, 32, 33, 63, 64]:
            for n in [64, 128]:
                a, b = text(period), text(period)
                old = (a * ((n + period - 1) // period))[:n]
                new = (b * ((n + period - 1) // period))[:n]
                add(f"periodic-{period}-{n}", anchor + old, anchor + new, "periodic-collision")
        for matched in [48, 49, 50, 51, 52]:
            shared = text(matched - 1) + b"\n"
            old = shared + text(99 - matched) + b"\n"
            new = shared + text(99 - matched) + b"\n"
            add(f"threshold-{matched}", old, new, "threshold")
        for length in [1, 3, 31, 62, 63, 64, 65, 126]:
            lines = [text(length), text(length + 1), text(max(1, length - 1))]
            old, new = b"\r\n".join(lines) + b"\r\n", b"\n".join(lines) + b"\n"
            add(f"crlf-{length}", old, new, "crlf")
            add(f"binary-crlf-{length}", b"\0\n" + old, b"\0\n" + new, "binary-crlf")
    if suite in ("random", "all"):
        for binary_mode in (False, True):
            for run in range(30):
                make = binary if binary_mode else text
                chunks = [make(64) for _ in range(4)]
                if binary_mode:
                    chunks[0] = b"\0" + chunks[0][1:]
                old = b"".join(chunks)
                for change in ["reorder", "one", "three", "duplicate"]:
                    if change == "reorder":
                        parts = [chunks[2], chunks[0], chunks[3], chunks[1]]
                    elif change == "one":
                        parts = [chunks[0], make(64), chunks[2], chunks[3]]
                    elif change == "three":
                        parts = [chunks[0], make(64), make(64), make(64)]
                    else:
                        parts = [chunks[0], chunks[0], chunks[2], chunks[3]]
                    add(f"random-{'binary' if binary_mode else 'text'}-{run}-{change}", old, b"".join(parts), "random-spans")
        for run in range(30):
            lines = [text(rng.choice([1, 7, 31, 32, 63, 64, 65, 97])) + b"\n" for _ in range(5)]
            old = b"".join(lines)
            shuffled = list(lines)
            rng.shuffle(shuffled)
            add(f"random-lines-{run}-reorder", old, b"".join(shuffled), "random-lines")
            changed = list(lines)
            changed[2] = b"!" + changed[2][1:]
            add(f"random-lines-{run}-edit", old, b"".join(changed), "random-lines")
    if suite in ("hash", "all"):
        anchor = text(63) + b"\n"
        zero = bytes(64)
        for gap in range(1, 64):
            for bit in range(8):
                mutated = bytearray(zero)
                mutated[0] = 1
                mutated[gap] = 1 << bit
                add(f"zero-pair-{gap}-bit{bit}", anchor + zero, anchor + bytes(mutated), "pair-cancellation")
        base = binary(64)
        for gap in [1, 2, 4, 8, 16, 31, 32, 33, 63]:
            for change in ("xor", "add"):
                new = bytearray(base)
                if change == "xor":
                    new[0] ^= 1
                    new[gap] ^= 1
                else:
                    new[0] = (new[0] + 1) % 256
                    new[gap] = (new[gap] - 1) % 256
                add(f"random-pair-{gap}-{change}", anchor + base, anchor + bytes(new), "random-pair")
    if suite in ("structural", "all"):
        anchor = text(63) + b"\n"
        for length in [31, 32, 33, 63, 64, 65, 127, 128]:
            body = bytes(rng.randrange(64, 96) for _ in range(length))
            for delta in [1, 2, 7, 32]:
                shifted = bytes(x + delta for x in body)
                add(f"offset-{length}-{delta}", anchor + body, anchor + shifted, "uniform-offset")
        body = bytes(rng.randrange(32, 96) for _ in range(64))
        for amount in [1, 2, 7, 8, 16, 31, 32, 33, 63]:
            add(f"rotate-{amount}", anchor + body, anchor + body[amount:] + body[:amount], "within-span-permutation")
        add("reverse-64", anchor + body, anchor + body[::-1], "within-span-permutation")
        shuffled = bytearray(body)
        rng.shuffle(shuffled)
        add("shuffle-64", anchor + body, anchor + bytes(shuffled), "within-span-permutation")
        for name, old, new in [
            ("anagram-line", b"abc\n", b"bac\n"),
            ("split-homogeneous", b"a" * 32 + b"b" * 32, b"ab" * 32),
            ("reverse-period2", b"ab" * 32, b"ba" * 32),
            ("offset-period2", b"ab" * 32, b"bc" * 32),
            ("swap-period4", b"abcd" * 16, b"badc" * 16),
        ]:
            add(name, anchor + old, anchor + new, "structural")
        for byte in [0, 1, 2, 3, 10, 13, 32, 65, 98, 127, 128, 254, 255]:
            add(f"uniform-byte-{byte}", anchor + b"a" * 64, anchor + bytes([byte]) * 64, "uniform-byte")
        # Test whether repeated-byte equivalence survives one distinguisher.
        for pos in [0, 1, 15, 31, 32, 47, 62, 63]:
            for variant in ["fixed", "offset"]:
                old, new = bytearray(b"a" * 64), bytearray(b"b" * 64)
                old[pos] = ord("X")
                new[pos] = ord("X") if variant == "fixed" else ord("Y")
                add(f"uniform-marker-{pos}-{variant}", anchor + bytes(old), anchor + bytes(new), "uniform-marker")
        for position in [0, 1, 63, 64, 127, 1023, 4095, 7999, 8000, 8191, 8192, 8193, 10000]:
            prefix = b"p" * position + b"\0\n"
            add(f"nul-classification-{position}", prefix + b"a\r\n" * 4000, prefix + b"a\n" * 4000, "nul-classification")
    if suite in ("equivalence", "all"):
        # Direct, unanchored comparisons distinguish classification failures,
        # not just a wrong score on a pair that still clears the 50% threshold.
        for byte in range(256):
            add(f"direct-uniform-{byte}", b"a" * 64, bytes([byte]) * 64, "direct-uniform")
        for run in range(40):
            body = bytes(rng.randrange(32, 96) for _ in range(64))
            delta = rng.choice([1, 2, 7, 32, 64, 96, 128, 159])
            shifted = bytes((x + delta) % 256 for x in body)
            add(f"direct-offset-{run}-{delta}", body, shifted, "direct-offset")
        for n in [48, 49, 50, 51, 52]:
            shared = text(n - 1) + b"\n"
            old = shared + text(99 - n) + b"\n"
            new = shared + text(99 - n) + b"\n"
            add(f"threshold-reordered-{n}", old, new[len(shared):] + shared, "threshold")
    if suite in ("wrap", "all"):
        for delta in [1, 2, 7, 32, 64, 128]:
            alphabet = [x for x in range(256) if x not in (10, 13) and (x + delta) % 256 not in (10, 13)]
            for run in range(20):
                body = bytearray(rng.choice(alphabet) for _ in range(64))
                body[0], body[1] = 255, 1
                shifted = bytes((x + delta) % 256 for x in body)
                add(f"mixed-wrap-{delta}-{run}", bytes(body), shifted, "mixed-wrap")
        for base in [0, 1, 125, 126, 127, 128, 252, 253, 254]:
            for pos in [0, 1, 7, 31, 32, 63]:
                old = bytearray([base] * 64)
                old[pos] = base - 1 if base > 0 else 1
                new = bytes(x + 1 for x in old)
                add(f"near-uniform-{base}-{pos}", bytes(old), new, "near-uniform")
    return cases


def run(suite):
    base = ROOT / f"target/rename-measure-{suite}"
    # Never remove an existing result/fixture tree. A repeated run needs a new
    # explicit output name, or the parent can archive its own previous results.
    base.mkdir()
    repo = base / "repo"
    repo.mkdir()
    report = {"suite": suite, "oracle": GIT, "oracle_sha256": hashlib.sha256(pathlib.Path(GIT).read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
              "cases": [], "hypotheses": "Exact bounded-span multiset; not a claim about implementation signatures."}
    output = ROOT / f"target/rename-measure-{suite}.json"
    started = time.monotonic()

    def git(*args):
        p = subprocess.run([GIT, *args], cwd=repo, capture_output=True, timeout=30)
        if p.returncode:
            raise RuntimeError((args, p.returncode, p.stdout, p.stderr))
        return p.stdout

    report["version"] = git("--version").decode().strip()
    git("init", "-q")
    source, destination = repo / "source", repo / "moved"
    try:
        for at, (name, old, new, family) in enumerate(fixture_cases(suite)):
            if time.monotonic() - started > 900:
                raise TimeoutError("15-minute bound: partial evidence saved")
            if destination.exists():
                destination.unlink()
            source.write_bytes(old)
            git("add", "-A")
            git("commit", "--allow-empty", "-qm", f"base-{at}")
            source.unlink()
            destination.write_bytes(new)
            git("add", "-A")
            raw = git("diff", "--cached", "--raw", "-z", "--find-renames=1%")
            status = git("status", "--porcelain=v1", "-z")
            records = raw.split(b"\0")
            scores = [int(part.rsplit(b" ", 1)[1][1:]) for part in records
                      if part.startswith(b":") and part.rsplit(b" ", 1)[1].startswith(b"R")]
            assert len(scores) <= 1
            observed = scores[0] if scores else None
            row = {"name": name, "family": family, "old_hex": old.hex(), "new_hex": new.hex(),
                   "old_size": len(old), "new_size": len(new), "score_at_1pct": observed,
                   "default_rename": status.startswith(b"R"), "raw_hex": raw.hex(), "status_hex": status.hex(),
                   "predictions": {f"span{bound}-{'crlf' if normalize else 'raw'}": prediction(old, new, bound, normalize)
                                   for bound in (32, 64, 128) for normalize in (False, True)}}
            row["predictions"]["span64-offset-normalized"] = prediction(old, new, 64, False, True)
            old_spans = spans(old, 64, b"\0" not in old[:8000])
            new_spans = spans(new, 64, b"\0" not in new[:8000])
            common = sum(len(chunk) * min(n, new_spans[chunk]) for chunk, n in old_spans.items())
            row["predictions"]["span64-sample8000-crlf"] = 100 * common // max(len(old), len(new))
            report["cases"].append(row)
            if at % 25 == 0 or family in ("known", "uniform-length", "threshold"):
                print(name, "score", observed, "rename", row["default_rename"], "candidate64", row["predictions"]["span64-raw"], flush=True)
    finally:
        report["elapsed_s"] = time.monotonic() - started
        output.write_text(json.dumps(report, indent=2) + "\n")
    rows = report["cases"]
    for key in rows[0]["predictions"]:
        mismatches = [r["name"] for r in rows if (r["score_at_1pct"] or 0) != r["predictions"][key]]
        print(key, "mismatches", len(mismatches), "/", len(rows), mismatches[:15], flush=True)
    print("RESULT", output, "cases", len(rows), "seconds", report["elapsed_s"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("initial", "random", "hash", "structural", "equivalence", "wrap", "all"), default="initial")
    run(parser.parse_args().suite)
