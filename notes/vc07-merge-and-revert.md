# vc07 — merge and revert (M3, not complete: the named boundaries)

_Materialised from the body of den#22 at the merge (`24ab92fa`)._


## Prediction

882e914 committed `notes/vc07-evidence/prediction.txt` before implementation. ORIG_HEAD ordering, squash without MERGE_HEAD, conflict stages and the need for REUC held. Retained counterexamples corrected nearby-conflict coalescing, full-ref message labels, no-commit REVERT_HEAD, direct revert publication, message cleanup and quiet diagnostics. Dirty true merges also create internal recovery objects and transient index metadata; they remain explicit prewrite refusals, not normalized parity.

## Forbidden

Git 2.56.0 documentation and the pinned binary only, plus den's own APIs. No Git/libgit2/other VCS implementation source, production subprocess dependency, pin/compiler/std change, host package installation, planning/memory/config edit, label, merge, tag, release or issue action. Builds and measurements used hasu block A under `/home/mfwolffe/lanes/hasu-A.lock`, taskset 0–5 inside a 12-GiB rootless container. Fresh vc07 clone; no other lane's directory moved, renamed or written. No Mac builds.

## Inputs verified

Base dd1533c. Wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4, bundled std 2386522e unchanged. Two fresh release/ref/tag reads agree; archive, staged compiler/runtime/std-tree, image and oracle digest reads are in `notes/vc07-evidence/pins/`. Oracle SHA256 remains c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60, built at `/work/den`.

Read the full contract, vc06 draft/note, campaign and RULES, vc05/vc04 notes, MAP/SOURCES and wolf guide. SOURCES records git-merge, merge-options/strategies, git-merge-base, git-revert, git-merge-file, git-read-tree, gitrepository-layout and gitformat-index by section. No new gitprotocol-* source.

- 049812c — command, base and marker tests before implementation.
- 6a831ae — bounded bases, text merge and REUC encoding.
- fba5617 — conflict resolution and abort worktree boundary.
- 4cab6db — measured coalescing and independent clients.
- 33b52b3 — merge/revert commands, resolved commit completion and complete-state tests.
- 240f2b6 — mandatory merge gate and main parity requirement.
- 28d762a — canonical client formatting.
- bea6bfb — measured message cleanup, empty-message failure and quiet diagnostics; final runtime/test change.
- a0a73f7, 3966d0f — README-only refresh/count update; 2f5db1c, edcfa0d — API/source record.
- 24ab92f — final captures, input proofs and derived counts; documentation/evidence only after bea6bfb.

## Evidence index

Full local `tools/gate` exited 0 on hasu, 2026-10-27 09:13:44–09:22:51 UTC, covering the final functional change bea6bfb. `final-gate.log` and `final-inputs.json` bind all 289 functional files before/after; all 289 hashes were independently verified again in the final Mac tree. The earlier pre-message green is retained separately and is not the final evidence. Static Linux builds repeated identically; stripped size 2,226,456 bytes, SHA256 42644bdc4bc54269c8560df42b57581936ca184899ce4ae687497591a79a2bdf.

Per native/release tier, derived from captures by `notes/vc07-evidence/counts.py`:
- 117 exact stdout/stderr/status and complete repository/worktree comparisons; 12 separately named not-yet captures, checked for immutable state.
- 1,521 exact generated three-way file merges through an independent importing package; 84 complete merge-base sets through a second independent package, including criss-cross graphs and immutable repositories.
- Three actual-checked `exit(0)` programs: mergebase, mergefile and mergeundo. Zero new skips.
- Main: 188 = 174 parity / 13 named not-yet / 1 shape / 0 failures. Existing history/refs/index/worktree/commit/codec/object/config/ignore/diff gates remain required.
- The inherited two hunk witnesses/eight contexts and 96 capture-bound binary representations remain non-parity, unchanged.

The matrix includes loose/packed refs, attached/detached and named unborn input, full names/lightweight tags/full and prefix OIDs, fast-forward/up-to-date, no-ff/squash/no-commit, regular-file conflicts in all three styles, stages, REUC resolution/deletion, resolved merge commit, abort, root/single revert, merge-mainline refusal, dirty/untracked safety and foreign index/HEAD/branch/ORIG_HEAD/AUTO_MERGE locks. No repository file is excluded; the inherited six-word per-file stat proof and validated raw-object/OID policy are unchanged.

