# vc08 — cherry-pick, rebase and the sequencer

_Materialised from the body of den#24 at the merge (`c18063b0`)._

## Prediction

061f960 committed the prediction before implementation. Source-author/current-committer separation, distinct empty/redundant picks, durable progress and publication before later ref failure held. Retained counterexamples corrected direct-path COMMIT_EDITMSG, early index refresh, hard versus merge-style recovery, and failure cleanup/diagnostic order. No Git expectation was edited to accept a differing byte result.

## Forbidden

Git 2.56.0 documentation and the pinned executable only; no Git/libgit2/other VCS implementation source opened. No production subprocess dependency, compiler/std/pin change, host package installation, planning/memory edit, label, merge, tag, release or issue action. Hasu block A, taskset 0–5 inside the pinned rootless container, 12 GiB and `/home/mfwolffe/lanes/hasu-block-A.lock`. Fresh vc08 clone; no other lane directory changed. No Mac builds.

## Inputs verified

Base aef24f2. Wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4, bundled std 2386522e unchanged. Two release/ref/annotated-tag reads, archive hashes, staged compiler/runtime/std-tree and oracle reads are in `notes/vc08-evidence/pins/`. Oracle SHA256 remains c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60.

- 31ec14e, ede0283 — independent command/state and pure sequencer tests first.
- d319625 — owned bounded records and empty policy.
- e4e5425 — shared replay, durable progress and commit integration.
- 9b1e5ee, 935bb56, 67e9be7 — measured message, recovery and lock-failure corrections.
- 44d3f40, b647881 — bounded scratch and conservative upstream-equivalence refusal.
- cb480fe — changed/foreign state guards and scope witnesses.
- 1806df5 — mandatory native/release/checked gate and main parity ratchets.
- fad6b05 — canonical formatting.
- 05c7f9f — README-only refresh; 1bacc82 — API/source documentation.
- f64b544 — name the retained revision-grammar refusal rather than the retired whole-command stub; final functional input change.
- c18063b — final captures, input binding and derived counts; evidence only.

Read the contract, campaign/RULES, vc07–vc04 notes, MAP/SOURCES and Wolf guide. SOURCES cites git-cherry-pick, git-rebase, git-revert/sequencer, gitrepository-layout, git-commit and git-reflog by section. Metadata absent from the layout page was measured, not attributed to that page. No new gitformat-* or gitprotocol-* parser.

## Evidence index

Final head c18063b0da786577c9ad99660baf9bd305e4ca6b. Full `tools/gate` exit 0 on hasu, **2026-10-27 17:54:24–18:05:34 UTC**, covering f64b544. `final-gate.log` and `final-inputs.json` bind **298 functional files** before/after; `counts.py` independently verified all 298 again in the final Mac tree. Static Linux builds repeated identically; stripped size **2,322,904 bytes**, SHA256 b00b9c7d653ca0567dcff3ea54d1938c1b33cf3f2b5c337ca4198c5a7cdcd606.

Per native/release tier, derived from captures:
- **89 exact complete-state scenarios**, **130 exact process-boundary comparisons** including earlier steps of scope cases; **20 named scope captures**, not parity.
- **136 independent importing-client checks**; one bounded actual-checked program reports **exit(0)**; zero new skips.
- Main **190 = 176 parity / 13 named not-yet / 1 shape / 0 failures**. All inherited component gates remain mandatory and green.
- Existing two hunk witnesses/eight contexts and 96 capture-bound binary representations remain separate non-parity counts.

Captures include single/list picks; full/short refs, tags and OIDs; packed/detached inputs; source author/date versus committer; empty/redundant handling; sequencer head/todo/options and rebase onto/orig-head/done/stopped metadata; first/second-step conflicts, stages/REUC; explicit resolution, continue/skip/abort; dirty/untracked safety; and initial/recovery locks, including earlier published state. Every repository/worktree file is compared. The six-word per-file stat proof and validated raw-object/OID policy are unchanged.

The first full run reached the main matrix but its legacy `rebase HEAD~1` row still expected the retired command stub. `pre-classifier-*` preserves that red and both outputs. f64b544 classifies the still-open **replay revision grammar** by its exact named refusal; the row was not promoted to parity. The complete gauntlet was rerun afterwards.

Plant **#23**, head 48dfbf3, CI run **40541318283**: the coordinator verified `wolf-trap: assert at src/sequencer_test.lu:16:5` and closed it unmerged. Correct implementation was committed first. The lane's sole immediate CI read saw queued; its redundant local plant waiter was cancelled before compilation, so no local plant red is claimed. `plant-ci-verdict.txt` records that provenance. No lane CI wait or label.

