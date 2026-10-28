# vc12 — M3 stash and notes over the shared layers

## Prediction

`bcd225b` (`notes/vc12-prediction.txt`) preceded every change and every stash/notes oracle measurement. Hits: S1 (W over [H, I], `index on`/`WIP on`/`On <branch>:` messages), S4, S5 (a foreign `refs/stash.lock` fails after the objects exist with `Cannot save the current status`), S6, S8, S9, S10 (`log for 'stash' only has N entries` from the shared evaluator), N1–N3, N6 (notes in default `log`/`show` only) and N7. Misses, each corrected from retained oracle captures, never by editing an expectation:

- S2: push publishes through a hard reset — it writes ORIG_HEAD and appends HEAD's `reset: moving to HEAD` (attached; a detached same-OID update logs nothing).
- S3 ordering: the index is refreshed and written **before** the unborn, no-change and lock checks.
- S1 refinement: W carries no final LF (I does), and W records the worktree of every path the index **or HEAD** tracks (vc09's `m2-edited-rename` corpus fixture).
- S7: apply merges against the current index tree (staged state takes part), leaves changed paths as zero-stat tree entries and writes AUTO_MERGE; `apply --index` also appends HEAD's reset record (measured, then refused by name).
- S9 additions: a bare `N` evaluates as `refs/stash@{N}`; a drop that keeps the ref's value still writes a loose `refs/stash`; drop takes the reflog lock first.
- S11: dirty overlap and untracked collisions are measured rows (git's own error, status on stdout, exit 128), not refusals.
- N4: `remove` echoes the operand spelling; one missing object without `--ignore-missing` commits nothing; its resolution failure is `error: Failed to resolve …`, exit 1.
- N5: the fan-out threshold is not 256. Five independent thresholds (61, 66, 71, 77, 78 notes) are predicted exactly by: flat until each of the sixteen first-hex-digit groups holds two notes (R-vc12-2).

## What was built

### Forbidden

Git v2.56.0 documentation and the pinned executable only; no Git, libgit2 or other VCS implementation source read. No production subprocess or third-party dependency, no pin/compiler/std change, no package installation, planning/memory edit, label, merge, tag, release or issue action. Fresh hasu clone `/home/mfwolffe/lanes/vc12/den` on `vc12` from `452227e`, block A under `/home/mfwolffe/lanes/hasu-block-A.lock` taken per run, taskset 0–5 inside a rootless 12-GiB container (`localhost/den-vc06-oracle:latest`, vc11's recipe). Mac worktree for git only; no Mac builds; `/home/mfwolffe/lanes/vc11/den` and `/home/mfwolffe/lanes/vc10/den` untouched.

### Inputs verified

Clean room: Git v2.56.0 `git-stash.adoc`, `git-notes.adoc`, `config/stash.adoc`, `config/notes.adoc` and `pretty-options.adoc` (sections in `docs/SOURCES.md`), and the pinned oracle built by `tools/fetch-oracle` at `/work/den`, SHA256 c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60 read twice (`notes/vc12-evidence/pins/`) and asserted by every harness. No Git/libgit2/VCS source read; no gitformat-*/gitprotocol-* parser added. Wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4, std 2386522e unchanged; release/tag/archive/staged reads twice, fresh.

- `bcd225b` — prediction.
- `a9a2d04` — oracle-only exploratory measurement (`initial-`/`round-two-observations.json`, not parity).
- `449a02a` — the differential contract before the implementation it judges.
- `0277226` — notes add/show/list/remove/get-ref over `refs/notes/commits`.
- `dabc072` — stash construction (objects only), publication (`refs/stash` + always-written reflog) and recovery (apply/pop/drop/clear).
- `4a2fb18` — packed `refs/stash`: a kept value is written loose.
- `a3dbc2d`, `fb345ef`, `3d5aefd` — notes in history output: rows first, then the default-format display.
- `18fd63a` — pure `stashlog` and `notestree` layers; `95f8040` — bounded units for the checked machine.
- `2ec2d78` — independent importing client `probes/stash-client` and driver.
- `eba021d` — `tools/check-stash` mandatory in `tools/gate`; strict witness moved to `fsck`; planner test updated.
- `f3d0296` — main `stash`/`notes` rows require parity.
- `ed374cd`, `0c854fb` — lock failure phases: rows, then the reflog-lock-first drop and measured diagnostics.
- `a22aafa` — README-only refresh; `6b72e12`, `2d0a222` — MAP and SOURCES.
- `6c4fda2`, `0caccb7` — pins, local plant witness, final-gate binder/counter/runner; functional head.
- `ba23704` — final captures, derived counts, deduplication record and spot-check; evidence only.
- this note — the five sections, materialised in the tree; evidence-only final head.

Layers: `stash.construct` (I/W objects only) is separate from `stash.publish` (ref + reflog) and from `stash.apply`/`records`/`drop`/`clear` (recovery). A revision operand goes through `revsyntax`/`revision`, never a second parser. W's and the notes trees go through the raw tree builder; the reset through `worktree.transition`; apply through vc07's `mergetree.plan` (never forked) and `worktree.merge_check`; the index through `index.begin`/`commit`. History shares `notes.read`/`display`.

### Recommendations implemented

- **R-vc12-1:** apply/pop merge W into the current index tree through the existing plan (labels `Updated upstream`/`Stash base`/`Stashed changes`); content conflicts, untracked-snapshot entries, `--index`, `-u`/`-a`, `-p`, `--staged`, path-limited push and the other subcommands stay named refusals before any write; dirty overlap and untracked collisions are measured rows.
- **R-vc12-2:** notes are read in any permitted fan-out; writes use the measured rule (flat until all sixteen first-hex-digit groups hold two notes, then two-hex directories); a directory over sixteen notes refuses rather than extrapolate a deeper level.
- **R-vc12-3:** history displays the default ref's notes in the default format, replacing the blanket `history notes` refusal (its loose-directory test missed a packed-only notes ref); other refs, other formats and patch-with-stat refuse by name.
- **R-vc12-4:** dirty recovery rows write their dirty bytes in the setup, identical in both copies; a tool-side stale stat word after its own step is unprovable by the inherited six-word proof (vc08's boundary), and the proof is not weakened.
- **R-vc12-5:** the main `stash` row uses the inherited `index-stat-proven` comparison, as every index-writing main row does.

### Stash and notes rows

- [x] push/bare/save, `-m`/`--message`, `-q`, `--keep-index`; refresh-write first; ORIG_HEAD and HEAD's reset record; lock and unborn failures.
- [x] list, show (diffstat default, diff options passed through), `stash@{N}`/`N` through the shared evaluator.
- [x] apply/pop over the index tree, AUTO_MERGE, zero-stat restoration, measured dirty/untracked errors; drop/clear with the reflog rewrite, packed refs and lock phases.
- [x] notes add (`-m`, `-f`, `--allow-empty`), show, list, remove (`--ignore-missing`), get-ref; any fan-out read, measured fan-out written; default-format history display.
- [ ] Named: `-u`/`-a`, `-p`, `--staged`, pathspec push, `--index`, conflicting apply, branch/create/store/export/import, list log options, `show -u`, `stash.*` config; notes append/copy/edit/merge/prune, `-F`/`-C`/`-c`/`-e`, editor, `--ref`, `GIT_NOTES_REF`, `core.notesRef`, `notes.displayRef`, `--stdin`.
- [ ] M3 is not complete: inherited merge/replay (recursive bases, rename topology, dirty true-merge recovery), editor execution and M2 display limits stand; pack writing and transports stay separate.

## Evidence index

Exactly **one complete `tools/gate`, exit 0**, hasu block A, wrapper window **2026-10-28 04:27:22–04:50:23 UTC**, at functional head `0caccb7`. Literal completion line:

`VC12 FINAL EXIT 0 2026-10-28T04:50:23Z`

Log: `notes/vc12-evidence/final-gate.log` (`VC12 GAUNTLET EXIT 0`); `final.exit` and `gauntlet.exit` are 0. `final-inputs.json` binds **428 unchanged functional/toolchain/docs inputs**, both path-set directions checked (`VC12 FUNCTIONAL INPUTS UNCHANGED 428`). Everything after `0caccb7` is under `notes/`; no second gauntlet. Static Linux builds repeated identically: full **16,049,808 bytes**, SHA256 455292422d0bbcfa659fbee9b6b1343e419f227f59824df3af99261bbffddc42; stripped **2,478,328 bytes**, SHA256 8d50a7c57facc3736cf37195ddb239564f447421316a1585212d3aa12d402924.

Per **native and release tier**, derived by `final-counts.py` from retained complete captures:

| Stash and notes proof | Loose | Packed |
|---|---:|---:|
| Complete-state cases (61 stash, 22 notes, 20 vc09-corpus, 1 subcommand diagnostic) | 104/104 | 104/104 |
| Exact intermediate process comparisons (stdout, stderr, status, every file and mode) | 395/395 | 395/395 |
| Named refusals, each byte-immutable (44 process captures) | 39 | 39 |
| Independent importing client | 19/19 | 19/19 |

The corpus rows are ten vc09 fixtures × (stash push/list/show/show -p/pop/list, notes add/list/show/remove/list). The bounded `src/stash_test.lu` reports **20 checks** natively on both tiers and actual checked **`exit(0)`** (`stash-checked.json`). Zero new skips. Main **190 = 181 parity / 8 named not-yet / 1 shape** (vc11: 179/10/1); the strict witness now rejects `fsck` as intended.

| Inherited proof, per native/release tier | Loose | Packed | Named per mode |
|---|---:|---:|---:|
| Blame commands (241 new + 50 corpus) | 291/291 | 291/291 | 10 |
| Blame clients | 6/6 | 6/6 | 0 |
| Revision commands / clients | 183 / 49 | 183 / 49 | 8 |
| History command/state | 576/576 | 576/576 | 7 |
| Refs/restore command/state | 632/632 | 632/632 | 17 |
| Merge/revert command/state | 132/132 | 132/132 | 12 |
| Replay scenarios (157 captures = 137 exact + 20 named) | 96/96 | 96/96 | 20 |

Pack reading **2,442/2,442** raw objects across **34** fixtures, entry types including **33 OFS and 33 REF**; structural/corruption/limit inputs **141/141**. Other gates read from the same log, per tier: scorer **1,510 + 24**; pairing **267** and **1,044** consumer comparisons; basic diff **336/336**; endpoints **575/575**; terminal widths **90/90**; diff API **12**; hunks **676/684** with **8** named differences; binary bodies **154/250** with **250/250** forward/reverse application; index integration **212** commands with **36** proven stat rows; ignore **840/840**; worktree **207/207**; commit-format **150/150**; commit CLI **51/51**; sequencer API **136/136**; refs client **14** checks with 1,002-ref enumeration; the **16**-repository corpus rebuilt twice with identical OIDs. These are not relabelled parity. The checked units `stash`, `blame`, `revision`, `pack`, `pretty`, `walk`, `refs`, `reflog` and `sequencer` all report `exit(0)`.

`retain-components.py` retained **103** component JSON captures and **570** complete process/state captures for all **190** main cases (`additional-captures.json`, `main-captures.tar.gz`). `dedupe-captures.py` removed two byte-identical stash duplicates (hashes verified, `deduplicated-captures.json`) and the stale pre-gauntlet `target/stash-measure.json` capture. Independent manual spot-check (`spot-check.py`, `spot-check.log`): from the retained main `stash` capture, W `c09bed5530316b309149e56593dc18e05254cf40` (parents a6e91b14…, 073a4316…) has its SHA-1 recomputed from stored bytes and is identical in git and den, with the exact `On main: scratch` message, I's trailing LF and the reflog record.

`initial-observations.json` and `round-two-observations.json` are oracle-only exploratory measurements, **not parity**.

Plant draft **#31**, head `ed45513`, run **40631677452**. Intended failure: `tools/check-stash`'s native unit, `wolf-trap: assert` at `src/stash_test.lu:114:5` (`(notestree.fanout(fanned) else -1) == 1`), after `notestree.fanout` was changed to require three notes per group. Correct implementation committed first (`2d0a222`). Local witness `plant-local.log`: same assertion at `target/plant-src/stash_test.lu:114:5`, exit 134. The single immediate lane CI read saw it queued.

### Done-when

- [x] Prediction before the first change; clean-room references; pins and the oracle digest read twice.
- [x] Native/release exact loose/packed stash and notes matrices, vc09 corpus rows, independent client, actual checked exit.
- [x] Main parity ratchet for `stash`/`notes`; history notes display; README-only refresh; MAP/SOURCES.
- [x] Plant draft #31 opened red-by-name after the correct implementation; its run read once (queued); local witness retained.
- [x] Sole full inherited gauntlet green; 428 unchanged inputs; repeated identical static builds; every count above derived from captures.
- [x] Final captures, spot-check and this note committed; the five sections are the PR body with a `Footprint:` line.
- [x] Final PR run read once; clean Mac worktree removed; canonical audit run once (its last line is in the hand-back).
- [ ] Coordinator verifies plant #31's intended red and closes it unmerged, checks the final PR-tier green, applies `full-matrix` at the final head and watches the full tier.

No issues filed or closed. `/home/mfwolffe/lanes/vc12/den` and its evidence are preserved; no vc12 compute job remains and block A is not held. `/home/mfwolffe/lanes/vc11/den` and `/home/mfwolffe/lanes/vc10/den` were only read.

## Corrections

- The first differential run was **80/92 loose cases, 34/34 named, 12 failures**. Each failure was corrected against the oracle, never by editing an expectation: (1) the index is refreshed and written before the unborn and lock checks (`push-unborn`, `push-stash-lock`); (2) apply merges against the index tree, not HEAD (`push-keep-index-short`'s pop); (3) an explicit operand bypasses `No stash entries found.` (`apply-not-stash`); (4) notes `remove` resolution errors are `error: Failed to resolve …`, exit 1, and a missing object commits nothing (`notes-errors`, `notes-remove-mixed`); (5) the notes lock text begins `update_ref failed for ref …` (`notes-lock`); (6) W records HEAD-tracked paths the index dropped (`corpus-stash-m2-edited-rename`).
- Harness corrections in the same pass: both tools now run at one path, so absolute-path diagnostics compare (as `replay-test.py` does); dirty-recovery rows write their dirty bytes in setup (R-vc12-4), because a tool-side stale stat word is unprovable by the inherited six-word proof; the fanned fixture is built by the measured rule (90 fixed notes did not fan out); `stash create` on a clean tree exits 1.
- These pre-commit mismatch logs were overwritten by later runs and **are not retained**; the cases that exposed them are named above and remain in the matrix.
- Retained in history: packed mode showed git writes a loose `refs/stash` on a kept-value drop (`4a2fb18`); the main `stash` row needed the inherited `index-stat-proven` comparison (`f3d0296`); new lock rows (`ed374cd`) exposed a real defect: drop moved `refs/stash` before discovering a foreign `logs/refs/stash.lock`, leaving the ref and reflog inconsistent. `0c854fb` takes the reflog lock first, so any lock failure changes nothing, and reports the measured diagnostics.
- Prediction misses are listed in the Prediction section (S1 refinement, S2, S3 ordering, S7, S9 additions, S11, N4, N5).
- `retain-components.py` swept every `target/*.json`, including one stale pre-gauntlet measure file, and duplicated the stash captures; the deduplication is recorded rather than the generated index edited.
- `final-counts.py` splits the 104 cases into stash/notes/corpus by case-name prefix; the totals are the authoritative counts.

## vc13 draft

Implement M4 pack writing over vc09's reader: pack v2 and idx v2 written from den's own objects (undeltified first, then OFS/REF deltas from the shared delta encoder), installed atomically beside loose objects and read back through the existing transparent store, with `count-objects -v` and `verify-pack` from their documentation pages and pinned observations, and `fsck --full` checks over the main matrix's `fsck`/`count-objects` rows. Under R4c, pack bytes are not a target: the pinned Git must read every pack, `fsck` must be clean and sizes stay within 1.5× of Git's for the corpus, measured and recorded. Keep `gc`/`repack` publication separate from pack construction; refuse multi-pack-index, bitmaps, cruft packs, `.keep` policy and thin packs by name. Differentially compare every process and complete file/mode state over immutable loose/packed fixtures, with independent importing clients, bounded actual-checked units, plants and the full inherited gauntlet (stash/notes, blame, revision, history, refs, merge, replay unchanged or better). The stash/notes follow-ons stay named for a later lane: `-u`/`-a` snapshots and their apply, `--index`, conflicting apply into stages, path-limited push, `store`/`create`/`branch`, notes `append`/`copy`/`--ref`/`merge`. Draft contract, not an M3- or M4-complete claim.
