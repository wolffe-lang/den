# vc11 — Implement bounded blame attribution over shared revisions

_Materialised from the body of den#30 at the merge (`ce0ca742`)._


## Prediction

`35d4457` preceded implementation. Ordered parent transfers, root markers, original line numbers, rename filenames and whitespace-only matching needed separate boundaries. Retained counterexamples corrected ordinary final-LF identity and exact-whole-file second-parent priority. No oracle expectation was weakened.

## Forbidden

Git 2.56.0 documentation and the pinned executable only; no Git/libgit2/VCS/matcher implementation source read. No production subprocess or third-party dependency, pin/compiler/std change, package installation, planning/memory edit, label, merge, tag, release or issue action. Fresh hasu clone, block A under its per-run flock, taskset 0–5 inside a rootless 12-GiB container. No Mac builds, helper agents or other-lane edits.

## Inputs verified

Base `55887be`. Unchanged wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4 and bundled std 2386522e. Fresh twice-read release/ref/archive/staged identities are under `notes/vc11-evidence/pins/`. The lane built its own oracle through `tools/fetch-oracle` at `/work/den`; SHA256 c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60 was read twice and asserted before every observation.

- `35d4457` — prediction.
- `3cce7fe` — differential and independent importing contracts first.
- `ed9dad7` — pure bounded ranges and shared line correspondence.
- `119604c` — ordered-parent/rename attribution, separate presentation and CLI.
- `ee0358e` — mandatory native/release/checked gate and main parity ratchet.
- `b731be3` — README-only refresh.
- `6b4ed4d` — API map and clean-room references.
- `147278f` — pin identities, retained reds and final-gate verification helpers; full-gate functional head.
- `ce0ca74` — complete final captures, derived counts and independent spot-check; evidence-only final head.

Read the contract, RULES §§1–10, campaign, vc10/vc09/vc04 notes, MAP/SOURCES and targeted Wolf guidance. Primary pages: git-blame, Synopsis/Description/Options/Specifying Ranges/Porcelain Format/Incremental Output/Mapping Authors/Configuration; blame-options; line-range-format; config/blame. No new gitformat-* or gitprotocol-* parser.

## Evidence index

Exactly **one complete `tools/gate`, exit 0**, hasu, wrapper window **2026-10-28 01:36:16–01:56:16 UTC**, at functional head `147278f`. Literal completion line:

`VC11 FINAL EXIT 0 2026-10-28T01:56:16Z`

Log: `/home/mfwolffe/lanes/vc11/den/notes/vc11-evidence/final-gate.log` (retained as `notes/vc11-evidence/final-gate.log`). Both `/home/mfwolffe/lanes/vc11/final.exit` and `notes/vc11-evidence/gauntlet.exit` are 0. `final-inputs.json` binds **409 unchanged functional/toolchain/docs inputs**, with both path-set directions checked. Subsequent changes are evidence only; no second gauntlet. Final head: `ce0ca7420b1e9ff5bb51e0071510a8336e27d54f`. Independent final-tree verification confirms 338 tracked inputs plus 71 installed toolchain inputs = 409 unchanged.

Static Linux builds repeated identically: full binary **15,971,472 bytes**, SHA256 5a956bd4ba7c5a6c4a1f696a42b52d9ceb68a7981348599a9089d71dad9157fb; stripped **2,402,040 bytes**, SHA256 b1c4c7ca1e2bd3445f49ddf5975e25212ab984fff7abe69fd02220bcf621fc5c.

Per **native and release tier**, derived from retained complete captures:

| Blame proof | Loose | Packed |
|---|---:|---:|
| New raw-commit/merge/rename/generated histories | 241/241 | 241/241 |
| Ten original corpus fixtures used by vc09 | 50/50 | 50/50 |
| Independent importing client | 6/6 | 6/6 |
| Separately named non-parity scope rows | 10 | 10 |

Thus each tier has **582 exact command/state rows, 12 client rows and 20 separately named refusals**. Actual checked `src/blame_test.lu` reports **exit(0)** with **18 bounded checks**. No new skips. Every compared file, symlink target and directory mode remains in the immutable snapshots, including foreign index locks and dirty files.

