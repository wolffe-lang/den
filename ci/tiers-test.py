#!/usr/bin/env python3
"""ci/tiers-test.py — the planner's own proof (wolf-lang's tl21 test, as
lope cut it, cut again to den's workflow). python3 only.

  T1  the tiers by event: a trunk push, the nightly, a dispatch with no
      jobs and the `full-matrix` label are full; another label's
      `labeled` event is a noop; a dispatch naming jobs is partial, and
      refuses a job the workflow does not have.
  T2  the pull-request tiers by path: code is pr (linux, plan-test);
      prose alone is noop; prose beside code is pr.
  T3  full wins: a path no rule names; changed paths that cannot be read.
  T4  the wiring of .github/workflows/ci.yml: every job but `plan` needs
      it and runs only when the plan names it; `tier` needs every job,
      runs on `!cancelled()` and calls the verdict; cancel-in-progress is
      for pull requests only; the trunk push, the nightly, the label and
      the dispatch input are there; macos is no pull-request job.
  T6  the verdict: green for a full, a pr, a noop and a partial run; red
      for a chosen job failed or skipped, a job that ran unasked, a failed
      plan, a plan with no tier, a full that chose less.
  T8  ci/nightly-red.sh against a stand-in `gh` (boreutils' T8): no open
      issue opens one; an open one is commented on; a label that exists is
      no failure; the script refuses without its environment; the
      nightly-red job runs on a failed schedule only, after the verdict.
  T13 a trunk push's macOS job already green at its commit, against a
      stand-in API and a scratch git repository: a completed, successful pull
      request or dispatch run at the commit, whose plan tested the same tree
      and has the job once, green, on macOS, lets the push leave it, and the
      plan names the run; anything less runs it: another event, another tree,
      no tree, a missing, duplicate, cancelled or Linux job, a short listing,
      an error, a timeout, a redirect, no token, another commit. Only the
      runner's own push to trunk asks (a labelled pull request's run hands
      its plan EVENT=push). The verdict accepts exactly the covered job and
      names its run; the wiring gives the plan its tree step, the runs to
      read and the token, and no job-level permission.

Exit 0 when every check passes, 1 otherwise.
"""
import json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "ci", "tiers.py")
WF = open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
KEYS = ("EVENT", "ACTION", "LABEL", "LABELS", "HEAD_SHA", "IN_JOBS", "NEEDS")
fails = 0
ALL = ["plan-test", "linux", "macos"]
PR = ["plan-test", "linux"]


def say(ok, what):
    global fails
    print("tiers-test: %s %s" % ("PASS" if ok else "FAIL", what))
    fails += not ok


def env(**more):
    e = {k: v for k, v in os.environ.items() if k not in KEYS}
    e.update(more)
    return e


def plan(paths=None, **kw):
    args = [sys.executable, PLAN, "plan", "--json"]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    if paths is not None:
        args += ["--paths-from", "-"]
    r = subprocess.run(args, input="\n".join(paths or []) + "\n", capture_output=True, text=True, env=env())
    if r.returncode != 0:
        return {"tier": "ERROR %d" % r.returncode, "jobs": []}
    return json.loads(r.stdout)


def verdict(needs):
    r = subprocess.run([sys.executable, PLAN, "verdict"], capture_output=True, text=True,
                       env=env(NEEDS=json.dumps(needs)))
    return r.returncode


def needs_for(tier, chosen, results=None):
    n = {"plan": {"result": "success", "outputs": {"tier": tier, "jobs": json.dumps(chosen)}}}
    for j in ALL:
        n[j] = {"result": (results or {}).get(j, "success" if j in chosen else "skipped")}
    return n


# T1
for ev in ("push", "schedule", "workflow_dispatch"):
    p = plan(event=ev)
    say(p["tier"] == "full" and p["jobs"] == ALL, "T1 %s is full" % ev)
p = plan(["src/den.lu"], event="pull_request", action="labeled", label="full-matrix", labels="full-matrix")
say(p["tier"] == "full" and p["jobs"] == ALL, "T1 the full-matrix label is full")
p = plan(["src/den.lu"], event="pull_request", action="labeled", label="docs", labels="docs")
say(p["tier"] == "noop" and p["jobs"] == [], "T1 another label is a noop")
p = plan(event="workflow_dispatch", jobs="linux")
say(p["tier"] == "partial" and p["jobs"] == ["linux"], "T1 a dispatch naming linux is partial")
p = plan(event="workflow_dispatch", jobs="windows")
say(p["tier"].startswith("ERROR"), "T1 a dispatch naming no job of the workflow is refused")
# T2
p = plan(["src/walk/walk.lu", "tests/oracle/sets.tsv"], event="pull_request", action="synchronize")
say(p["tier"] == "pr" and p["jobs"] == PR, "T2 code is pr")
p = plan(["README.md", "notes/ap00-the-first-light.md", "CHANGELOG.md", "docs/MAP.md"], event="pull_request", action="opened")
say(p["tier"] == "noop", "T2 prose alone is a noop")
p = plan(["README.md", "src/den.lu"], event="pull_request", action="opened")
say(p["tier"] == "pr", "T2 prose beside code is pr")
# Object plumbing must run in the PR Linux gate, not only nightly.
for path in ("src/object/store.lu", "src/oid/oid.lu", "src/index/index.lu", "src/repository/repository.lu", "tools/check-objects", "tools/objects-test.py", "probes/object-client/main.lu"):
    p = plan([path], event="pull_request", action="synchronize")
    say(p["tier"] == "pr" and p["jobs"] == PR, "T2 object gate path " + path)
