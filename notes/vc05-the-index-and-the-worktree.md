# vc05 — history: log and show (den M2, partial)

_Materialised from den#17's PR body at the merge (8bb545f); the lane's wrapper could not write Markdown notes._

## Prediction
Committed before implementation in `notes/vc05-evidence/prediction.txt`. Default order follows committer timestamps on the pending frontier, stable on ties, not author dates or a global sort. Ordered parents and raw headers/messages survive; human first-paragraph subjects differ from reflog first-line subjects. Readers must not publish objects/index/refs.

Hits: frontier ordering, parent ties, author-date display, stored timezone and read-only behavior. Corrections from retained black-box witnesses: UTC strict ISO ends in Z; medium message tabs expand; patch+stat inserts `---`; show revision limiting is not ordinary input-order truncation. No oracle expectation was rewritten to accept a differing byte result.

The wrapper does not write Markdown lane notes. This five-section PR body, including the vc06 draft below, is the note materialization source.

## Forbidden
No Git/libgit2/VCS implementation source was opened. Only Git 2.56.0 documentation and its pinned executable, plus existing org-owned APIs. No production subprocess dependency, compiler/std/pin change, package installation, planning or memory edit, label, merge, tag, release or issue action. Builds/oracle ran on hasu block A, taskset CPUs 0–5 inside the existing rootless container, 12 GiB cap and `/home/mfwolffe/lanes/hasu-A.lock`. No Mac builds.

## Inputs verified
Base den trunk c3426ec. Wolf 0.2.35, lupin 0.1.56, bundled std 2386522e unchanged. Two release and annotated-tag reads, plus two staged binary/runtime/std/oracle reads, are retained in `notes/vc05-evidence/pins/`. Oracle Git 2.56.0 SHA256 c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60. Archive identities remain 4cc4045b… and ad703550…; the full digests are in the captures and pin file.

Read vc04's entire note/draft, MAP/SOURCES, M2 campaign/surface limits and RULES §1–§10. New primary reads: git-log Description/Options/Diff Formatting; git-show Description/Options/Examples; pretty-formats built-ins and merge line; rev-list-options Commit Limiting, Commit Ordering and --date. No new gitformat-* or gitprotocol-* parser was introduced; inherited format references remain in SOURCES.

- c0e05a9 — prediction before implementation.
- 8b8eb58 — raw owned commits and stable timestamp walk.
- 4d9c744 — pure pretty dates/identities/messages and checked units.
- 874a93d — log/show, tree/tag/blob/path display and shared diff consumers.
- d4fb0d1 — independent oracle generators and complete state comparisons.
- 6935539 — mandatory native/release/checked gate.
- 72c1486 — stable frontier slots without repeatedly copying pending commits.
- 89f9ce3 — config/refusal controls and independent resource-bound clients.
- 858027a — isolate scratch patch application from an enclosing Git checkout.
- 2900a03 — require main-matrix parity for log/show.
- 8bb545f — final captures, pin reads and functional input manifest.
- 97ef7f5, 606901e — README-only refresh and API/source contracts.