| Inherited proof, per native/release tier | Loose | Packed | Separate named rows per mode |
|---|---:|---:|---:|
| Revision commands | 183/183 | 183/183 | 8 |
| Revision importing clients | 49/49 | 49/49 | 0 |
| History command/state | 576/576 | 576/576 | 7 |
| Refs/restore command/state | 632/632 | 632/632 | 17 |
| Merge/revert command/state | 132/132 | 132/132 | 12 |
| Replay scenarios | 96/96 | 96/96 | 20 |

Replay retains **157 process captures = 137 exact comparisons + 20 named refusals**, per mode/tier. Pack reading remains **2,442/2,442 raw objects across 34 fixtures**, all six entry types including **33 OFS and 33 REF entries**; independent structural/corruption/limit inputs **141/141**. Required importing clients retain history's **3**, refs' **14** (including 1,002-ref enumeration), merge-file's **1,521** exact inputs, merge-base's **84** complete sets, and replay's **136** checks. The bounded blame, revision, pack, pretty, walk, refs, reflog and sequencer programs report actual checked exit(0); inherited checked gates also pass, with their pre-existing budget/platform boundaries unchanged.

Other inherited counts, per native/release tier: scorer **1,510 + 24** collision pairs; pairing **267**; status/commit consumers **1,044**; basic diff **336**; endpoint/pathspec/width **575**; refresh **66**; diff API **12**; terminal widths **90**. Hunk bytes remain **676/684** with **8** named differences; binary bodies **154/250** with **96** capture-bound representation differences and **250/250** forward/reverse application witnesses. These are not relabelled parity. Index integration is **212** commands with **36** proved stat rows; ignore **840/840**; worktree **207/207**; commit-format API **150/150**, commit CLI **51/51**, ref/failure cases **35**. Object API records are **14** with **22** malformed inputs and **19** initial OIDs. Codec coverage is **52** vectors/**2,272** cross-codec calls, **1,099** loose objects + **31** packed entries = **1,130** interoperable rewrites, **32** corruption refusals, **1** empty corpus, and **250** fuzz rounds/**1,250** calls per tier. The **16**-repository corpus is rebuilt twice with identical object inventories. Main **190 = 179 parity / 10 named not-yet / 1 shape**.

`final-counts.py` derives `final-counts.json` and raw SHA256 bindings. Compressed complete blame/revision/history/refs/merge/replay/pack captures are retained under `notes/vc11-evidence/`; `additional-captures.json` indexes **97** final component JSON captures and **570** complete process/state captures for all **190** main cases. The full log also retains parser/config/filesystem/race/TLS and static checks. Independent manual spot-check `spot-check.py` verifies all four raw-path client captures, raw content bytes and filename quoting against the bound outputs, and recomputes blob SHA-1 **3bd625fa893ab451ef75e12a230da3909ab8a4c9**.

`initial-observations.json` is oracle-only exploratory measurement, **not differential parity**. `initial-red.log` and `merge-edge-red.log` preserve corrected counterexamples. Component/preflight logs are explicitly not substitutes for the final gauntlet.

Plant draft **#29**, head `a312e26`, run **40615116826**. Intended failure: `vc11 gate: exact unchanged line correspondence` followed by false `map.len == 999` at `src/blame_test.lu`. Correct implementation committed first. Sole immediate lane CI read: in_progress. Coordinator verifies intended-red output and closes unmerged; no lane CI wait or label.

### Recommendations implemented

- **R-vc11-1:** owned bounded attribution, 10,000 work items, 128-MiB commit/blob/rename/position payload, 16-MiB bodies and 200,000 lines; inherited 2,000-change diff bound. Numeric ranges: 256 operands/4,096 bytes. Renderer: 128 MiB, per-line reclaimed scratch; shared correspondence reclaims each search. Payload/work bounds, not peak RSS or streaming.
- **R-vc11-2:** conservative named refusals for changed repeated/hash-colliding lines, reordered common lines, multiple origin paths per commit and unsupported metadata/configuration. Whole-file-identical parents win before ordered partial transfers. Reuse the existing rename pairer for whole-file history; all -M/-C line-move/copy levels refuse separately.
- **R-vc11-3:** implement porcelain and line-porcelain for importing consumers now, preserving raw identity/content bytes. Argv remains UTF-8-limited; raw non-UTF-8 tree paths work through the public API.

### Blame rows

- [x] Shared revision evaluator and packed/raw object/path boundaries; attribution separate from numeric syntax/rendering.
- [x] Default columns, boundary/root and long IDs, show-name/number/email/suppressed metadata.
- [x] Numeric/omitted/reversed/signed-offset -L unions; regex/function ranges refuse by name.
- [x] -w changes comparisons only; raw bytes and final source-line rendering retained.
- [x] Ordered merge parents, explicit first-parent and exact-whole-file parent priority.
- [x] Whole-file exact/edited renames through the shared pairer; -M/-C heuristics named refusals.
- [x] Porcelain/line-porcelain; immutable loose/packed matrices; independent raw-path/ownership/limit/malformed-result clients.
- [ ] Uncommitted/alternate contents, reverse blame, ignored revisions, unsupported topologies/configuration/display widths remain named refusals.
- [ ] Stash/notes, full merge/replay, M2 editor/combined-show/history limits and pack writing remain open. No M3-complete claim.

### vc12 draft

Implement the remaining M3 stash/notes surface from git-stash and git-notes documentation and the same pinned oracle. Keep stash snapshot construction/publication separate from apply/pop/drop recovery; preserve index/worktree/untracked distinctions, ordered parent shape and durable ref/reflog state. Reuse revision resolution, raw object/tree writers, index transactions, worktree transitions and the existing merge engine; never fork the matcher or approximate unsupported merge/rename topologies. Stage measured ordinary push/list/show/apply/pop/drop and explicit notes add/show/list/remove with message-supplied inputs, naming editor, path-limiting, untracked/ignored and conflicting recovery forms not yet implemented. Differentially compare every intermediate process and complete file/mode state over immutable loose/packed fixtures, with independent importing clients, bounded actual-checked units and mandatory gates/plants. Keep pack writing, transports, editor execution and all inherited merge/replay/blame boundaries separate. Draft contract, not an M3-complete claim.

## Done-when

- [x] Prediction, clean-room references and twice-read pins.
- [x] Native/release exact loose/packed proof and actual checked exit.
- [x] Main blame parity ratchet, README-only refresh, API/source documentation and vc12 draft.
- [x] Named plant opened as draft; sole immediate CI read recorded, no wait/label.
- [x] Sole full inherited gauntlet green, repeat static build and 409 unchanged inputs; final counts named.
- [x] Final captures committed, final head pushed, this five-section body finalized as PR body.
- [x] Read final PR CI run once immediately; remove clean Mac worktree; canonical audit exactly once, exact last line recorded.
- [ ] Coordinator verifies plant red and final PR-tier green, applies full-matrix at the final head and watches the full tier.
- [ ] Coordinator materialises this body as `notes/vc11-blame.md` on trunk.

No issues filed or closed. Preserve `/home/mfwolffe/lanes/vc11/den` and evidence. No compute job remains running; both recorded PIDs exited and a nonblocking lock check confirmed block A free, acquiring and releasing it immediately.

### Final-head handoff

PR **#30**, final head **ce0ca7420b1e9ff5bb51e0071510a8336e27d54f**. Sole immediate final-head CI read: **40619796004**, in_progress; no lane wait or label.

One canonical `bash wolf/tools/lane-audit.sh den vc11 30` invocation from `/Users/mfwolffe/GithubOrgs/wolffe-lang`, exit 1. Exact last line: **`AUDIT FAIL (footprint: cross-cutting)`**. Only coordinator-owned merge-gate conditions fail: head CI in progress, no completed green tier, full-matrix label absent. Fast-forward ancestry, no attribution, Footprint, matching head, all five sections, untouched spec, all fourteen cited SHAs, removed worktrees and orphan checks pass. Audit not rerun. Raw audit record: `/Users/mfwolffe/lanes/vc11/vc11-audit.log`; finalized five-section body: `/Users/mfwolffe/lanes/vc11/pr-body.txt`. Both clean Mac worktrees were removed individually without force; no vc11 compute process remains.

