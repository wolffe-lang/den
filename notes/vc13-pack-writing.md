# vc13 — pack writing over the existing reader

_Materialised from the body of den#34 at the merge (`78076c45`)._


## Prediction

`75a860f` committed `notes/vc13-prediction.txt` before implementation or oracle measurements. P1/P2 held: pack-v2 and idx-v2 writing needed no reader change, and vc04's delta encoder is shared rather than duplicated. P3 held for the compressed modes: window 10/depth 50, with measured maxima OFS 1.025967 and REF 1.399425 against Git. P4 held for separate construction/publication and loose-object preservation; publication is atomic per file, not a two-file transaction. P6's allocated-block/pack-size/prune-packable model matched the tested inventories. P8 held: gc/repack policy is left named rather than guessed.

P5 missed: verbose verify-pack reports **delta instruction-stream size**, not reconstructed object size. Empty packs omit the non-delta line, and the one-object histogram uses the singular. P7 was too broad: commit-graph checks, complex error rendering and multiple dangling-tip ordering remain explicit fsck boundaries. None of these limitations is counted as parity.

## What was built

### Forbidden

Git 2.56.0 documentation and its pinned binary only; no Git, libgit2, other VCS or external codec implementation source read. No production subprocess/dependency, toolchain pin change, package installation, helper agent, planning/memory edit, label, merge, tag, release or issue action. Fresh hasu vc13 clone from `1d64bb7f`; block A, taskset 0–5 inside the rootless 12-GiB container, lock held per run. Other lanes' directories were read-only. Mac worktree used for git/evidence handling, not builds.

### Inputs verified

