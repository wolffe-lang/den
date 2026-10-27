# vc09 — pack and idx reading

_Materialised from the body of den#26 at the merge (`57bc8dbd`)._

# vc09 — pack and idx reading


## Prediction

`ef66f80` preceded implementation. Packed lookup needed both the object reader and the prefix namespace; writes also had to avoid duplicating an already-packed object. CRC, SHA-1, zlib consumption and reconstructed OID checks proved distinct. Forward REF bases, OFS boundaries, cycles and the zero-copy-size instruction are independent witnesses. No command expectation was weakened.

## Forbidden

Git 2.56.0 documentation and the pinned binary only; no Git/libgit2/other VCS implementation source opened. No production subprocess dependency, pin/compiler/std change, package installation, planning/memory edit, label, merge, tag, release or issue action. Fresh hasu vc09 clone; block A, taskset 0–5 inside the rootless 12-GiB container under its block lock. Mac worktrees for git only, no Mac builds. No helper agents.

## Inputs verified

Base `c0e4c17`; wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4, bundled std 2386522e unchanged. Release/ref/annotated-tag metadata, archive digests, staged binaries/runtime/std files and oracle identity were read twice; `notes/vc09-evidence/pins/`. Oracle SHA256: c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60.

- `e9ca1c0` — independent encoder, malformed inputs, importing client and bounded units before implementation.
- `4292358` — pack/idx reader, delta application, transparent object/prefix integration and packed-object reuse on writes.
- `4c2101c` — complete inherited matrices over packed fixtures.
- `d3b755e` — mandatory native/release/checked pack gate and all-object interop.
- `f462473` — named missing-companion refusals and canonical formatting.
- `ee3e373` — all six entry types required; packed output binding and expanded structural cases.
- `26bf315` — README-only refresh.
- `28ae0ea` — MAP/SOURCES; last functional-input change.
- `57bc8db` — final captures and unchanged-input proof only.

Read contract/RULES/campaign, vc08 and vc04 notes, MAP/SOURCES and the Wolf guide. SOURCES records gitformat-pack by checksum/header/type/size/delta/idx-v2 sections, and gitformat-index by header/entry/extensions. The worktree-index page is not misidentified as the pack-idx specification.

## Evidence index

Final head: 57bc8dbd6b4a3c40b69699efffb9fd72ad008b37.

Exactly one full `tools/gate`, hasu, **2026-10-27 19:35:57–19:52:03 UTC**, completed all inherited gates and both identical static builds. Main matrix remains **190 = 176 parity / 13 named not-yet / 1 shape**. Stripped static binary: **2,342,552 bytes**, SHA256 e2bcbed068f2881eb0ff11c8a4388d8ad2fe15b735ccd584441aa5102a8865bd.

**Exit accounting is explicit:** `tools/gate` returned 0 (the recorded `bash -ec` proceeded to its next command); the enclosing runner returned **1**, because my post-gate manifest walk had included generated `.lu-cache` files. The raw failure, original 550-entry manifest and runner remain unchanged. The independent `verify-functional.py` filters only generated cache paths, checks the remaining path set both ways, adds five tests bound to the functional Git head, and verifies **318 unchanged functional inputs** on hasu and the final Mac tree. No source or expectation changed after the gauntlet; no second gauntlet was run. `final-accounting.txt` explains this bookkeeping failure rather than calling the wrapper green.

Per **native and release**, derived by `counts.py` from complete retained captures:

| Proof | Exact / total | Separate named rows |
|---|---:|---:|
| All oracle-listed raw objects | 2,442 / 2,442 across 34 packed fixtures | 0 |
| Independent structure/corruption/limit inputs | 141 / 141 | errors are required results, not oracle parity |
| Packed history command/state | 575 / 575 | 8 |
| Packed refs command/state | 434 / 434 | 8 |
| Packed merge command/state | 117 / 117 | 12 |
| Packed replay scenarios | 89 / 89 | 20 |

Replay retains 150 process captures: 130 exact comparisons and 20 separately named refusals. History also retains three external-client checks. Oracle inventories include commit/tree/blob/tag plus **33 OFS and 33 REF entries** per tier; Git fsck/verify-pack pass. The independent pack client reads raw body/type/OID bytes. `pack-checked.json` reports actual **exit(0)** for bounded CRC/delta units. Zero new skips.

Captures are `notes/vc09-evidence/{structural,interop,history,refs,merge,replay}-{native,release}.json.gz`; their raw hashes and counts are in `final-counts.json`. Tests cover loose precedence, multiple packs/duplicate names, `.keep`, forward REF chains, 64-link boundary/over-limit, cycles, exact caller caps, all copy fields, CRC/checksum/binding failures, truncated files and 300,000-byte input crossing 64-KiB windows. Large-offset slots use synthetic small packs; no multi-gigabyte IO benchmark is claimed. Existing hunk/binary exceptions remain non-parity.