## Evidence index
Final head: `8bb545f27f1243acfe938087717e73f7416a4f57`. Final-head PR run [40370819005](https://github.com/wolffe-lang/den/actions/runs/40370819005) was queued at the single direct read; no wait or label.

Full local `tools/gate` exit 0 on hasu, 2026-10-26 17:31:51–17:38:30 UTC, functional head `2900a031a9521d51d568880f168c58e5e103f9b5`. `notes/vc05-evidence/final-gate.log` contains the complete run. `final-inputs.json` binds all 242 tracked functional files, still identical at final head. The original pre-run inventory is also retained; its 678 generated compiler-cache entries are explicitly excluded from source identity, not treated as inputs. Subsequent changes are evidence only.

Main matrix: 188 = 170 parity / 17 named not-yet / 1 shape / 0 failures. Static build repeated with identical SHA256 `ce431991d49e4d66bc4feb2a2631d651718ac59509c1daa846424085b955195a`; stripped size 2,024,344 bytes. Inherited full-gate hunk/binary policies still distinguish 676/684 exact hunks (8 named differences) and 154/250 exact binary bodies (96 capture-bound representations); all 250 apply in both directions. `final-counts.json` derives the history counts and checked verdicts from captures.

History: 575/575 exact stdout/stderr/status and immutable file-byte/mode state on each native/release tier, three independent-client checks per tier, two actual-checked `exit(0)` programs, eight separately named unsupported rows, zero new skips. Fixtures cover message whitespace/NUL/raw bytes, fixed dates/offsets, root/linear/merge/tied/skewed histories, detached/unborn HEAD, ordinary patch/stat/rename/binary output, tree/tag/blob and `REV:path` show, a deliberate four-digit object-prefix collision, foreign index locks and dirty worktrees. `show` revision-limit observations retain both the Git output and the named refusal, never count as parity.

An inherited hunk semantic gate was not clone-safe: `git apply` discovered the enclosing den checkout and silently skipped its scratch-relative patch. The first complete local gate failed `boundary--6f6e65` reconstruction. The preserved red log is `notes/vc05-evidence/full-gate-enclosing-repo-red.log`; the fix places the apply subprocess below a GIT_CEILING_DIRECTORIES boundary. Afterwards the unchanged 684 cases give 676 exact/8 named hunk differences and zero unreviewed differences. No expected patch bytes changed.

CI plant: #16, head 61fe363, deliberately replaces Author with Writer. `tools/check-history` must fail the default message comparison. The one immediate run-id read returned an empty list; the coordinator must inspect the intended red, not infer it. The plant remains open/unmerged, and its clean local worktree was removed. No CI wait or label by this lane.

## Done-when
- [x] Prediction committed before code; source/input record retained.
- [x] Ordered/lossless walk and pretty boundaries; no porcelain calls or index.write_tree in history readers.
- [x] Exact bounded command matrices, actual-checked units, independent importing client and byte/mode state checks.
- [x] Complete local gauntlet green; all 242 tracked functional hashes unchanged; static builds repeat exactly.
- [x] README read and refreshed in its own commit.
- [x] Inherited hunk/binary exceptions remain visible, separately counted and unchanged.
- [ ] Coordinator verifies intended CI plant red, final PR-tier green, then applies full-matrix and watches the full tier.

Audit (one invocation at final head): `AUDIT FAIL (footprint: cross-cutting)`. It found only pending head CI/no green tier, the missing coordinator-owned full-matrix label, and the Mac worktree still present at audit time. Both clean vc05 Mac worktrees were subsequently removed explicitly without force; the audit was not rerun. Two warnings are the verified archive digest prefixes, not stranded commit SHAs. All cited commit SHAs resolve, PR head matches, ancestry is fast-forwardable, spec is untouched, and no orphaned lane processes were found.

### M2 checklist
- [x] Inherited index v2 writing and v3/v4 reading; add/rm/mv/status measured subsets retained by the full gate.
- [x] Inherited commit -m/-a/--amend, identity/config/env and deterministic input dates; path restore/checkout; measured ignore precedence retained.
- [ ] Actual commit editor execution remains a named vc03 limitation; literal path and higher-stage mutation limits also remain.
- [x] Worktree/cached/two-commit diff, shared rename detection, ordinary binary display and stat retained.
- [ ] Exact diff alignment/representation is not universal: vc04's two hunk witnesses (eight contexts) and 96 binary representation captures remain explicit, not parity.
- [x] Bounded log default/oneline/-p/--stat/-n, stable revision walk, fixed date formats and first-parent/skip/reverse controls.
- [x] Show ordinary commits, trees, blobs, annotated tags and literal REV:path; merge messages via show -s.
- [ ] Combined merge show needs a multi-parent diff renderer; show-specific revision limiting, history path simplification, custom pretty formats, relative/human dates, non-UTC local zones, transcoding/mailmaps and non-ASCII tab widths remain named refusals. General revision grammar stays M3.

M2 is not complete; a green bounded history gate does not erase these items.

### Recommendations implemented
- R-vc05-1: keep combined merge display a named refusal until a shared multi-parent diff API exists; default log -p omits merge patches, explicit first-parent reuses the existing diff API. Never approximate dense-combined output with an unrequested first-parent patch.
- R-vc05-2: keep unsupported show limiting and clock-relative/local-zone/width/transcoding surfaces separate from exact counts. Preserve oracle captures and refuse by name rather than inventing bytes or changing expectations.

### vc06 draft
Implement refs/branches under M3 over the existing raw object and HEAD provenance APIs: attached/detached HEAD, loose/packed refs, reflogs, branch/lightweight and annotated tag commands, switch/branch checkout and reset soft/mixed/hard. Preserve ref CAS/exclusive-lock ordering and report multi-file failure side effects. Differentially measure packed-refs lookup, unborn/detached output, reflog messages, branch safety and reset index/worktree state; use independent clients and actual-checked bounded units. Do not reuse index.write_tree as a history read or fork the rename/diff scorer. Before claiming M2 complete, supply the missing multi-parent show renderer and the explicit remaining history/editor rows above, or retain them unchecked. Keep the two hunk witnesses and capture-bound binary representation policy visibly separate from parity. General ranges/reflog revision grammar remains vc10's surface.

### Follow-ons and prune list
No issue filed or closed. Proposed den follow-ons: combined merge show and remaining history presentation/selection surfaces; the enclosing-checkout hunk-harness defect is fixed here. The coordinator owns plant closeout and CI labels/watches. No upstream compiler/std gap was newly found.

Removed clean local `/Users/mfwolffe/lanes/vc05/plant-pretty` and `/Users/mfwolffe/lanes/vc05/den` individually without force. Keep hasu `/home/mfwolffe/lanes/vc05/den` until adoption: it is clean on branch vc05 at final head, with all 242 functional hashes verified again. The Mac `/Users/mfwolffe/lanes/vc05` helper/bundle files and hasu lane-owned bundles, source tar, target data and copied toolchain may be pruned afterwards. Never prune the shared hasu-env image/store or another lane. No long-running job is intended to remain at handoff.

