# vc04 — the diff

Materialised from den#12 (head b396a2c8, merged 2026-10-25) at the merge; evidence under `notes/vc04-evidence/`.

Footprint: cross-cutting

## Forbidden

Git documentation, the Myers paper, existing org-owned code and the pinned black-box executable only. No Git/libgit2/VCS/diff-library/codec implementation source, host package installation, org merge/tag/release/issue action, label, private planning edit, memory edit or git-config invocation. Builds/tests used hasu block B, taskset 6–11 inside the existing rootless container, 12 GiB cap and flock per run. No Mac builds.

## Inputs verified

Base `fd42d7ff`; wolf 0.2.35, lupin 0.1.56 and std2386522e unchanged. Two fresh release/tag reads and the oracle executable's two digest reads are in `notes/vc04-evidence/pins/`. Git2.56.0 matches SHA256 c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60.

- `f7df8b4` — prediction before implementation.
- `4dcae9d`, `1b7c269` — fingerprint derivation and original wolf scorer.
- `a60f081` — shared candidate pairer, status and commit consumers.
- `3803181`, `50fb79c` — unified hunks and binary patch bodies.
- `34cd41d`, `7284a66` — endpoints, pathspecs, output forms and measured index refresh.
- `7cdffc8`, `76ec0d1` — mandatory gates and corrected CI negative control.
- `de15aa5`, `3f77ca6` — bounded scratch/API validation, terminal widths and configured display defaults.
- `e6e5969`, `7df7be4`, `b396a2c` — contracts, README and final evidence.

## Prediction

The committed prediction remains unchanged. Hits: exact chunks and a line ratio are insufficient; 49% rejects/50% accepts; default indent heuristics change measured output; scoring/pairing is shared. Miss: the ordinary worktree binary `index` line uses the computed destination OID, not all zeroes. There are no retrofitted expectations.

## Evidence index