### Recommendations implemented

- **R-vc08-1:** retain named prewrite refusals for `replay AUTO_MERGE lock transient stat` and `cherry-pick dirty recovery transient stat`; do not invent historical stat proofs or exclude index bytes. R-vc07-1's dirty true-merge recovery remains open.
- **R-vc08-2:** default rebase refuses `rebase possible upstream patch equivalence; use --reapply-cherry-picks`. The original net-line checksum is a conservative refusal filter, **not patch-id and never a reason to drop a commit**. Explicit reapplication remains subject to the existing tree limits.
- **R-vc08-3:** retain `rebase continuation editor execution`; explicitly commit the resolution first, then continue. Interactive/apply/real-merge replay, separate branch operands and upstream inference remain named. General revision grammar stays vc10; revert sequences/mainline remain open.
- **R-vc08-4:** refuse changed abort tips/original branches, foreign state files and unsupported replay configuration before recovery writes. State files, including author-script, are inert data. R-vc07-2's repeated-line/multi-hunk, rename topology, binary/modify-delete/nonregular and recursive-base boundaries remain; no arbitrary-replay claim.

The 20 scope captures name the transient-stat cases, staged-editor continuation, possible equivalence, inherited multi-hunk/repeated-line/rename/nonregular/binary/modify-delete limits, changed HEAD/original branch, foreign rebase state, rebase.autostash/commit.cleanup configuration, rebase -i/--apply/--rebase-merges and cherry-pick -n. Earlier exact steps remain checked; refused steps must leave their own pre-step state immutable.

### M3 / M2 checklist

- [x] Bounded single/list cherry-pick, author/date preservation, measured empty options and durable continue/skip/abort.
- [x] Current-branch linear rebase/--onto, detached progress, exact skip/abort and explicit-resolution-commit followed by continue.
- [x] Shared walk/mergetree/index/ref/commit boundaries, shared rename scorer, no index.write_tree history reads, independent client and actual-checked proof.
- [ ] Staged editor-dependent rebase continuation, exact upstream patch-equivalence selection and the named replay/configuration/recovery boundaries above.
- [ ] Remaining vc07 true-merge/recursive/rename/alignment/unborn/annotated/mainline boundaries; blame, stash/notes and general revision grammar. **M3 is not complete.**
- [ ] M2 editor execution, combined merge show and named history presentation/selection limits; hunk/binary exceptions remain non-parity.

### vc09 draft

Recommend **M4 pack/idx reading beneath object.read_object** next: pack v2 and idx v2, OFS/REF deltas, checksums/object identities, bounded chains and offset-window reads without mmap. Keep objects owned and callers unchanged; validate against the pinned Git binary, fsck/verify-pack, independent clients, bounded checked units, corruption/truncation/limit cases and named plants. Run the complete inherited gauntlet, especially history and replay, to prove packed lookup is transparent. Pack byte identity is not the target. Ordinary packed repositories are a fundamental usability gap; this does not waive the named M3/M2 follow-ons or declare either milestone complete. General revision grammar remains vc10's work.

## Done-when

- [x] Prediction before implementation; clean-room references and twice-read pins.
- [x] Native/release complete-state matrices, independent client, actual-checked exit and named scope captures.
- [x] Intended CI plant red verified and closed by coordinator.
- [x] Full inherited gauntlet at final functional inputs; repeat static builds; all 298 final-tree hashes verified.
- [x] README-only refresh, MAP/SOURCES and vc09 draft.
- [ ] Coordinator verifies final PR-tier green, labels the final head for the full matrix, and watches its result; no lane label/wait/merge.
- [ ] Coordinator materialises this five-section body as the vc08 note on trunk.

No new upstream issue to file; none filed or closed. Preserve `/home/mfwolffe/lanes/vc08/den` and captures for review. That clone is clean at c18063b, and all 298 functional hashes were verified there again. Both clean Mac vc08 worktrees were removed individually without force. No vc08 job remains running.

### Final-head handoff

PR #24, head c18063b0da786577c9ad99660baf9bd305e4ca6b. Single immediate CI read: run [40558786287](https://github.com/wolffe-lang/den/actions/runs/40558786287), queued. No further lane CI polling, wait or label.

One audit invocation from the org directory, with explicit `/Users/mfwolffe/lanes/vc08/den`, exit 1. Literal last line: `AUDIT FAIL (footprint: cross-cutting)`. Only merge-gate conditions failed: head CI was in progress, no green tier had completed, and the coordinator-owned full-matrix label was absent. Ancestry, attribution, footprint, matching PR head, all five sections, untouched spec, all 22 cited SHAs, removed worktree and orphan checks passed. The audit was not rerun.

