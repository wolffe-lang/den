# vc06 — refs and branches: bounded refs and branch transitions

_Materialised from the body of den#20 at the merge (`83599600`)._


## Prediction

`c893dd0` committed `notes/vc06-evidence/prediction.txt` before implementation. Loose refs override packed refs; peeled tag metadata is not the tag OID; tag objects and lightweight refs differ; soft reset preserves index/worktree; hard reset can publish those before a ref-lock failure. Those predictions held. The lower bound of 150 differential rows became 434 per native tier.

Corrections retained as witnesses: default branch creation says `Created from main`, not an implicit `HEAD`; current-branch rename writes old-to-zero and zero-to-old HEAD records; same-OID detached reset omits the reflog update; tag reflogs use the first physical subject line and UTC committer date; verbatim tag `-m` does not acquire commit's final LF. No oracle expectation was changed to accept differing output.

## Forbidden

Git documentation and the pinned binary only; no Git/libgit2/other VCS implementation file opened. No production subprocess dependency, compiler/std/pin change, package installation on a host, planning/memory/config edit, label, merge, release or issue action. Builds and oracle measurements ran on hasu block A under `/home/mfwolffe/lanes/hasu-A.lock`, taskset CPUs 0–5 inside rootless containers, 12 GiB. No Mac builds or oracle runs. No other lane's files were moved, renamed, deleted or written. The initial bundle was only read from vc05; vc06 has its own fresh clone and newly fetched release archives.

## Inputs verified

Base den `3b767c1`. Wolf 0.2.35 `cf0c13d3`, lupin 0.1.56 tag `28547b4`, bundled std `2386522e`, unchanged. Two release/ref/annotated-tag reads agree; archive digests and two staged compiler/runtime/std reads are in `notes/vc06-evidence/pins/`.

The identical oracle image ID is `f59d9fe871ff769948fb33a83d9eb8e16bea271b17a6c2a10f50043a314d928e`, read twice. Building at `/work` produced the wrong oracle digest; the unchanged Containerfile at CI's `/work/den` reproduced the required Git 2.56.0 SHA-256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`, verified again independently. Both logs remain; no pin was changed. The build path, not a different image, was the changed input in this experiment.

- `3b06491` — bounded loose/packed refs and owned clients/units.
- `f8e3112` — first measured branch commands and differential harness.
- `6a6cf62` — HEAD/rename/cleanup transactions and bounded enumeration.
- `c28dabd` — tags, checkout/reset, detached commits and complete-state tests.
- `202905a` — mandatory refs gate and main-matrix promotion.
- `9c50f78` — correct the planner's hardcoded branch-refusal witness to rebase; this CI edit makes the footprint cross-cutting.
- `4ebe12f` — active-operation guards, forced-branch reset reflogs, scope and limit checks; final runtime head.
- `4a7a2ec` — divergent `-d` refusal and `-D` force cases, loose and packed; final functional test head.
- `eb3ea02`, `7f947b2` — README-only refresh and final coverage count.
- `c36cc6b`, `c8625d8` — API map and source citations.

Read vc05's note whole, den#1/#11 bodies, MAP/SOURCES, campaign/surface census, RULES and the wolf guide. SOURCES records gitrepository-layout, check-ref-format, pack-refs, update-ref, symbolic-ref, branch, tag, switch, checkout, reset and reflog by section. No new gitformat-* or gitprotocol-* source was introduced; inherited object/index citations remain in force.

## Evidence index

Final head: `83599600e9a18bf6be81883d551d60bc07868a3f`. Full local `tools/gate` passed on hasu; `notes/vc06-evidence/final-gate.log` and `final-inputs.json` bind all 269 functional files before and after the run. Only documentation/evidence changed after the functional head. `counts.py` derives `final-counts.json` from captures, not manually entered totals.

- Refs: **434/434 exact stdout/stderr/status and repository/worktree state per native/release tier**, **14 independent-client checks per tier**, two actual-checked `exit(0)` programs, eight separately captured named unsupported rows, zero new skips.
- Main: **188 = 173 parity / 14 named not-yet / 1 shape / 0 failures**. Branch/tag/switch now require parity. General reset ancestry remains a named refusal.
- Full inherited history, codec, objects/races, config, index, ignore, worktree, commit, similarity and diff gates passed. The two hunk witnesses/eight contexts and 96 capture-bound binary representations remain separately counted, not new parity claims.
- Static Linux binary built twice with identical bytes; stripped size **2,136,536 bytes**, SHA-256 `03150adcfb9cd472492497e3ff432f7dfb9eb224193a71e2f64856b8ae833972`.
- Independent client: direct packed/tag OIDs, 1,002-ref listing and explicit 4,097-entry limit, successful CAS/create/delete comparisons, stale-CAS and foreign-ref/packed-lock immutability. Checked units exercise name/packed/peeled validation and exact reflog framing.
- Matrix: attached/detached/unborn, loose/packed, branch safety/rename/force, lightweight/annotated/nested tags and reflogs, switch/checkout, soft/mixed/hard reset, dirty/staged files, same-OID updates, foreign locks and in-progress operations. Six inode/time index words use the inherited per-file proof; loose objects use the existing validated raw-bytes/OID policy rather than compressed-stream identity. No index or repository file is excluded.
- Early detached harness red was unequal fixture preparation: Git checkout refreshed two different ctime values. The fix copies one prepared fixture to both tools. Original captures remain in `branch-initial-red.json`; no expected bytes were normalized to hide it.
- `locks-initial-red.json`, `branch-rename-red.json`, `transition-initial-red.json`, `tag-message-red.json`, `force-create-red.json` and oracle-only measurements retain the counterexamples that drove corrections.