gate = open(os.path.join(ROOT, "tools", "gate")).read()
say("tools/check-wire" in gate.splitlines(), "T2 wire integration gate is mandatory")
wire_gate = open(os.path.join(ROOT, "tools", "check-wire")).read()
say("tools/check-porcelain" in wire_gate.splitlines(), "T2 configured porcelain gate is mandatory")
for path in ("src/pktline/pktline.lu", "src/wiregit/upload.lu", "src/refs/transaction.lu", "tools/check-wire", "probes/wire-client/main.lu"):
    p = plan([path], event="pull_request", action="synchronize")
    say(p["tier"] == "pr" and p["jobs"] == PR, "T2 wire gate path " + path)
say("tools/check-http" in gate.splitlines(), "T2 smart-HTTP gate is mandatory")
for path in ("src/http/client.lu", "src/transport/peer.lu", "tools/check-http", "tools/http-git-test.py", "probes/http-client/main.lu"):
    p = plan([path], event="pull_request", action="synchronize")
    say(p["tier"] == "pr" and p["jobs"] == PR, "T2 smart-HTTP gate path " + path)
say("tools/check-objects" in gate, "T2 object integration gate is mandatory")
for command in ("tools/check-config", "tools/check-index", "tools/check-ignore", "tools/check-worktree", "tools/check-commit", "tools/check-history"):
    say(command in gate, "T2 M2 integration gate is mandatory: " + command)
say("--filter rev-parse --strict" in gate, "T2 strict witness remains unimplemented")
say("tools/check-housekeeping" in gate, "T2 housekeeping and validator gate is mandatory")
say("tools/check-blame" in gate, "T2 blame attribution gate is mandatory")
say("tools/check-stash" in gate, "T2 stash and notes gate is mandatory")
say("tools/check-revision" in gate, "T2 shared revision grammar gate is mandatory")
say("tools/check-history" in gate, "T2 inherited history gate remains mandatory")
say("tools/check-refs" in gate, "T2 refs integration gate is mandatory")
say("tools/check-merge" in gate, "T2 merge integration gate is mandatory")
say("tools/check-everyday" in gate.splitlines(), "T2 everyday exact-row gate is mandatory")
say("tools/check-submodule" in gate.splitlines(), "T2 submodule exact-row gate is mandatory")
say("tools/check-status-speed" in gate.splitlines(), "T2 status ratio row is mandatory")
say("tools/check-newest-wolf" in gate.splitlines(), "T2 the newest wolf release builds den too")
say("tools/check-replay" in gate, "T2 replay integration gate is mandatory")
say("tools/check-pack-write" in gate, "T2 pack writer R4c gate is mandatory")
say("tools/check-pack" in gate, "T2 packed storage and packed regression gate is mandatory")
for path in ("src/pack/read.lu", "tools/check-pack", "tools/pack-interop.py", "tools/packed-fixture.py", "probes/pack-client/main.lu"):
    p = plan([path], event="pull_request", action="synchronize")
    say(p["tier"] == "pr" and p["jobs"] == PR, "T2 pack gate path " + path)
for command in ("tools/check-diff --units-only", "tools/check-delta", "tools/check-rename", "tools/check-diff --corpus-only", "tools/check-diffbinary --reviewed-body --with-cli"):
    say(command in gate, "T2 diff integration gate is mandatory: " + command)
cases = json.load(open(os.path.join(ROOT, "tests", "cases.json")))
say(next(c for c in cases if c['name']=='fsck').get('require_parity') is True,
    "T2 validated packed fsck cannot regress to a named refusal")
say(all(c.get("require_parity") for c in cases if c["args"][0] in ("diff", "log", "show", "branch", "tag", "switch", "merge", "blame", "stash", "notes")),
    "T2 implemented diff/history/refs cases cannot regress to named refusals")
say(all(c.get("require_parity") for c in cases if c["name"] in ("reset", "rebase", "rebase-up-to-date", "cherry-pick-redundant")),
    "T2 replay parity rows cannot regress to named refusals")
# T3
p = plan(["somewhere/new"], event="pull_request", action="opened")
say(p["tier"] == "full", "T3 a path no rule names is full")
r = subprocess.run([sys.executable, PLAN, "plan", "--json", "--event", "pull_request", "--action", "opened"],
                   capture_output=True, text=True, env=env())
say(json.loads(r.stdout)["tier"] == "full", "T3 unreadable paths are full")
# T4
linux_block = WF.split("\n  linux:\n", 1)[1].split("\n  macos:\n", 1)[0]
say(re.search(r"^    timeout-minutes: 180$", linux_block, re.M) is not None,
    "T4-linux-budget the Linux full gauntlet has a 180-minute budget")