Final head: `b396a2c80d4d25e277f469efbfb4b2cc5f635ca6`. Final-head PR run [40228095166](https://github.com/wolffe-lang/den/actions/runs/40228095166) was in_progress at the single direct CI read; no wait or poll. The mandatory audit's own lookup also saw it pending.

Audit read directly: `AUDIT FAIL (footprint: cross-cutting)` solely because head CI is still running, no green tier has completed, and the coordinator has not yet applied full-matrix. All other checks pass: fast-forward ancestry, report/commit provenance, untouched spec, matching PR head, owned worktrees removed and no orphaned lane processes. No label was applied by the lane.

Full local `tools/gate` exit0, 2026-10-25 19:24:43–19:30:43 UTC, at functional head `3f77ca6`. `notes/vc04-evidence/final-gate.log` ends `FINAL INPUT MANIFEST UNCHANGED 234`. All234 hashes still match the final head; subsequent changes are documentation/evidence only. Static builds were repeated with identical digests. `final-counts.json` derives the counts from captures.

| Corpus | Native | Release |
|---|---:|---:|
| Inherited similarity pairs | 1510/1510 | 1510/1510 |
| Newly isolated hash collisions | 24/24 | 24/24 |
| Multi-candidate pairing | 267/267 | 267/267 |
| Status/commit full-state consumers | 1044/1044 | 1044/1044 |
| Basic diff display/state | 336/336 | 336/336 |
| Endpoints, pathspecs, thresholds, stat widths | 575/575 | 575/575 |
| Stat-cache refresh/state | 66/66 | 66/66 |
| External collect/render API | 12/12 | 12/12 |
| COLUMNS/private-PTY widths | 90/90 | 90/90 |
| Hunk bytes | 676/684; 8 named differences | 676/684; 8 named differences |
| Binary body bytes | 154/250; 96 representation differences | 154/250; 96 representation differences |
| Binary forward/reverse indexed application and exact CLI envelope | 250/250 | 250/250 |

Similarity suite counts: initial123, random300, hash522, structural90, equivalence301, wrap174 =1510. These score/default-threshold results are separate from the267 multi-candidate cases. The new24 collision pairs include16 projection-fit pairs and8 held-out validation pairs. Production has no fixture exception table.

Main matrix:188 =167 parity /20 named not-yet /1 shape /0 failures. Four new actual-checked programs (`delta`, `rename`, `difftext`, `diffbinary`) report `exit(0)`. New gates have zero skips. The inherited checked-budget/platform limitations remain explicit, not relabelled passes.

Corrected intended plants, confirmed by the coordinator's CI read; all remain open:
- den#13, `40e94ad`, run40222929774 — `vc04 gate: exact unified hunk header`.
- den#14, `c704b47`, run40222930228 — `vc04 gate: reject a rename at 49 percent`.
- den#15, `6b16a4a`, run40222930811 — `vc04 gate: missing-final-newline marker`.

The first plant heads' unrelated planner-preflight failures are not counted. The CI self-test had hard-coded the now-implemented diff-symlink refusal; it now requires log-default to remain unimplemented and checks every new mandatory gate. This CI edit is why the footprint is cross-cutting.

## Note

Diff supports worktree/index, cached, two loose commits/trees/blobs, unified context/final-LF markers, modes/types, binary/stat/name forms, shared rename/copy detection and top/literal/icase/glob/exclude pathspecs. Pure `diff.collect`/`render` never publish state; `diff.configured` supplies config/terminal defaults. The CLI implements documented `diff.autoRefreshIndex`, including silent foreign-lock suppression and the six independently proved inode/time words. An explicit zero stat width means80; omitted width follows COLUMNS/window size.

R-vc04-1 A remains the recommendation: measured chunk-hash similarity, supported by every inherited pair. R-vc04-2 remains the recommendation to follow observed R100 scores and correct the documentation's identity claim; unequal R100 contents still contribute actual edit counts.

R-vc04-3 remains a recommendation: retain the two named equal-cost alignments, seeded-21 and seeded-116, at four context widths. Complete inputs and both outputs are immutable review records. Every patch reconstructs both directions and has the same insertion/deletion counts as the oracle. The eight are NOT parity passes; default indentation is not silently disabled. Git's two heuristic modes differ in56/684 observations.

R-vc04-4 was decided by the coordinator by analogy to R4c and refined to include literal/delta choice and `delta N` instruction-byte lengths as representation-dependent. Literal target lengths, blob sizes/OIDs, `GIT binary patch`, ordinary diff/index/mode headers and canonical base85 framing are exact or independently validated. Every accepted body is capture-bound and applies forward/reverse to exact blobs; new/changed captures fail. The strict byte report remains visibly red, separately from the accepted application gate. Bodies follow Git's level-1 zlib/delta search: den reproduces55/150 original cases and154/250 expanded cases, not the rest. There are96 total differing expanded cases (95 original plus1 new), not97. The maintainer can overrule the analogy.

Bounds and inherited limits are explicit in README/MAP: 16-MiB bodies, 128-MiB aggregate endpoints, 200,000 text lines, 2,000-change general Myers searches and2,000-candidate rename pools; attrs/filters, unmerged output, general revision walks and packs are not smuggled into a parity claim. Simple bounded caret/tilde ancestry is implemented. No new upstream issue was filed. README read and refreshed in its own commit. The wrapper does not write Markdown lane notes; this Note is the materialization source.

### vc05 draft

Implement log/show walking and pretty dates over the preserved raw object/header APIs. Reuse `diff.configured`, `collect`, `changes` and `render` for patch/stat output; do not call the porcelain CLI or index.write_tree from a history reader. Preserve detached/unborn HEAD provenance, ordered parents, raw messages and separate human/reflog subject rules. Add byte-exact default/oneline/n/date/show/-p/--stat matrices, bounded actual-checked units and independent external clients. Carry the two named hunk witnesses and capture-bound binary representation policy visibly; do not call them parity or duplicate the scorer/pairer. General revision grammar remains its planned separate surface. No M2-complete claim until log/show's gate passes.

## Done-when

- [x] Prediction, primary-source record, twice-read pins.
- [x] Shared scorer/pairer and status/commit/diff integration.
- [x] Endpoint/pathspec/display generators, native/release and actual-checked witnesses.
- [x] All three intended CI plant reds at corrected heads; left open.
- [x] Full local gate, static archive repeat, unchanged234-input manifest.
- [x] Explicit hunk/binary differences, immutable captures, strict byte report.
- [x] README/API/source updates and vc05 draft.
- [x] Final head pushed, PR ready, canonical audit read directly; only CI/label requirements pending.
- [ ] Final-head tier-pr result, then coordinator's full-matrix label and tier-full watch.

## Follow-ons

R-vc04-3's exact tie alignment and exact binary representation remain visible follow-ons, not hidden greens. The final audit reports only the pending PR/full-tier requirements; no lane label or CI wait. The coordinator owns the final-head full-matrix label/watch and plant closeout. No merge, tag, release or issue action is part of this handoff.

The four clean local vc04 worktrees were removed individually without force. The reproducible pool tree and logs remain at hasu `/home/mfwolffe/lanes/vc04/den` and `/home/mfwolffe/lanes/vc04/final-gate.log`; no pool job or helper remains running. Preserve those until adoption. The local shared checkout was never switched.