Plant: local `tools/check-refs` was seen red for TAB-to-space reflog corruption: `wolf-trap: assert` at `src/reflog_test.lu:9:5`, exit 134, `notes/vc06-evidence/plant-reflog.log` on hasu. Correct code was committed first. CI plant den#19, head `05ee334`, run **40450512817**, was queued at the single immediate read; the coordinator owns verification of the intended CI assertion. No CI wait or label by this lane. The clean Mac plant worktree was removed without force.

### Recommendations implemented

- **R-vc06-1:** retain a bounded revision adapter: HEAD, full refs, unambiguous short branch/tag names, full OIDs and unambiguous loose prefixes. Do not claim ranges/ancestry/reflog selectors/previous-checkout grammar; reject ambiguous short names rather than guess.
- **R-vc06-2:** carry only proven packed-ref peeling traits and expose ordered, non-atomic multi-file publication. Do not advertise `fully-peeled` merely because a record lacks a peeled line, or promise rollback of already-published index/worktree changes.
- **R-vc06-3:** retain unmerged/flagged-index, tracking, orphan, list-pattern and editor boundaries until their own measured consumers exist. Protect in-progress operations instead of erasing their state. Keep the oracle build at CI's pinned mount path.

### M3 and M2 rows

- [x] Bounded refs/HEAD attached and detached, loose/packed/peeled data, exact command reflogs and CAS/exclusive locks.
- [x] Branch list/create/force/delete/rename; lightweight/annotated tags; branch switch/checkout; reset soft/mixed/hard, with measured failure side effects.
- [x] Independent importing client, bounded actual-checked programs, source manifest, full local gate, README/MAP/SOURCES.
- [ ] Merge/revert, cherry-pick/rebase, blame, stash/notes and general revision grammar remain subsequent M3 work. M3 is not complete.
- [x] Small M2 limit closed: detached commit publication and summaries, including same-OID amend behavior.
- [ ] M2 combined merge show, actual editor execution and named history selection/presentation limits remain open. Existing hunk/binary exceptions remain unchanged. M2 is not complete.

### vc07 draft

Implement merge/revert using the owned object/walk, index, refs and worktree boundaries above. Start with fast-forward and already-up-to-date cases, then merge bases, three-way regular-file merge, exact conflict markers, `--no-ff` and `--squash`. Supply stage 1/2/3 and REUC generation before lifting the current higher-stage mutation refusal. Reuse the existing rename/diff scorer; never call `index.write_tree` as a history read.

Measure MERGE_HEAD/MERGE_MSG/MERGE_MODE/ORIG_HEAD/AUTO_MERGE, reflog wording, lock order, failure/abort side effects and dirty/untracked safety against the pinned oracle. Carry packed refs, detached/unborn inputs and the existing stat proof through the matrix. Keep conflict/rename/merge-base limits named rather than approximate. Add independent clients, bounded actual-checked merge units, plants and the full gauntlet. Preserve M2's open combined-show/editor/history rows and the hunk/binary exception counts; draft vc08's sequencer handoff.

## Done-when

- [x] Prediction, clean-room references and twice-verified inputs.
- [x] Native/release exact matrices, independent clients, actual checked units and named scope rows.
- [x] Local intended plant red; CI plant open for coordinator verification.
- [x] Complete local gauntlet at unchanged functional inputs; static build repeats.
- [x] README-only refresh, API/source docs and vc07 draft.
- [ ] Coordinator verifies final PR-tier green, applies full-matrix at the final head, and watches its full run; no lane label/wait/merge.
- [ ] Coordinator materialises this five-section body as `notes/vc06-refs-and-branches.md`.

Final PR run and one audit invocation are recorded below at handoff. No issues were filed or closed; the remaining den surfaces above are follow-ons, not new compiler/std gaps. Preserve `/home/mfwolffe/lanes/vc06/den` until evidence review; vc06 owns that clone, its target files and its oracle-image alias. Never prune hasu-env or another lane. The complete local job has ended.

### Final-head handoff

PR #20, head `83599600e9a18bf6be81883d551d60bc07868a3f`. Single immediate CI read: run [40456183422](https://github.com/wolffe-lang/den/actions/runs/40456183422), queued. No further lane polling or CI wait.

One audit invocation from the org directory, exit 1. Literal last line:

`AUDIT FAIL (footprint: cross-cutting)`

Only merge-gate state failed: head CI is still in progress, no green tier is available yet, and the coordinator-owned full-matrix label is absent. Fast-forward ancestry, attribution, footprint, five report sections, plant artifact, head identity, spec scope, all 18 cited SHAs and orphan checks passed. The audit's default `/private/tmp/vc06` is absent; the actual clean Mac worktree `/Users/mfwolffe/lanes/vc06/den` is retained for review, as is the clean hasu clone at the same final head. The audit was not rerun.