jobs = re.findall(r"^  ([a-z-]+):\s*$", WF.split("\njobs:\n", 1)[1], re.M)
say(jobs == ["plan", "plan-test", "linux", "macos", "tier", "nightly-red"], "T4 the jobs, in order: %s" % jobs)
for j in ALL:
    blk = WF.split("\n  %s:\n" % j, 1)[1].split("\n  ", 1)[0] + WF.split("\n  %s:\n" % j, 1)[1].split("\n\n  ", 1)[0]
    say("needs: plan" in blk and "contains(fromJSON(needs.plan.outputs.jobs || '[]'), '%s')" % j in blk,
        "T4 %s needs the plan and runs only when it is named" % j)
tblk = WF.split("\n  tier:\n", 1)[1]
say(all("- %s" % j in tblk for j in ["plan"] + ALL) and "!cancelled()" in tblk and "ci/tiers.py verdict" in tblk,
    "T4 tier needs every job, runs unless cancelled, checks the verdict")
say("cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in WF, "T4 cancel-in-progress for pull requests only")
say("branches: [trunk]" in WF and "schedule:" in WF and "labeled" in WF and "inputs:" in WF,
    "T4 the trunk push, the nightly, the label and the dispatch input")
# T6
say(verdict(needs_for("full", ALL)) == 0, "T6 a green full")
say(verdict(needs_for("pr", PR)) == 0, "T6 a green pr")
say(verdict(needs_for("noop", [])) == 0, "T6 a green noop")
say(verdict(needs_for("partial", ["linux"])) == 0, "T6 a green partial")
say(verdict(needs_for("pr", PR, {"linux": "failure"})) == 1, "T6 a chosen job failed")
say(verdict(needs_for("pr", PR, {"linux": "skipped"})) == 1, "T6 a chosen job skipped")
say(verdict(needs_for("pr", PR, {"macos": "success"})) == 1, "T6 a job that ran unasked")
say(verdict(needs_for("full", PR)) == 1, "T6 a full that chose less")
n = needs_for("pr", PR)
n["plan"]["result"] = "failure"
say(verdict(n) == 1, "T6 a failed plan")
n = needs_for("pr", PR)
n["plan"]["outputs"]["tier"] = ""
say(verdict(n) == 1, "T6 a plan with no tier")
# T8
RED = os.path.join(ROOT, "ci", "nightly-red.sh")
WORKFLOW_NAME = "ci"
FAKE_GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_LOG"
case "$1 $2" in
  "label create") exit "${FAKE_LABEL_RC:-0}" ;;
  "issue list") printf '%s' "${FAKE_EXISTING:-}"; [ -n "${FAKE_EXISTING:-}" ] && echo; exit 0 ;;