Retained initial red: `initial-red.log` (36 packed cases missing). `packed-unreachable-red.log` exposed a fixture-builder defect: ordinary repacking dropped an unreferenced packed commit. The corrected builder uses `--keep-unreachable` and checks the entire before/after OID sets. A separate structural fixture correction addresses the first physical offset rather than the first lexicographic ID. The later history-output fix prevents a client mode variable from shadowing the packed-mode selector.

CI negative control **#25**, `bf8ba2f`, run **40569986934**. Correct implementation was committed first. Intended failure: CRC known-answer assertion at `src/pack_test.lu:4`; single immediate lane read saw in_progress. Coordinator observation/closeout is pending; no CI-red verdict is fabricated, no lane wait or label.

### Recommendations implemented

- **R-vc09-1:** use bounded owned reconstruction: 16-MiB entries/bodies, 17,000,000 compressed bytes, 64 delta links, 128-MiB charged reconstruction payload, 16-MiB/400,000-entry indexes and 256 packs. File IO/checksums use reclaimed 64-KiB windows; this is not whole-object streaming or a peak-RSS guarantee. No persistent checksum cache; candidate packs are rehashed. Limits refuse by name.
- **R-vc09-2:** use ordinary idx-v2 oracle generation for interoperability. The retained `index-threshold-probe.json` shows `index-pack --index-version=2,1` returning success, followed by the same Git rejecting its tiny index as `wrong index v2 file size` (cat-file itself still exits 0). Do not count this as a parity pass or imitate an empty inventory. The reader's checked 64-bit slot arithmetic remains independently tested on synthetic data. Recommend an upstream Git report only with approval; none filed.

### M4 reading checklist

- [x] Pack-v2/idx-v2 headers, count, fan-out, sorted names, CRCs, 32/64-bit offsets, both SHA-1 trailers and binding.
- [x] Undeltified kinds, OFS/REF chains, copy/insert instructions, identity and bounded cycle/depth/size handling.
- [x] Transparent loose/one-pack/multiple-pack reads and prefixes, `.keep`, no duplicate loose writes for packed objects.
- [x] Independent clients, pinned interop, corruption/truncation/limits and bounded actual-checked units.
- [x] Inherited complete-state matrices over packed copies; full inherited gauntlet at unchanged functional inputs.
- [ ] Pack writing, gc/repack/fsck/count-objects/verify-pack commands; multi-pack-index/bitmaps and thin packs/protocol. **M4 is not complete.**
- [ ] All named vc08/vc07 M3 and M2 follow-ons remain; no general replay/merge or revision-grammar waiver.

### vc10 draft

Implement a shared, bounded revision parser/evaluator next, from gitrevisions documentation and pinned-binary measurements. Separate an owned syntax tree from repository resolution and commit-set walking. Unify the existing diff caret/tilde adapter with refs/history/replay consumers rather than adding another parser. Stage full/short refs and OIDs, parent/ancestor and peel forms, literal `REV:path`, reflog/previous-checkout selectors, exclusions and two/three-dot ranges with explicit grammar and consumer-specific restrictions. Preserve ambiguity, unborn/detached provenance, parent order and raw path bytes; never call index.write_tree for history reads. Differentially compare successful results and exact malformed/ambiguous diagnostics across loose and packed fixtures; add independent importing clients and small actual-checked parser units. Keep walk-order and replay/merge limitations named, and retain all vc08 scope rows. Stash/notes and blame remain separate follow-ons rather than pretending this parser completes M3.

## Done-when

- [x] Prediction before implementation; clean-room references and twice-read pins.
- [x] Native/release interop, corruption and packed complete-state matrices; actual-checked exit.
- [x] One complete inherited gauntlet; repeat static builds; 318 functional hashes verified, wrapper bookkeeping failure retained explicitly.
- [x] README-only refresh, MAP/SOURCES and vc10 draft.
- [x] Final head pushed; no lane label/wait/merge.
- [ ] Coordinator observes/closes intended CRC plant #25, verifies final PR-tier green, labels the final head and watches full tier.
- [ ] Coordinator materialises this five-section body as `notes/vc09-pack-and-idx-reading.md` on trunk.

Potential issue to file with approval: the nondefault Git index threshold witness above. No issue filed or closed by this lane. Preserve `/home/mfwolffe/lanes/vc09/den` and its evidence; the clone is clean at the final head and no vc09 job remains running. Both clean Mac worktrees were removed individually without force.

### Final-head handoff

PR #26, head 57bc8dbd6b4a3c40b69699efffb9fd72ad008b37. Single immediate CI read: run **40574167730**, in_progress; no further lane polling or label.

One canonical audit invocation, exit 1. Exact last line: `AUDIT FAIL (footprint: cross-cutting)`. Only merge-gate conditions failed: head CI is running, no green tier has completed, and the coordinator-owned full-matrix label is absent. Ancestry, attribution, footprint, matching PR head, five report sections, untouched spec, all 14 cited SHAs, removed worktree and orphan checks passed. The audit observed plant #25 already closed; this lane has not read its CI conclusion and makes no independent intended-red claim. The audit was not rerun.