Wolf 0.2.35 (wolf-lang `cf0c13d3`), lupin 0.1.56 (wolf-interp `28547b4`), bundled std (wolf-std `2386522e`) unchanged. Fresh release/ref/tag reads twice, archive digests twice, archive-versus-staged binary/runtime comparisons, std revision and staged/oracle hashes are under `notes/vc13-evidence/pins/`. Oracle built through `tools/fetch-oracle` at `/work/den`; every pack harness asserts SHA256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`.

Documentation: gitformat-pack checksum/header/type/size/delta/OFS/idx-v2 sections; pack-objects construction/default-window/default-depth/options; complete verify-pack/count-objects pages; fsck roots/full checks/diagnostics; gc/repack safety and publication options. `docs/SOURCES.md` records sections. The pack idx layout is not attributed to the worktree gitformat-index page.

- `75a860f` — prediction.
- `1b4cb02` — independent importing client and R4c contract before implementation.
- `fffa189` — one shared delta encoder, bounded pair construction and verified publication.
- `00a83fa` — pack inspection, count-objects, bounded fsck and pack-objects CLI.
- `1cdff51` — checked units, publication failures and inherited fixtures.
- `0d40fbf` — mandatory writer gate and planner assertion.
- `e37789b` — verified existing pairs need not create new files.
- `94f9dd3` — actual fifty-link chains, corruption/refusal proof, all-mode size gates and precise fsck scope metadata.
- `1cdd11f` — README-only refresh.
- `6bcbbb2` — MAP/SOURCES.
- `1529c37` — explicit shared dependencies for external binary-patch clients.
- `fa97baa` — retained targeted proof, fresh pins and final accounting.
- `a623ac0` — isolated plant evidence; full-gauntlet functional head.
- `f6b0700` — final captures and independent REF spot-check only; original PR head.
- `d6b8532` — isolated Linux CI timeout correction, 40 to 60 minutes, with a red/green planner assertion.
- `c8c7151` — snapshot-cost prediction before profiling.
- `a8da593` — unchanged-proof phase timings and explicitly labelled targeted profiles.
- `18d259f` — batch read-only object exchanges, strict framing/identity checks and complete process-state comparisons.
- `d3e24d3` — batch protocol provenance; README read, current.
- `78076c4` — before/after timings and complete native/release replacement pack proof; current PR head.

### Boundaries and recommendations implemented

**R-vc13-1:** retain bounded construction separate from publication and housekeeping. `pack.encode` emits owned pack-v2/idx-v2 pairs, with none/OFS/REF modes, deduplicated IDs, a ten-entry candidate window and fifty-link cap. Inputs cap at 10,000 objects, 16 MiB/body, 128 MiB aggregate input/output. `pack.install` writes and syncs an exclusive temporary pair, validates every object through the unchanged vc09 reader, renames pack then idx, and syncs the directory. Ordinary failures clean owned files; abrupt termination can leave an orphan pack that needs cleanup. No two-file transaction or crash-cleanup guarantee, and no loose pruning. gc/repack publication/expiry is named future work. These are payload bounds, not streaming or peak-RSS guarantees.

**R-vc13-2:** keep R4c semantic interop and the 1.5 size gate, never pack-byte/hash-stdout parity. OFS and REF modes both use Git's default-window/default-depth OFS baseline. Diagnostic no-delta mode is also gated, against Git explicitly given `--window=0 --no-reuse-object`; its default-Git ratio remains separately recorded. **REF's worst ratio is 1.399425 (1,461 / 1,044 bytes), only 0.100575 below the 1.5 ceiling: a follow-on expansion must not treat that as ample headroom.** The no-delta similarity/default ratio is 12.254789, and fanned-note/default ratios also exceed 1.5; those are not hidden or claimed as default-compression passes.

**R-vc13-3:** bounded fsck validates all loose/packed objects, parsed trees/headers/identities, typed links and HEAD/ref/index/reflog roots, but refuses commit-graph validation (unless explicitly disabled), multiple dangling-tip display ordering, detailed corruption/missing/wrong-type diagnostics, strict/configured fsck and alternate stores by name. The inherited main packed fsck row remains named, not parity; count-objects now requires parity. No silent clean verdict over unsupported auxiliary data.

### Pack rows

- [x] pack v2 + idx v2, canonical object IDs, entry CRCs, both SHA-1 trailers/binding; unchanged transparent reader.
- [x] Shared vc04 delta encoder for binary patches and pack OFS/REF entries; independent decoder and true depth-50 witnesses.
- [x] `pack-objects` stdin full object IDs to the repository's `objects/pack/pack` base; quiet/no-reuse, OFS, zero/default window/depth forms.
- [x] `verify-pack` and `-v` physical listing/chain histogram; `count-objects [-v]` with real allocated blocks; bounded `fsck --full`, `--no-dangling`, `--no-reflogs`, `--no-progress`.
- [x] Git verification/fsck and byte-equal cat-file of every new pack's objects, after removing old packed/loose copies only from test copies so duplicates cannot mask errors.
- [ ] Named: gc/repack/pruning, multi-pack-index, bitmaps, cruft, .keep policy, thin/transport/stdout, nondefault window/depth, unsupported pack configuration and arbitrary output bases; the fsck boundaries above.
- [ ] All inherited merge/replay/blame/stash/notes/editor/transport refusals stand. No M3- or M4-complete claim.

## Evidence index

Exactly **one full `tools/gate`, exit 0**, hasu block A, **2026-10-28 08:01:45–09:08:04 UTC**, at `a623ac0`. Literal completion:

`VC13 FINAL EXIT 0 2026-10-28T09:08:04Z`

`notes/vc13-evidence/final-gate.log` also records `VC13 GAUNTLET EXIT 0` and `VC13 FUNCTIONAL INPUTS UNCHANGED 448`; `final.exit` and `gauntlet.exit` are 0. Both input path-set directions and every hash checked. `tracked-inputs.log` verifies the corresponding **377 tracked inputs** at `f6b0700`; that head added evidence only after the gauntlet. Subsequent `d6b8532` changed the Linux workflow timeout and its planner assertion; the later cost correction changes test harnesses, their importing client and source documentation. Production code and toolchain pins remain unchanged, and the timeout stays 60. These follow-ups have their own targeted proof described in Corrections, including a complete native/release pack gate after batching. The earlier full gauntlet is not claimed to cover those later CI/harness edits; no second full `tools/gate` was run. `final-counts.json`, `inherited-counts.json` and `pack-sizes.tsv` derive the counts/table from captures. 111 top-level component sources and 570 complete main before/Git/den captures are retained, with content-identical files deduplicated by digest.

Static Linux build repeated identically: full **16,099,344 bytes**, SHA256 `3b373bd6722953b4a1eed89782500a75224b908b0b74527fbd6a3fea0c475a5d`; stripped **2,526,776 bytes**, SHA256 `6e1a384202dc73a3a0ffb1ab28dc78349804437b0e9c93b8e700c7b61dd28cc3`.

### Original full-gauntlet proof, per native and release tier

| Proof | Count |
|---|---:|
| Source fixtures: original 16 + similarity + den-origin + vc09 34 + vc12 6 | 58 |
| Pair encodings, none/OFS/REF | 174 |
| Canonical objects compared with Git and independent den importing client | 14,055 |
| Complete writer-harness process captures | 38,208 |
| Exact immutable command comparisons | 1,439 |
| Named immutable command refusals, separately counted | 39 |
| Publication failure/repeat cases + CLI publication | 8 + 1 (14 captures) |
| Adversarial cases / process captures | 22 / 415 |
| Actual chain witnesses | OFS 75 objects, depth 50; REF 75 objects, depth 50 |
| New bounded actual-checked program | `src/pack_write_test.lu`: exit(0), 5 check groups |

New gates have zero skips. Corruption cases include idx/pack checksums, CRC corruption with recomputed idx checksum, missing companions with loose duplicates retained, and foreign temporary ownership. Format/policy/configuration refusals preserve complete state. File/mode snapshots retain all bytes in a content-addressed store, with no path exclusions. Writer captures are interoperability evidence, not a claim that distinct pack bytes or hashes compare equal.

### Per-fixture pack sizes

Native/release rows are identical. Each cell is **den bytes / Git bytes (ratio)**; all gated ratios are at most 1.5. N = no-delta versus Git `--window=0 --no-reuse-object`; O/R = OFS/REF versus Git default-window/default-depth OFS. Only `.pack` bytes are tabulated; every companion `.idx` is independently validated. The full TSV additionally retains every no-delta/default-Git ratio. vc09 labels retain the original fixture ordinal and source encoding.

| Fixture | Objects | N: den / Git (ratio) | O: den / Git (ratio) | R: den / Git (ratio) |
|---|---:|---:|---:|---:|
| binary | 5 | 553 / 554 (0.998195) | 553 / 554 (0.998195) | 553 / 554 (0.998195) |
| empty | 2 | 162 / 162 (1.000000) | 162 / 162 (1.000000) | 162 / 162 (1.000000) |
| linear | 31 | 2,407 / 2,415 (0.996687) | 2,043 / 2,415 (0.845963) | 2,318 / 2,415 (0.959834) |
| m2-amend | 9 | 771 / 772 (0.998705) | 528 / 561 (0.941176) | 596 / 561 (1.062389) |
| m2-edited-rename | 5 | 264 / 267 (0.988764) | 264 / 267 (0.988764) | 264 / 267 (0.988764) |
| m2-ignore | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| m2-index-v4 | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| m2-modes | 6 | 359 / 360 (0.997222) | 359 / 360 (0.997222) | 359 / 360 (0.997222) |
| m2-staged-rename | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| m2-unborn | 0 | 32 / 32 (1.000000) | 32 / 32 (1.000000) | 32 / 32 (1.000000) |
| merge | 12 | 1,082 / 1,086 (0.996317) | 757 / 882 (0.858277) | 868 / 882 (0.984127) |
| packed | 31 | 2,407 / 2,415 (0.996687) | 2,043 / 2,415 (0.845963) | 2,318 / 2,415 (0.959834) |
| rename | 6 | 479 / 481 (0.995842) | 408 / 481 (0.848233) | 445 / 481 (0.925156) |
| symlink | 5 | 298 / 299 (0.996656) | 298 / 299 (0.996656) | 298 / 299 (0.996656) |
| thousand | 1002 | 37,693 / 36,739 (1.025967) | 37,693 / 36,739 (1.025967) | 37,693 / 36,739 (1.025967) |
| two | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| similar | 24 | 12,794 / 12,821 (0.997894) | 1,026 / 1,044 (0.982759) | 1,461 / 1,044 (1.399425) |
| den-origin | 9 | 653 / 653 (1.000000) | 543 / 653 (0.831547) | 580 / 653 (0.888208) |
| vc09-0-ofs | 5 | 553 / 554 (0.998195) | 553 / 554 (0.998195) | 553 / 554 (0.998195) |
| vc09-0-ref | 5 | 553 / 554 (0.998195) | 553 / 554 (0.998195) | 553 / 554 (0.998195) |
| vc09-1-ofs | 2 | 162 / 162 (1.000000) | 162 / 162 (1.000000) | 162 / 162 (1.000000) |
| vc09-1-ref | 2 | 162 / 162 (1.000000) | 162 / 162 (1.000000) | 162 / 162 (1.000000) |
| vc09-10-ofs | 12 | 1,082 / 1,086 (0.996317) | 757 / 884 (0.856335) | 868 / 884 (0.981900) |
| vc09-10-ref | 12 | 1,082 / 1,086 (0.996317) | 757 / 884 (0.856335) | 868 / 884 (0.981900) |
| vc09-11-ofs | 31 | 2,407 / 2,415 (0.996687) | 2,043 / 2,415 (0.845963) | 2,318 / 2,415 (0.959834) |
| vc09-11-ref | 31 | 2,407 / 2,415 (0.996687) | 2,043 / 2,415 (0.845963) | 2,318 / 2,415 (0.959834) |
| vc09-12-ofs | 6 | 479 / 481 (0.995842) | 408 / 481 (0.848233) | 445 / 481 (0.925156) |
| vc09-12-ref | 6 | 479 / 481 (0.995842) | 408 / 481 (0.848233) | 445 / 481 (0.925156) |
| vc09-13-ofs | 5 | 298 / 299 (0.996656) | 298 / 299 (0.996656) | 298 / 299 (0.996656) |
| vc09-13-ref | 5 | 298 / 299 (0.996656) | 298 / 299 (0.996656) | 298 / 299 (0.996656) |
| vc09-14-ofs | 1002 | 37,693 / 36,739 (1.025967) | 37,693 / 36,739 (1.025967) | 37,693 / 36,739 (1.025967) |
| vc09-14-ref | 1002 | 37,693 / 36,739 (1.025967) | 37,693 / 36,739 (1.025967) | 37,693 / 36,739 (1.025967) |
| vc09-15-ofs | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-15-ref | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-16-ofs | 91 | 10,924 / 10,358 (1.054644) | 5,245 / 6,734 (0.778883) | 6,339 / 6,734 (0.941342) |
| vc09-16-ref | 91 | 10,924 / 10,358 (1.054644) | 5,245 / 6,736 (0.778652) | 6,339 / 6,736 (0.941063) |
| vc09-2-ofs | 31 | 2,407 / 2,415 (0.996687) | 2,043 / 2,415 (0.845963) | 2,318 / 2,415 (0.959834) |
| vc09-2-ref | 31 | 2,407 / 2,415 (0.996687) | 2,043 / 2,415 (0.845963) | 2,318 / 2,415 (0.959834) |
| vc09-3-ofs | 9 | 771 / 772 (0.998705) | 528 / 561 (0.941176) | 596 / 561 (1.062389) |
| vc09-3-ref | 9 | 771 / 772 (0.998705) | 528 / 561 (0.941176) | 596 / 561 (1.062389) |
| vc09-4-ofs | 5 | 264 / 267 (0.988764) | 264 / 267 (0.988764) | 264 / 267 (0.988764) |
| vc09-4-ref | 5 | 264 / 267 (0.988764) | 264 / 267 (0.988764) | 264 / 267 (0.988764) |
| vc09-5-ofs | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-5-ref | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-6-ofs | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-6-ref | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-7-ofs | 6 | 359 / 360 (0.997222) | 359 / 360 (0.997222) | 359 / 360 (0.997222) |
| vc09-7-ref | 6 | 359 / 360 (0.997222) | 359 / 360 (0.997222) | 359 / 360 (0.997222) |
| vc09-8-ofs | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-8-ref | 4 | 252 / 253 (0.996047) | 252 / 253 (0.996047) | 252 / 253 (0.996047) |
| vc09-9-ofs | 0 | 32 / 32 (1.000000) | 32 / 32 (1.000000) | 32 / 32 (1.000000) |
| vc09-9-ref | 0 | 32 / 32 (1.000000) | 32 / 32 (1.000000) | 32 / 32 (1.000000) |
| vc12-stashed-loose | 23 | 2,289 / 2,297 (0.996517) | 1,350 / 1,547 (0.872657) | 1,573 / 1,547 (1.016807) |
| vc12-stashed-packed | 23 | 2,289 / 2,297 (0.996517) | 1,350 / 1,547 (0.872657) | 1,573 / 1,547 (1.016807) |
| vc12-noted-loose | 19 | 1,705 / 1,710 (0.997076) | 1,250 / 1,514 (0.825627) | 1,378 / 1,514 (0.910172) |
| vc12-noted-packed | 19 | 1,705 / 1,710 (0.997076) | 1,250 / 1,514 (0.825627) | 1,378 / 1,514 (0.910172) |
| vc12-fanned-loose | 498 | 263,578 / 263,391 (1.000710) | 32,981 / 48,290 (0.682978) | 36,841 / 48,290 (0.762912) |
| vc12-fanned-packed | 498 | 263,578 / 263,391 (1.000710) | 32,981 / 49,906 (0.660862) | 36,841 / 49,906 (0.738208) |

### Inherited proof, per native and release tier

| Proof | Loose | Packed | Named per mode |
|---|---:|---:|---:|
| Stash/notes complete-state cases / exact processes | 104 / 395 | 104 / 395 | 39 (44 captures) |
| Stash/notes clients | 19 | 19 | 0 |
| Blame commands / clients | 291 / 6 | 291 / 6 | 10 |
| Revision commands / clients | 183 / 49 | 183 / 49 | 8 |
| History commands / clients | 576 / 3 | 576 / 3 | 7 |
| Refs command/state | 632 | 632 | 17 |
| Merge/revert command/state | 132 | 132 | 12 |
| Replay scenarios (137 exact processes /157 captures) | 96 | 96 | 20 |

Stash/notes cases retain 61 stash +22 notes +20 original-corpus +1 subcommand diagnostic per mode. Pack reader: **2,442/2,442** objects across **34** fixtures (including 33 OFS and 33 REF entries), **141/141** structural/corruption/limit inputs. Main **190 =182 parity /7 named /1 shape**; fsck remains the strict not-yet witness.

Other inherited gates from the same log, per native/release tier: merge-file **1,521/1,521**, merge bases **84/84**; sequencer client **136/136**; refs client **14** with 1,002-ref enumeration; scorer **1,510 +24**; pairer **267**, full-state consumers **1,044**; basic diff **336/336**, endpoints **575/575**, terminal widths **90/90**, external diff API **12**, refresh **66/66**; hunks **676/684**, eight named differences; binary bodies **154/250**, 96 capture-bound representation differences, **250/250** forward/reverse application, four corrupt bodies rejected and 85 base85 symbols covered. These exceptions are not parity.

Index **212** commands /36 proven stat rows and five bounded checked programs; ignore **840/840**; worktree **207/207**; commit formatting **150/150** and CLI **51/51**; config **67** read-only CLI rows. Codec **1,099** loose objects +31 packed entries, **1,130** rewrites, 32 corrupt refusals, 250 fuzz rounds /1,250 calls and four checked programs. Object integration retains 22 malformed rows, 16 racing writers and its independent API/e2e checks. The 16-repository corpus rebuilt twice with identical OIDs. Pack-write, stash, blame, revision, pack, pretty, walk, refs, reflog and sequencer checked verdicts are exit(0); other checked captures are retained. The inherited local TLS checked-budget result remains **unsupported**, not a pass; no new skip was introduced.

### Independent spot-check and plant

`spot-check.py`/`spot-check.log` independently parse the retained worst-ratio similar-REF pack: idx/pack SHA-1, entry CRC32, REF reconstruction and all 24 canonical blob OIDs. Selected object `dc1cb16fc374e3fa5218db6a265bd9b3cf0d5fd6`, depth 4, body 7,611 bytes, matches captured Git cat-file and the importing client in the identical pack-only state. The measured size is independently 1,461 /1,044 =1.3994252873563218.

Plant draft **#33**, head `94c7d04`, run **40652913532**. Correct implementation committed first at `fa97baa`; the checksum break lives only on `vc13-plant-idx-checksum`. Intended red row: **`vc13 writer binary-none: validated pair publication`**, Linux `tools/check-pack-write`. Local `plant-local.log` and complete `plant-local.json` show exit 1, `Unsupported(pack index checksum)`, unchanged file/mode state. The single immediate lane CI read saw in_progress; no subsequent CI conclusion is claimed. The coordinator owns observing that exact red and closing the plant unmerged.

### Done-when

- [x] Prediction first; clean-room sections; twice-read pins and oracle digest.
- [x] Native/release writer interop, all-mode per-fixture size table, exact command/state rows, importing clients and bounded checked exit.
- [x] Publication/corruption/depth/policy witnesses, separate plant PR and local named red.
- [x] Sole complete inherited gauntlet, 448 unchanged inputs, repeated identical static build, retained full captures and independent spot-check.
- [x] README-only refresh and MAP/SOURCES; evidence-only `f6b0700`, followed by isolated CI-budget correction `d6b8532`.
- [x] Measured snapshot-cost fix, unchanged 1,002-object rows and size table, complete native/release pack gate plus legacy client and framing regressions; cap remains 60.
- [ ] Final main run ID read once, clean Mac worktree removal and canonical audit exactly once; results in lane hand-back.
- [ ] Coordinator checks PR-tier green, labels full-matrix at the final head, watches full tier and closes plant #33 by its named red.

No issue filed or closed. Preserve `/home/mfwolffe/lanes/vc13/den` and its evidence. The final job has exited and block A is released. No lane label or CI wait.

## Corrections

**Measured cost correction, `18d259f`; the cap stays 60.** Run **40724308949** cancelled `linux x86-64 (every gate)` at **16:16:46–17:17:11 UTC (60m25s)**. The hot path was the differential harness: after each per-object Git/client process it rehashed the entire repository, including all 1,000 worktree files. On hasu A, snapshot work took 129.929 seconds of the first vc09-14-ofs row and about 63.7 seconds of each later row. The actual writer took only 4.25–4.89 seconds; den read-back about 5.10 seconds; Git cat-file about 0.85 seconds per output mode. No full fixture was running on the checked machine. `performance-ci-cancelled.json`, the committed prediction and before-profile captures retain the diagnosis.

Measurements below are **seconds per completed PACK WRITE row**, same pinned container, **hasu cores 0–5 under the block-A lock**, with **1,002 objects in every row**. The first `none` row includes fixture inventory/reference-pack setup, explaining its previous roughly doubled cost. No fixture or comparison was removed.

| Input fixture | Output mode | Objects | Before s | After s | Before snapshot s | After snapshot s | Speedup |
|---|---|---:|---:|---:|---:|---:|---:|
| vc09-14-ofs | none | 1002 | 144.427 | 9.013 | 129.929 | 0.586 | 16.02× |
| vc09-14-ofs | ofs | 1002 | 75.993 | 9.284 | 63.711 | 0.349 | 8.19× |
| vc09-14-ofs | ref | 1002 | 76.226 | 9.457 | 63.921 | 0.351 | 8.06× |
| vc09-14-ref | none | 1002 | 143.925 | 8.980 | 129.589 | 0.572 | 16.03× |
| vc09-14-ref | ofs | 1002 | 75.932 | 9.203 | 63.466 | 0.352 | 8.25× |
| vc09-14-ref | ref | 1002 | 75.614 | 9.298 | 63.295 | 0.354 | 8.13× |

For `none` alone, excluding setup: vc09-14-ofs **75.224 → 8.604 seconds** (setup **69.202 → 0.410**); vc09-14-ref **74.881 → 8.625 seconds** (setup **69.044 → 0.356**). These are measured wall times, not a claim of faster production pack algorithms.

The fix batches read-only exchanges using Git's documented `cat-file --batch` framing and an importing-client batch mode. Every object still passes through `object.read_object`; its scratch is reclaimed per object, with **no checksum cache or production-reader change**. Strict framing checks validate every requested OID/type/size/body, canonical SHA-1, ordering, missing/extra records and trailing bytes; raw Git/client batch bytes also compare exactly. Every actual process retains stdout/stderr/status and a complete file/mode snapshot, with explicit before/after immutability assertions for reads. The 1,002-object inventories are now asserted explicitly. This reduces process boundaries and redundant full-tree snapshots, not the object proof.

The complete replacement pack gate passed **native and release**, each with **174 pairs /58 source fixtures /14,055 objects**, **1,439 exact command rows +39 named**, 14 publication captures and 22 adversarial cases/415 captures (including real depth-50 chains). Writer-harness process captures are now **1,134 per tier**, versus the historical 38,208; all 174 object/size rows are identical to the original table, including the **REF 1.399425** maximum. Git verify-pack/fsck remain clean and every object is byte-equal. Added framing vectors: **24 =6 valid +18 rejected**. Bounded checked delta verdict remains exit(0). The original single-object client separately passes **2,442/2,442** interop objects and **141/141** structural/corruption/limit cases on each tier.

The targeted runner (format/planner, complete pack gate on both tiers, legacy interop) completed **18:01:53–18:10:04 UTC, 8m11s**, ending `VC13 PERFORMANCE PACK GATE EXIT 0`; structural tests were then checked separately. `performance-counts.json` derives every row, retains the raw before/after/full captures and checks the unchanged size table; `performance-inputs.log` binds nine tested harness/workflow/pin files. `performance-before.log`, `performance-before-ref.log`, `performance-after.log`, `performance-pack-gate.log` and `performance-structural.log` are the evidence. Production code and the **60-minute timeout are unchanged**; README read, current. This is targeted follow-up proof, not a second full inherited gauntlet.

- **CI timeout, `d6b8532`:** labelled run **40692530972** was cancelled at the old 40-minute Linux job budget. `linux x86-64 (every gate)` ran **2026-10-28 13:05:29–13:45:48 UTC: 40 minutes 19 seconds**; its container step ran 40 minutes 4 seconds, and `tier full` failed after the cancellation. `notes/vc13-evidence/timeout-ci-run.json` retains the completed run/job metadata. Raise only that job's `timeout-minutes` from 40 to **60**. The new scoped planner assertion `T4 Linux full gauntlet has a 60-minute budget` fails against 40 (exit 1), then the entire planner suite passes against 60 (exit 0); `timeout-planner-red.log` and `timeout-planner-green.log` retain both. No production code, pack expectation, label or gate command changed; the coordinator owns the replacement full run.

- First command matrix exposed singular histogram output; `pack-command-initial-red.json.gz` preserves the mismatch, fixed to Git's `non delta: 1 object` without changing an expectation.
- Independent external binary-patch client failed to resolve the newly shared pack dependency. `shared-encoder-import-red.log` is retained; `1529c37` declares the module's dependencies. Targeted and final native/release/checked binary gates preserve all inherited exact/exception counts.
- The main fsck row initially failed because its old generic refusal metadata still named vc12. The new command refuses the measured commit-graph boundary precisely; before/Git/den captures are retained as `main-fsck-initial-*.json.gz`. The row now names that boundary and remains non-parity. No oracle output or repository path was normalized away.
- Initial writer snapshots duplicated large byte maps. Final snapshots store complete bytes once by content hash and reference complete file/mode maps. Other packed copies are removed only from the post-publication test copy before all-object reads, preventing a preexisting pack from masking the new writer. Existing identical pairs are valid no-op publications.
- The early expanded test had 38,150 writer processes and 1,409 command comparisons; adding the explicit no-delta Git baseline raised the original full-gauntlet counts to 38,208 and 1,439. The early no-delta/default ratio is retained, not retrofitted into a compression success. All 58 matched no-delta baselines were independently measured before the full gate.
- Early exploratory setup/build preconditions (container declaration, oracle exec path, client file API and Wolf region/map/field typing) were corrected before successful measurements; their transient terminal output is not presented as retained differential evidence. P5/P7 misses are listed above.

## vc14 draft

Continue M4 with housekeeping and the remaining validator surface before transports. Read Git's gc/repack/prune-packed/fsck/commit-graph documentation and pinned-binary observations only. Keep selection, construction, verified publication and removal separate: identify the reachable closure from refs/HEAD/index/reflogs, preserve unreachable data according to measured options, verify every new pair through the existing reader, then implement the measured `repack -d` cleanup ordering and failure recovery without deleting the last readable copy. Keep gc expiry/reflog/ref-packing effects separate from repack; refuse unmeasured options rather than approximate them.

Extend fsck with commit-graph validation and exact missing/corrupt/type/root diagnostics, and measure multiple dangling-tip output ordering before removing its refusal. Add crash/foreign-temporary/repeated-publication recovery witnesses and a larger repetitive/binary/mixed corpus; keep the REF 1.399425 headroom flag and per-fixture 1.5 gate visible. Use the single delta encoder, existing reader, object/ref/index parsers and immutable state captures; no new production Git/shell dependency. Native/release independent clients, bounded actual checked units, isolated CI plants and one full inherited gauntlet, every count named. Thin packs, multi-pack-index, bitmaps, cruft/.keep policy and transports remain named until separately measured. Inherited M2/M3 and stash/notes follow-ons remain open. Draft contract only, not an M4-complete claim.