esac
exit 0
"""


def nightly_red(existing="", label_rc=0):
    d = tempfile.mkdtemp(prefix="tiers-test-gh-")
    try:
        with open(os.path.join(d, "gh"), "w") as f:
            f.write(FAKE_GH)
        os.chmod(os.path.join(d, "gh"), 0o755)
        log = os.path.join(d, "log")
        e = env(PATH=d + os.pathsep + os.environ.get("PATH", ""), FAKE_LOG=log, FAKE_EXISTING=existing,
                FAKE_LABEL_RC=str(label_rc), REPO="wolffe-lang/den", WORKFLOW=WORKFLOW_NAME,
                RUN_URL="https://github.com/wolffe-lang/den/actions/runs/1")
        r = subprocess.run(["bash", RED], capture_output=True, text=True, env=e)
        calls = open(log).read().splitlines() if os.path.exists(log) else []
        return r.returncode, calls
    finally:
        shutil.rmtree(d, ignore_errors=True)


TITLE = "nightly red: %s on trunk" % WORKFLOW_NAME
rc, calls = nightly_red()
creates = [c for c in calls if c.startswith("issue create")]
say(rc == 0 and len(creates) == 1 and "--title %s" % TITLE in creates[0] and "--label nightly-red" in creates[0]
    and not [c for c in calls if c.startswith("issue comment")],
    "T8 no open issue: one is opened, labelled nightly-red, titled '%s'" % TITLE)
rc, calls = nightly_red(existing="41")
say(rc == 0 and [c for c in calls if c.startswith("issue comment 41 ")] and not [c for c in calls if c.startswith("issue create")],
    "T8 an open issue: a comment on it, no new issue")
rc, calls = nightly_red(label_rc=1)
say(rc == 0 and [c for c in calls if c.startswith("issue create")], "T8 a label that already exists is no failure")
r = subprocess.run(["bash", RED], capture_output=True, text=True, env=env())
say(r.returncode != 0, "T8 the script refuses to run without REPO, WORKFLOW and RUN_URL")
say(re.search(r"^name: %s$" % re.escape(WORKFLOW_NAME), WF, re.M) is not None, "T8 the workflow's name is %s, the title's" % WORKFLOW_NAME)
nblk = WF.split("\n  nightly-red:\n", 1)[1]
say("needs: tier" in nblk and "failure() && github.event_name == 'schedule'" in nblk and "issues: write" in nblk
    and "ci/nightly-red.sh" in nblk, "T8 nightly-red runs after the verdict, on a red schedule only, may write issues")
# T8, what the reporter writes is public: the issue's title and body, a comment,
# the label's description. The plain rule holds in every run: no lane, ruling,
# crawl or sprint word and no internal tag (two letters and two or three digits). A
# local record also passes PUBLIC_TEXT_REFUSE, a file of further words kept outside
# this repository; a word from that file is reported by its line number, never spelt.
PLAIN = re.compile(r"\b(?:lanes?|rulings?|crawls?|sprints?)\b|\b[a-z]{2}\d{2,3}[a-z]?\b", re.I)
LISTED = []
if os.environ.get("PUBLIC_TEXT_REFUSE"):
    with open(os.environ["PUBLIC_TEXT_REFUSE"], encoding="utf-8") as fh:
        LISTED = [(n, re.compile(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(w.strip()), re.I))
                  for n, w in enumerate(fh, 1) if w.strip() and not w.startswith("#")]


def _log_lines(x):
    return x.splitlines() if isinstance(x, str) else list(x)


written = "\n".join(c for e in ("", "41") for c in _log_lines(nightly_red(existing=e)[1]) if not c.startswith("issue list"))
said = sorted({m.group(0) for m in PLAIN.finditer(written)}) + ["listed word %d" % n for n, rx in LISTED if rx.search(written)]
say(bool(written) and not said, "T8 nothing the reporter writes in public carries an internal word (%s)%s" % (
    "the plain rule and %d listed words" % len(LISTED) if LISTED else "the plain rule", ": " + ", ".join(said) if said else ""))

T13_REPO = "wolffe-lang/den"
T13_MAC = {"macOS Homebrew git field leg (nonblocking)": "macos-latest"}
T13_IDS = {"macOS Homebrew git field leg (nonblocking)": "macos"}

# T13: the macOS job a trunk push may leave (its name: runner label), as GitHub
# names it; T13_IDS, each one's job id; T13_LINUX, other jobs a run has; and
# the names the rows below read, from this file's own.
T13_WHOLE = list(T13_MAC)
T13_LINUX = ["linux", "plan-test"]
ENV_KEYS = KEYS
WORKFLOW_FILE = "ci.yml"
wf = WF
EVERY = list(ALL)


def t13_verdict(needs):
    r = subprocess.run([sys.executable, PLAN, "verdict"], capture_output=True, text=True, env=env(NEEDS=json.dumps(needs)))
    return r.returncode, r.stdout + r.stderr

# --- T13 a trunk push leaves the macOS legs already green at its commit -----------
# Merges are fast-forwards, so a trunk push runs the commit its pull request's run
# has just passed. On the runner's own push to trunk the plan asks the REST API for
# this workflow's runs at the commit and leaves a macOS leg or job only on positive
# evidence. These rows run the planner as the workflow does (EVENT, and the
# runner's GITHUB_EVENT_NAME, GITHUB_REF, GITHUB_SHA, GITHUB_REPOSITORY,
# GITHUB_API_URL; PLAN_TOKEN) over a scratch git repository (--repo), against a
# stand-in API on 127.0.0.1; then the verdict's rows and the wiring's.
import http.server
import math
import threading
import time
import urllib.parse

T13_TOKEN = "tiers-test-stand-in-token-5e8a"
T13_SCRUB = ENV_KEYS + ("PLAN_TOKEN", "PLAN_API_TIMEOUT", "GH_TOKEN", "GITHUB_TOKEN", "GITHUB_EVENT_NAME", "GITHUB_REF",
                        "GITHUB_SHA", "GITHUB_REPOSITORY", "GITHUB_API_URL", "GITHUB_SERVER_URL", "GITHUB_STEP_SUMMARY",
                        "GITHUB_OUTPUT")
T13_WF_PATH = ".github/workflows/" + WORKFLOW_FILE


class T13Server(http.server.ThreadingHTTPServer):
    # A client that timed out leaves a handler writing to a closed socket.
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class T13API:
    """The REST API's two answers the plan reads: the runs of the workflow at a
    commit, and a run's jobs (paged). `fault` is (path prefix, kind)."""

    def __init__(self, runs=(), jobs=None, fault=None, page_cap=100, ignore_filter=False, totals=None):
        self.runs, self.jobs = list(runs), dict(jobs or {})
        self.fault, self.page_cap, self.ignore_filter = fault, page_cap, ignore_filter
        self.totals, self.requests, self.redirect_to = dict(totals or {}), [], None
        api = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                api.requests.append((self.path, self.headers.get("Authorization")))
                status, body, extra = api.answer(self.path)
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                for k, v in extra.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = T13Server(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def answer(self, path):
        u = urllib.parse.urlsplit(path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if self.fault and u.path.startswith(self.fault[0]):
            kind = self.fault[1]
            if kind in (500, 403, 404):
                return kind, {"message": "stand-in error %d" % kind}, {}
            if kind == "html":
                return 200, b"<html>not json</html>", {}
            if kind == "keys":
                return 200, {"message": "an answer without the expected keys"}, {}
            if kind == "slow":
                time.sleep(4)
            if kind == "redirect":
                return 302, {}, {"Location": self.redirect_to + path}
        if u.path == "/repos/%s/actions/workflows/%s/runs" % (T13_REPO, WORKFLOW_FILE):
            rs = [x for x in self.runs if self.ignore_filter or x["head_sha"] == q.get("head_sha")]
            return 200, {"total_count": len(rs), "workflow_runs": rs}, {}
        m = re.fullmatch(r"/repos/%s/actions/runs/(\d+)/jobs" % re.escape(T13_REPO), u.path)
        if m:
            rid = int(m.group(1))
            js = self.jobs.get(rid, [])
            per, page = min(int(q.get("per_page", 30)), self.page_cap), int(q.get("page", 1))
            return 200, {"total_count": self.totals.get(rid, len(js)), "jobs": js[(page - 1) * per:page * per]}, {}
        return 404, {"message": "Not Found"}, {}


T13_GIT = """#!/bin/sh
# A stand-in for git: the plan's two questions about the checkout, the
# pushed commit and its tree, and nothing else (any other call fails, so a
# plan that asks git anything more fails its rows).
[ "$1" = "-C" ] && shift 2
if [ "$*" = "rev-parse HEAD" ]; then echo "$T13_HEAD"; exit 0; fi
if [ "$*" = "rev-parse HEAD^{tree}" ]; then echo "$T13_TREE"; exit 0; fi
echo "stand-in git: not answered: $*" >&2
exit 1
"""


def t13_repo():
    """The checkout a trunk push plans in: a directory whose `git` (first on
    the plan's PATH) answers for a pushed commit and its tree, so these rows
    need no git of their own."""
    d = tempfile.mkdtemp(prefix="tiers-test-push-")
    with open(os.path.join(d, "git"), "w") as f:
        f.write(T13_GIT)
    os.chmod(os.path.join(d, "git"), 0o755)
    return d, "a1" * 20, "b2" * 20


T13_DIR, T13_SHA, T13_TREE = t13_repo()
T13_SEEN = []


def t13_plan(api, event="push", event_name="push", ref="refs/heads/trunk", sha=None, token=T13_TOKEN, timeout=None,
             summary=None):
    d = tempfile.mkdtemp(prefix="tiers-test-out-")
    out = os.path.join(d, "output")
    open(out, "w").close()
    env = {k: v for k, v in os.environ.items() if k not in T13_SCRUB}
    env.update(GITHUB_EVENT_NAME=event_name, GITHUB_REF=ref, GITHUB_SHA=sha or T13_SHA, GITHUB_REPOSITORY=T13_REPO,
               GITHUB_API_URL=api.url, GITHUB_SERVER_URL="https://github.com", T13_HEAD=T13_SHA, T13_TREE=T13_TREE)
    env["PATH"] = T13_DIR + os.pathsep + env.get("PATH", "")
    if token:
        env["PLAN_TOKEN"] = token
    if timeout:
        env["PLAN_API_TIMEOUT"] = str(timeout)
    if summary:
        env["GITHUB_STEP_SUMMARY"] = summary
    r = subprocess.run([sys.executable, PLAN, "plan", "--event", event, "--repo", T13_DIR, "--github-output", out],
                       capture_output=True, text=True, env=env, timeout=120)
    text = open(out).read()
    shutil.rmtree(d, ignore_errors=True)
    T13_SEEN.append(r.stdout + r.stderr + text)
    if r.returncode != 0:
        return {"ERROR": r.returncode}, r.stderr
    o = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    got = {"tier": o.get("tier"), "jobs": json.loads(o.get("jobs", "null")),
           "matrix": {k: json.loads(v) for k, v in o.items() if k.startswith("matrix_")}}
    got["covered"] = json.loads(o["macos_covered"]) if "macos_covered" in o else None
    return got, r.stderr


def t13_render(job, leg):
    return "%s (%s)" % (job, ", ".join(str(v).lower() if isinstance(v, bool) else str(v) for v in leg.values()))


def t13_less(p, names):
    """A plan less the macOS legs and jobs named."""
    q = {"tier": p["tier"], "jobs": [j for j in p["jobs"] if not any(T13_IDS.get(n) == j for n in names)]}
    q["matrix"] = {k: [l for l in v if t13_render(k[len("matrix_"):], l) not in names] for k, v in p["matrix"].items()}
    return q


def t13_wrun(rid, event="pull_request", conclusion="success", status="completed", sha=None, path=None):
    return {"id": rid, "event": event, "status": status, "conclusion": conclusion, "head_sha": sha or T13_SHA,
            "path": path or T13_WF_PATH, "run_attempt": 1}


def t13_job(name, conclusion="success", labels=None, steps=None):
    return {"name": name, "status": "completed", "conclusion": conclusion,
            "labels": labels if labels is not None else [T13_MAC.get(name, "ubuntu-24.04")], "steps": steps or []}


def t13_green(tree=None, step=True, drop=(), swap=None, extra=()):
    steps = [{"name": "Set up job", "conclusion": "success"}]
    if step:
        steps.append({"name": "the tree under test is %s" % (tree or T13_TREE), "conclusion": "success"})
    js = [t13_job("plan", steps=steps), t13_job("tier full")] + [t13_job(n) for n in T13_LINUX]
    js += [(swap or {}).get(n, t13_job(n)) for n in T13_MAC if n not in drop]
    return js + list(extra)


T13_PLANS = []
T13_LINE = re.compile(r"^tiers: (skip|keep) (.+?): (.*)$", re.M)


def t13_row(what, api, want_names, **kw):
    """`want_names`: the macOS names the plan should leave (the rest run)."""
    got, err = t13_plan(api, **kw)
    T13_PLANS.append(got)
    want = t13_less(T13_FULL, want_names)
    lines = T13_LINE.findall(err)
    skipped = {n: why for v, n, why in lines if v == "skip"}
    ok = ("ERROR" not in got and {k: got[k] for k in ("tier", "jobs", "matrix")} == want
          and sorted(got["covered"] or {}) == sorted(want_names) and sorted(n for _, n, _ in lines) == sorted(T13_MAC)
          and sorted(skipped) == sorted(want_names))
    say(ok, "T13 %s: leaves %s%s" % (what, sorted(want_names) or "no macOS leg",
                                      "" if ok else " (got %s; lines %s)" % (got, [(v, n) for v, n, _ in lines])))
    return got, err, skipped


T13_FULL, _ = t13_plan(T13API(), token=None)
say("ERROR" not in T13_FULL and T13_FULL["tier"] == "full" and T13_FULL["covered"] == {}
    and sorted(n for n in T13_MAC) == sorted(
        [t13_render(k[len("matrix_"):], l) for k, v in T13_FULL["matrix"].items() for l in v if l["os"].startswith("macos")]
        + [n for n, j in T13_IDS.items() if j in T13_FULL["jobs"]]),
    "T13 a trunk push with no token plans the full tier, covers nothing, and its macOS legs are %s" % sorted(T13_MAC))

summary = os.path.join(tempfile.mkdtemp(prefix="tiers-test-sum-"), "summary.md")
api = T13API([t13_wrun(7001)], {7001: t13_green()})
got, err, skipped = t13_row("a green pull request run at the commit and tree", api, list(T13_MAC), summary=summary)
say(got.get("covered") and all((c["run"], c["event"], c["sha"], c["tree"], c["label"]) == (7001, "pull_request", T13_SHA, T13_TREE, T13_MAC[n])
                               for n, c in got["covered"].items())
    and all(("green in pull_request run 7001 at %s, tree %s" % (T13_SHA, T13_TREE)) in why for why in skipped.values()),
    "T13 each skip names the run it relied on (pull_request run 7001), the commit and the tree")
say(os.path.exists(summary) and open(summary).read().count("7001") >= len(T13_MAC), "T13 the step summary names the run for each skipped leg")
jq = [urllib.parse.parse_qs(urllib.parse.urlsplit(p).query) for p, _ in api.requests if "/jobs" in p]
say(jq and all(q.get("filter") == ["latest"] for q in jq), "T13 a run's jobs are read at its latest attempt (filter=latest)")
say(api.requests and all(a == "Bearer " + T13_TOKEN for _, a in api.requests), "T13 every request carries the workflow's token")
api.close()

api = T13API([t13_wrun(7002, event="workflow_dispatch")], {7002: t13_green()})
t13_row("a green dispatch run at the commit counts", api, list(T13_MAC))
api.close()
for ev in ("schedule", "push"):
    api = T13API([t13_wrun(7003, event=ev)], {7003: t13_green()})
    t13_row("a green %s run at the commit does not count" % ev, api, [])
    api.close()
api = T13API([t13_wrun(7004, conclusion="failure"), t13_wrun(7005, conclusion="cancelled"),
              t13_wrun(7006, status="in_progress", conclusion=None)], {i: t13_green() for i in (7004, 7005, 7006)})
t13_row("a failed, a cancelled and a running pull request run do not count", api, [])
api.close()
for what, jobs in (("a run that tested another tree", t13_green(tree="0" * 40)), ("a run whose plan names no tree", t13_green(step=False)),
                   ("a green run with no macOS job at all", t13_green(drop=list(T13_MAC)))):
    api = T13API([t13_wrun(7007)], {7007: jobs})
    t13_row(what + ": every macOS leg runs", api, [])
    api.close()
first = sorted(T13_MAC)[0]
rest = [n for n in T13_MAC if n != first]
for what, jobs in (("missing", t13_green(drop=[first])), ("cancelled", t13_green(swap={first: t13_job(first, conclusion="cancelled")})),
                   ("listed twice, once red", t13_green(extra=[t13_job(first, conclusion="failure")])),
                   ("run on Linux", t13_green(swap={first: t13_job(first, labels=["ubuntu-24.04"])}))):
    api = T13API([t13_wrun(7008)], {7008: jobs})
    t13_row("%s %s: it runs, the green ones do not" % (first, what), api, rest)
    api.close()
api = T13API([t13_wrun(7009), t13_wrun(7010, conclusion="failure")], {7009: t13_green(drop=[first]), 7010: t13_green()})
t13_row("two runs at the commit, the red one with every leg: only the green one counts", api, rest)
api.close()
if rest:
    api = T13API([t13_wrun(7011), t13_wrun(7012, event="workflow_dispatch")], {7011: t13_green(drop=[first]), 7012: t13_green(drop=rest)})
    t13_row("two green runs, each with some legs: each leg relies on a run that has it", api, list(T13_MAC))
    api.close()
api = T13API([t13_wrun(7013)], {7013: t13_green()}, page_cap=2)
t13_row("a jobs listing over several pages is read to its count", api, list(T13_MAC))
pages = math.ceil(len(t13_green()) / 2)
say(pages >= 2 and len([p for p, _ in api.requests if "/jobs" in p]) == pages, "T13 the planner read every page (%d)" % pages)
api.close()
api = T13API([t13_wrun(7014)], {7014: t13_green()}, totals={7014: 999})
t13_row("a jobs listing short of its total_count is no evidence", api, [])
api.close()
api = T13API([t13_wrun(7015, sha="1" * 40), t13_wrun(7016, path=".github/workflows/other.yml")], {7015: t13_green(), 7016: t13_green()},
             ignore_filter=True)
t13_row("runs of another commit or another workflow, listed anyway, do not count", api, [])
api.close()
for where, kind in (("/repos/%s/actions/workflows" % T13_REPO, 500), ("/repos/%s/actions/runs" % T13_REPO, 403),
                    ("/repos/%s/actions/workflows" % T13_REPO, "html"), ("/repos/%s/actions/runs" % T13_REPO, "keys"),
                    ("/repos/%s/actions/workflows" % T13_REPO, 404)):
    api = T13API([t13_wrun(7017)], {7017: t13_green()}, fault=(where, kind))
    t13_row("the lookup answered %s at %s: every macOS leg runs" % (kind, where.rsplit("/", 1)[-1]), api, [])
    api.close()
api = T13API([t13_wrun(7018)], {7018: t13_green()}, fault=("/repos/%s/actions/workflows" % T13_REPO, "slow"))
t0 = time.time()
t13_row("the lookup timed out: every macOS leg runs", api, [], timeout=1)
say(time.time() - t0 < 30, "T13 the timeout holds (%.1f s)" % (time.time() - t0))
api.close()
elsewhere = T13API([t13_wrun(7019)], {7019: t13_green()})
api = T13API([t13_wrun(7019)], {7019: t13_green()}, fault=("/repos/%s/actions/workflows" % T13_REPO, "redirect"))
api.redirect_to = elsewhere.url
t13_row("the API redirected: not followed, every macOS leg runs", api, [])
say(elsewhere.requests == [], "T13 a redirect takes the token nowhere (the other host saw %d requests)" % len(elsewhere.requests))
api.close()
elsewhere.close()
api = T13API([t13_wrun(7020)], {7020: t13_green()})
t13_row("no token: every macOS leg runs", api, [], token=None)
t13_row("the checkout is not the pushed commit: every macOS leg runs", api, [], sha="2" * 40)
say(api.requests == [], "T13 without a token, or off the pushed commit, nothing is asked")
api.close()
# A labelled pull request's run hands its plan EVENT=push: only the runner's own
# event and ref decide. Neither that run, another branch's push, the nightly nor a
# dispatch asks.
for what, kw in (("a labelled pull request's run (EVENT=push)", dict(event_name="pull_request")),
                 ("a push to another branch", dict(ref="refs/heads/a-lane")),
                 ("the nightly", dict(event="schedule", event_name="schedule")),
                 ("a dispatch", dict(event="workflow_dispatch", event_name="workflow_dispatch"))):
    api = T13API([t13_wrun(7021)], {7021: t13_green()})
    got, err = t13_plan(api, **kw)
    say(api.requests == [] and "ERROR" not in got and got["covered"] == {} and not T13_LINE.search(err),
        "T13 %s asks nothing and leaves nothing" % what)
    api.close()
say(all("ERROR" not in p for p in T13_PLANS), "T13 every trunk push plan exits 0")
say(T13_SEEN and not [s for s in T13_SEEN if T13_TOKEN in s], "T13 the token is never printed")
shutil.rmtree(T13_DIR, ignore_errors=True)

# The verdict: a full run less the covered legs, each covered leg named.
T13_COVER = {n: {"job": (T13_IDS[n] if n in T13_WHOLE else n.split(" (", 1)[0]), "label": T13_MAC[n], "run": 7001, "event": "pull_request",
                 "sha": "a" * 40, "tree": "b" * 40} for n in T13_MAC}
for n, c in T13_COVER.items():
    c["leg"] = None if n in T13_WHOLE else [l for l in T13_FULL["matrix"]["matrix_" + c["job"].replace("-", "_")]
                                            if t13_render(c["job"], l) == n][0]


def t13_needs(plan_, covered, ran=()):
    outs = {"tier": plan_["tier"], "jobs": json.dumps(plan_["jobs"]), "macos_covered": json.dumps(covered)}
    for k, v in plan_["matrix"].items():
        outs[k] = json.dumps(v, separators=(",", ":"))
    n = {"plan": {"result": "success", "outputs": outs}}
    for j in EVERY:
        n[j] = {"result": "success" if j in plan_["jobs"] or j in ran else "skipped", "outputs": {}}
    return n


left = t13_less(T13_FULL, list(T13_MAC))
rc, text = t13_verdict(t13_needs(left, T13_COVER))
say(rc == 0 and all(("covered %s: green in pull_request run 7001 at %s, tree %s" % (n, "a" * 40, "b" * 40)) in text for n in T13_MAC),
    "T13 a full run less its covered macOS legs reads green and names each one's run%s" % ("" if rc == 0 else ": " + text.strip()[-300:]))
for what, needs in (
        ("the covered legs left without their cover", t13_needs(left, {})),
        ("a cover in a pr tier", t13_needs(dict(left, tier="pr"), T13_COVER)),
        ("a cover that names a push run", t13_needs(left, {n: dict(c, event="push") for n, c in T13_COVER.items()})),
        ("a cover with no run", t13_needs(left, {n: dict(c, run="x") for n, c in T13_COVER.items()})),
        ("a cover that is no object", dict(t13_needs(left, {}), plan={"result": "success", "outputs": dict(
            t13_needs(left, {})["plan"]["outputs"], macos_covered='["x"]')}))):
    rc, text = t13_verdict(needs)
    say(rc == 1, "T13 the verdict says no to %s (exit %d)" % (what, rc))
linux = [(k, l) for k, v in T13_FULL["matrix"].items() for l in v if not l["os"].startswith("macos")]
if linux:
    k, l = linux[0]
    job = k[len("matrix_"):]
    name = t13_render(job, l)
    bad = dict(T13_COVER, **{name: {"job": job, "leg": l, "label": l["os"], "run": 7001, "event": "pull_request",
                                    "sha": "a" * 40, "tree": "b" * 40}})
    shorter = dict(left, matrix={kk: [x for x in vv if not (kk == k and x == l)] for kk, vv in left["matrix"].items()})
else:
    job = [j for j in left["jobs"] if j not in T13_IDS.values()][0]
    bad = dict(T13_COVER, **{job: {"job": job, "leg": None, "label": "ubuntu-24.04", "run": 7001, "event": "pull_request",
                                   "sha": "a" * 40, "tree": "b" * 40}})
    shorter = dict(left, jobs=[j for j in left["jobs"] if j != job])
rc, _ = t13_verdict(t13_needs(shorter, bad))
say(rc == 1, "T13 the verdict says no to a covered Linux leg or job (exit %d)" % rc)
rc, _ = t13_verdict(t13_needs(T13_FULL, T13_COVER))
say(rc == 1, "T13 the verdict says no to a leg both covered and run (exit %d)" % rc)

# The wiring.
tb = dict(re.findall(r"^  ([A-Za-z0-9_-]+):\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", wf.split("\njobs:\n", 1)[1], re.M | re.S))
pb = tb.get("plan", "")
say("      macos_covered: ${{ steps.plan.outputs.macos_covered }}\n" in pb, "T13 the plan job declares macos_covered")
TREE_NAME = "      - name: the tree under test is ${{ steps.tree.outputs.tree }}\n"
say("        id: tree\n" in pb and TREE_NAME in pb and pb.index("        id: tree\n") < pb.index(TREE_NAME) < pb.index("      - id: plan\n")
    and "test \"$(git rev-parse 'HEAD^{tree}')\" = \"${{ steps.tree.outputs.tree }}\"" in pb,
    "T13 the plan job names the tree it tests in a step's name, checked, before the plan")
say(wf.count("PLAN_TOKEN") == 1 and re.search(r"^      - id: plan\n        if: [^\n]*\n        env:\n(          .*\n|          #.*\n)*          PLAN_TOKEN: \$\{\{ github\.token \}\}\n", pb, re.M) is not None,
    "T13 the plan's step, and no other, is given the workflow's token")
head = wf.split("\njobs:\n", 1)[0]
say(re.search(r"^permissions:\n(  [a-z-]+: read\n)*  actions: read\n", head, re.M) is not None
    and re.search(r"^permissions:\n(  [a-z-]+: read\n)*  contents: read\n", head, re.M) is not None
    and not re.search(r"^    permissions:", pb, re.M),
    "T13 the workflow reads its runs (actions: read beside contents: read), and the plan job asks for no permission of its own")
named = []
for n, label in T13_MAC.items():
    if n in T13_WHOLE:
        b = tb.get(T13_IDS[n], "")
        named.append(("    runs-on: %s\n" % label) in b and (re.findall(r"^    name: (.*)$", b, re.M) or [T13_IDS[n]]) == [n])
    else:
        b = tb.get(n.split(" (", 1)[0], "")
        named.append("    runs-on: ${{ matrix.os }}\n" in b and not re.search(r"^    name: ", b, re.M))
say(named and all(named), "T13 the macOS jobs a trunk push looks for are named as this workflow names them: %s" % sorted(T13_MAC))

print("tiers-test: %s" % ("every check passes" if not fails else "%d check(s) FAILED" % fails))
sys.exit(1 if fails else 0)
