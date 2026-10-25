"""Independent filesystem/provenance check-ignore witnesses, Git docs + binary.

No implementation source, production mutation, or expectation normalisation.
Run only inside the assigned pinned container through tools/env. Every query
captures stdout/stderr/status and content/metadata no-write snapshots, including
raw index bytes. Fixture setup writes are outside the measured query windows.
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT = pathlib.Path(os.environ["DEN_GIT"])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        key = "." if path == root else path.relative_to(root).as_posix()
        record = {"mode": info.st_mode, "size": info.st_size, "ino": info.st_ino,
                  "dev": info.st_dev, "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}
        if stat.S_ISLNK(info.st_mode):
            record["link_hex"] = os.fsencode(os.readlink(path)).hex()
        elif stat.S_ISREG(info.st_mode):
            record["sha256"] = digest(path.read_bytes())
        result[key] = record
    return result


def changes(before, after):
    return [key for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)]


def run(args):
    client = ROOT / f"target/{args.tier}/ignore-client"
    command = ROOT / f"target/{args.tier}/worktree-client"
    absent = [str(path) for path in (GIT, client, command) if not path.is_file() or not os.access(path, os.X_OK)]
    if absent:
        print("UNAVAILABLE existing binary:", absent, flush=True)
        return 2
    base = ROOT / f"target/ignore-filesystem-{args.suite}"
    output = ROOT / f"target/ignore-filesystem-{args.suite}.json"
    if output.exists():
        raise FileExistsError(output)
    base.mkdir()
    report = {"suite": args.suite, "tier": args.tier, "rows": [], "snapshots": {},
              "completed": False, "source_sha256": digest(pathlib.Path(__file__).read_bytes()),
              "binaries": {str(path): digest(path.read_bytes()) for path in (GIT, client, command)}}
    started = time.monotonic()

    def execute(argv, cwd, env, data=None):
        p = subprocess.run([str(x) for x in argv], cwd=cwd, env=env, input=data, capture_output=True, timeout=30)
        return {"status": p.returncode, "stdout": p.stdout.hex(), "stderr": p.stderr.hex()}

    def setup_git(repo, env, *argv):
        answer = execute([GIT, *argv], repo, env)
        if answer["status"]:
            raise RuntimeError((argv, answer))
        return answer

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())

    def fresh(name, excludes=""):
        fixture = base / name
        fixture.mkdir()
        repo = fixture / "repo"
        repo.mkdir()
        home, xdg = fixture / "home", fixture / "xdg"
        home.mkdir()
        xdg.mkdir()
        config = fixture / "global-config"
        config.write_bytes(b"")
        env = dict(os.environ)
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(xdg), GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM="1")
        setup_git(repo, env, "init", "-q", "--template=" + os.environ["DEN_EMPTY_TEMPLATE"])
        if excludes is not None:
            setup_git(repo, env, "config", "core.excludesFile", excludes)
        for path in ["scratch.tmp", "keep.tmp", "root-only", "a/scratch.tmp", "a/root-only", "a/deep/leaf.tmp", "none"]:
            write(repo / path, b"fixture\n")
        return fixture, repo, env

    def remember(tree):
        identifier = digest(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode())
        report["snapshots"].setdefault(identifier, tree)
        return identifier

    def measured(fixture, repo, env, family, name, git_args, den_args, data=None, cwd=None, metadata=None):
        if time.monotonic() - started > 900:
            raise TimeoutError("15-minute experiment bound")
        cwd = cwd or repo
        before_git = snapshot(fixture)
        oracle = execute([GIT, "check-ignore", *git_args], cwd, env, data)
        after_git = snapshot(fixture)
        before_den = after_git
        actual = execute(den_args, cwd, env, data)
        after_den = snapshot(fixture)
        row = {"family": family, "name": name, "cwd": str(cwd), "git_args": git_args,
               "den_args": [str(x) for x in den_args], "stdin_hex": None if data is None else data.hex(),
               "git": oracle, "den": actual, "equal": oracle == actual,
               "git_writes": changes(before_git, after_git), "den_writes": changes(before_den, after_den),
               "before_git": remember(before_git), "after_git": remember(after_git),
               "before_den": remember(before_den), "after_den": remember(after_den),
               "metadata": metadata or {}}
        report["rows"].append(row)
        if not row["equal"]:
            print("MISMATCH", family, name, "git", oracle["status"], bytes.fromhex(oracle["stdout"]), bytes.fromhex(oracle["stderr"]),
                  "den", actual["status"], bytes.fromhex(actual["stdout"]), bytes.fromhex(actual["stderr"]), flush=True)
        if row["git_writes"] or row["den_writes"]:
            print("UNEXPECTED WRITE", family, name, row["git_writes"], row["den_writes"], flush=True)

    def module(fixture, repo, env, family, path, mode="query", metadata=None):
        flags = ["-v", "--no-index"]
        if mode == "query-plain":
            flags = ["--no-index"]
        elif mode == "query-n":
            flags = ["-v", "-n", "--no-index"]
        is_dir = (repo / path).is_dir() and not (repo / path).is_symlink()
        measured(fixture, repo, env, family, f"module-{mode}-{path}", [*flags, "--", path],
                 [client, mode, repo / ".git", repo, path, "dir" if is_dir else "file"], metadata=metadata)

    def cmd(fixture, repo, env, family, name, operands, flags=("-v",), data=None, cwd=None):
        argv = [*flags]
        if operands:
            argv += ["--", *operands]
        measured(fixture, repo, env, family, name, argv, [command, "check-ignore", *argv], data=data, cwd=cwd)

    try:
        # Global excludes representations, defaults, and explicitly disabled defaults.
        for variant in ["absolute", "relative", "tilde", "xdg", "home-empty-xdg", "home-unset-xdg", "disabled", "missing", "quoted-source"]:
            f, repo, env = fresh("global-" + variant, None)
            pattern = b"*.tmp\n!keep.tmp\n/root-only\n"
            chosen = None
            if variant == "absolute":
                chosen = f / "absolute.ignore"
                write(chosen, pattern)
                setup_git(repo, env, "config", "core.excludesFile", str(chosen))
            elif variant == "relative":
                chosen = repo / "relative.ignore"
                write(chosen, pattern)
                setup_git(repo, env, "config", "core.excludesFile", "relative.ignore")
            elif variant == "tilde":
                chosen = pathlib.Path(env["HOME"]) / "personal.ignore"
                write(chosen, pattern)
                setup_git(repo, env, "config", "core.excludesFile", "~/personal.ignore")
            elif variant in ("xdg", "disabled"):
                chosen = pathlib.Path(env["XDG_CONFIG_HOME"]) / "git/ignore"
                write(chosen, pattern)
                if variant == "disabled":
                    setup_git(repo, env, "config", "core.excludesFile", "")
            elif variant.startswith("home-"):
                chosen = pathlib.Path(env["HOME"]) / ".config/git/ignore"
                write(chosen, pattern)
                if variant == "home-empty-xdg":
                    env["XDG_CONFIG_HOME"] = ""
                else:
                    env.pop("XDG_CONFIG_HOME")
            elif variant == "missing":
                setup_git(repo, env, "config", "core.excludesFile", str(f / "missing.ignore"))
            else:
                chosen = f / 'global "quote\ttab.ignore'
                write(chosen, pattern)
                setup_git(repo, env, "config", "core.excludesFile", str(chosen))
            for path in ["scratch.tmp", "keep.tmp", "root-only", "a/scratch.tmp", "a/root-only", "none"]:
                for mode in ["query", "query-plain", "query-n"]:
                    module(f, repo, env, "global-" + variant, path, mode)
            # The command client preserves cwd-relative operand spelling, unlike
            # the canonical-root-path module probe. Compare those independently.
            for operand in ["scratch.tmp", "../scratch.tmp", "./root-only"]:
                cmd(f, repo, env, "global-" + variant, "nested-cwd-" + operand, [operand], cwd=repo / "a")

        # Cross-source precedence, within-file ordering and excluded-parent barrier.
        f, repo, env = fresh("precedence")
        global_file = f / "global.ignore"
        write(global_file, "*.tmp\n*.log\n*.global\n!global-keep.tmp\n/global-only\n")
        setup_git(repo, env, "config", "core.excludesFile", str(global_file))
        write(repo / ".git/info/exclude", "*.tmp\n*.log\n!info-keep.tmp\ninfo-only\n/anchored.info\n")
        write(repo / ".gitignore", "*.tmp\n!root-keep.tmp\nblocked/\nopened/\n!opened/\nopened/*\n!opened/file\nroot-only\na/parent.txt\n")
        write(repo / "a/.gitignore", "!local-keep.tmp\nlocal*.global\n!parent.txt\n/here\ndeep/*\n!deep/visible\n")
        write(repo / "a/deep/.gitignore", "!deep-keep.tmp\n!leaf\n")
        write(repo / "blocked/.gitignore", "!file\n")
        paths = ["global-only", "a/global-only", "info-only", "anchored.info", "a/anchored.info", "global-keep.tmp",
                 "info-keep.tmp", "root-keep.tmp", "a/local-keep.tmp", "a/deep/deep-keep.tmp", "a/local.global",
                 "a/parent.txt", "a/here", "a/deep/here", "a/deep/visible", "a/deep/leaf", "blocked/file", "opened/file"]
        for path in paths:
            write(repo / path, b"fixture\n")
        for path in [*paths, "blocked", "opened", "a", "a/deep"]:
            module(f, repo, env, "precedence", path)
            cmd(f, repo, env, "precedence", "command-" + path, [path], flags=("-v", "--no-index"))

        # Literal operand bytes, raw pattern fields and source/path C quoting.
        f, repo, env = fresh("literal-names")
        names = ["literal*name", "literal?name", "bracket[name]", 'quote"name', "back\\slash", "tab\tname", "space name", "#hash", "!bang", "é.tmp"]
        pattern = b'literal\\*name\nliteral\\?name\nbracket\\[name\\]\nquote\\"name\nback\\\\slash\ntab\tname\nspace name\n\\#hash\n\\!bang\n*.tmp\n'
        write(repo / ".gitignore", pattern)
        for name in names:
            write(repo / name, b"fixture\n")
            module(f, repo, env, "literal-names", name, metadata={"pattern_hex": pattern.hex()})
            cmd(f, repo, env, "literal-names", "command-" + name, [name], flags=("-v", "--no-index"))
        cmd(f, repo, env, "literal-names", "all-nul", [], flags=("-v", "--no-index", "-z", "--stdin"), data=b"\0".join(n.encode() for n in names) + b"\0")
        setup_git(repo, env, "config", "core.quotePath", "false")
        cmd(f, repo, env, "literal-names", "nonascii-quotePath-false", ["é.tmp"], flags=("-v", "--no-index"))

        # Invalid brackets against the literal bracket names themselves, unlike
        # a matrix that only tests invalid patterns against ordinary names.
        f, repo, env = fresh("invalid-brackets")
        bad = [b"[", b"[abc", b"[!", b"[!]", b"[]", b"[z-a]", b"[[:unknown:]]", b"[[:digit:]", b"[\\]", b"[.a.]", b"[]]", b"[!]]"]
        for n, pattern in enumerate(bad):
            write(repo / ".gitignore", pattern + b"\n")
            candidates = [pattern.decode(), "[", "]", "a", "7"]
            for path in dict.fromkeys(candidates):
                if not (repo / path).is_dir():
                    write(repo / path, b"fixture\n")
                module(f, repo, env, "invalid-brackets", path, metadata={"pattern_hex": pattern.hex(), "case": n})
                cmd(f, repo, env, "invalid-brackets", f"command-{n}-{path}", [path], flags=("-v", "--no-index"))

        # Follow global/info links, never follow a per-directory .gitignore.
        for variant in ["root-link", "nested-link", "dangling-root", "blocked-nested-link", "global-link", "info-link"]:
            f, repo, env = fresh("symlink-" + variant)
            target = f / "patterns"
            write(target, "*.tmp\n")
            if variant == "root-link":
                (repo / ".gitignore").symlink_to(target)
            elif variant == "dangling-root":
                (repo / ".gitignore").symlink_to(f / "absent")
            elif variant == "nested-link":
                (repo / "a/.gitignore").symlink_to(target)
            elif variant == "blocked-nested-link":
                write(repo / ".gitignore", "a/\n")
                (repo / "a/.gitignore").symlink_to(target)
            elif variant == "global-link":
                link = f / "linked.ignore"
                link.symlink_to(target)
                setup_git(repo, env, "config", "core.excludesFile", str(link))
            else:
                (repo / ".git/info").mkdir(parents=True, exist_ok=True)
                (repo / ".git/info/exclude").symlink_to(target)
            for path in ["scratch.tmp", "a/scratch.tmp", "a/deep/leaf.tmp", "none"]:
                module(f, repo, env, "symlink-" + variant, path)
                cmd(f, repo, env, "symlink-" + variant, "command-" + path, [path], flags=("-v", "--no-index"))
            cmd(f, repo, env, "symlink-" + variant, "batch", ["a/scratch.tmp", "a/deep/leaf.tmp"], flags=("-v", "--no-index"))

        # Tracked paths, tracked directory prefixes and literal metacharacters.
        f, repo, env = fresh("tracked")
        tracked = ["tracked.tmp", "nested/track.tmp", "literal*name"]
        for name in [*tracked, "nested/untracked.tmp", "literalXname", "visible"]:
            write(repo / name, b"fixture\n")
        write(repo / ".gitignore", "*.tmp\nnested/\nliteral*name\n!visible\n")
        setup_git(repo, env, "add", "-f", "--", *tracked)
        for name in [*tracked, "nested", "nested/untracked.tmp", "literalXname", "visible", "missing.tmp"]:
            for flags in [(), ("-v",), ("-v", "-n"), ("--no-index",), ("-v", "--no-index"), ("-v", "-n", "--no-index")]:
                cmd(f, repo, env, "tracked", str(flags) + ":" + name, [name], flags=flags)
        cmd(f, repo, env, "tracked", "batch-default", tracked, flags=("-v",))
        cmd(f, repo, env, "tracked", "batch-no-index", tracked, flags=("-v", "--no-index"))
        cmd(f, repo, env, "tracked", "stdin-nul-default", [], flags=("-v", "-n", "-z", "--stdin"), data=b"\0".join(n.encode() for n in tracked) + b"\0")
        cmd(f, repo, env, "tracked", "stdin-nul-no-index", [], flags=("-v", "-n", "--no-index", "-z", "--stdin"), data=b"\0".join(n.encode() for n in tracked) + b"\0")
        report["completed"] = True
    finally:
        report["elapsed_s"] = time.monotonic() - started
        report["counts"] = dict(collections.Counter(row["family"] for row in report["rows"]))
        report["parity"] = sum(row["equal"] for row in report["rows"])
        report["mismatches"] = len(report["rows"]) - report["parity"]
        report["write_failures"] = sum(bool(row["git_writes"] or row["den_writes"]) for row in report["rows"])
        output.write_text(json.dumps(report, indent=2) + "\n")
    print("RESULT", output, "rows", len(report["rows"]), "parity", report["parity"], "mismatches", report["mismatches"],
          "write_failures", report["write_failures"], "seconds", report["elapsed_s"], flush=True)
    return int(bool(report["mismatches"] or report["write_failures"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="full")
    parser.add_argument("--tier", default="native")
    raise SystemExit(run(parser.parse_args()))