Plant: local hasu `notes/vc07-evidence/plant-marker.log` records `wolf-trap: assert` at `src/mergefile_test.lu:25:5`, exit 134, for a six-character opening marker. Correct implementation was committed first. CI plant #21 at f49200a, run 40477015201, was queued at the one immediate read; the coordinator must verify the intended assertion, not infer it. No lane CI wait or label.

### Recommendations implemented

- R-vc07-1: refuse dirty/staged true-merge recovery before writes until its internal recovery objects and transient-stat lifecycle are implemented and proved. Retain the counterexamples; fast-forward dirty/untracked safety is implemented.
- R-vc07-2: keep the file API's measured Myers algorithm separate from ort's histogram policy. Tree merges refuse repeated base-line hashes and multiple edit hunks on either changed side rather than silently substitute algorithms. All best bases are returned; recursive virtual bases, rename topology, modify/delete/binary conflicts and nonregular trees stay named. Rename detection reuses the existing scorer.
- R-vc07-3: retain unborn merge, annotated-tag messages, explicit revert mainline selection, editor execution and sequencer operations as named boundaries. Do not claim M3 complete from the bounded green matrix.

### M3 / M2 checklist

- [x] Fast-forward/up-to-date; bounded regular-file three-way merge and merge/diff3/zdiff3 marker bytes.
- [x] Stage 1/2/3 writing, REUC generation before lifting add's higher-stage guard; resolved merge commit and measured abort.
- [x] No-ff, squash, no-commit, message/file inputs, root/single revert and merge-mainline refusal.
- [x] Owned object/walk/index/ref/worktree APIs, shared scorer, no index.write_tree history read, independent clients and checked units.
- [ ] Recursive/criss-cross virtual bases, rename conflict topology, histogram/multi-hunk/repeated-anchor cases, dirty true-merge recovery, nonregular/binary/modify-delete conflicts, unborn/annotated-tag merge and revert mainline selection remain named.
- [ ] M3 sequencer, blame, stash/notes and general revision grammar remain follow-ons.
- [ ] M2 combined merge show, actual editor invocation and named history presentation/selection limits remain open; hunk/binary exceptions are not parity.

### vc08 draft

Implement cherry-pick and linear rebase/--onto over the owned walk, mergetree plan, index transactions, refs and commit boundaries. Add a durable sequencer with exact continue/skip/abort state transitions; measure todo/head/onto/original-tip/stopped-commit metadata, author versus committer identity/date, reflog wording, empty picks, conflicts, dirty/untracked safety and lock failures against the pinned binary. Reuse the file engine and rename scorer; never index.write_tree as a history read. Preserve stages/REUC and distinguish already-published worktree/index/ref state from rollback. Before arbitrary replay claims, close the relevant dirty-recovery, histogram, recursive-base and rename limits above or retain explicit refusals. Include importing clients, bounded actual-checked units, named plants and the full inherited gauntlet. Preserve M2's open rows and all non-parity diff exceptions; general revision grammar stays vc10.

## Done-when

- [x] Prediction before implementation; clean-room source record and twice-verified inputs.
- [x] Native/release complete-state matrices, independent file/base clients and three actual-checked exits.
- [x] Local intended plant red; CI plant opened without a label and read once.
- [x] Full local gauntlet covering final functional inputs; repeated static builds.
- [x] README refresh, API/source documentation, named remaining M3/M2 rows and vc08 draft.
- [ ] Coordinator verifies final PR-tier green, labels the final head for the full matrix, and watches that run.
- [ ] Coordinator verifies/closes plant #21 unmerged and materialises this five-section body as the vc07 note.

No new upstream issue to file; none filed or closed. Keep hasu `/home/mfwolffe/lanes/vc07/den` and its captures for evidence review. The local plant worktree was removed cleanly. Both clean local vc07 worktrees have been removed individually without force. The hasu clone is clean at final head 24ab92fa9827a5f20808a4054e79b159b3db958f; all 289 functional hashes match again. No local or pool job remains running.
Final head: 24ab92fa9827a5f20808a4054e79b159b3db958f. Single immediate CI read: run [40481087116](https://github.com/wolffe-lang/den/actions/runs/40481087116), queued. No further lane polling, CI wait or label.

One audit invocation, exit 1. Literal last line: `AUDIT FAIL (footprint: cross-cutting)`. Only merge-gate conditions failed: head CI was in progress, no green tier yet, and the coordinator-owned full-matrix label absent. An informational warning notes the still-open plant #21; it must remain unmerged. Ancestry, attribution, footprint, all five sections, matching head, all 19 cited SHAs, untouched spec, removed worktree and orphan checks passed. The audit was not rerun.

