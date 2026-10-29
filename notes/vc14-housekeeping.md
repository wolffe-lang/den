# vc14 — M4 housekeeping

_Materialised from the body of den#37 at the merge (`2864f533`)._


## Forbidden

Clean-room Git 2.56.0 documentation and pinned-binary observations only. No Git/libgit2/other VCS implementation source read; no new production Git, shell, Python or codec dependency. No pin change, package installation, helper agent, planning/memory edit, attribution trailer, label, merge, tag, release or issue action. Builds/tests ran on hasu block B, cores 6–11 inside the rootless 12-GiB container under its per-run flock. Mac worktree used for git/evidence handling, not builds.

## Inputs verified

Base `516e238`; wolf 0.2.35 (wolf-lang `cf0c13d3`), lupin 0.1.56 (`28547b4`) and bundled std (`2386522e`) unchanged. Fresh release/ref/annotated-tag metadata and archive SHA256 read twice; staged binary/runtime/std compared with archives; pinned oracle executable SHA256 c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60 checked repeatedly through the existing fetch-oracle path. Proof is under notes/vc14-evidence/pins/.

Documentation sections: git-repack description and -a/-A/-d/-k/quiet/server-info/keep/cruft options; git-gc description/options/aggressive/expiry/concurrency notes; complete git-prune-packed page; git-fsck roots/full checks/reflogs/dangling/diagnostics/commit-graph controls; git-commit-graph verify/split/configuration; gitformat-commit-graph header/chunk table/OIDF/OIDL/CDAT/EDGE/generation overflow/optional Bloom and base chunks/trailer. docs/SOURCES.md records provenance. Existing object, tree/header, refs/reflog, index TREE and pack parsers remain shared; there is still one delta encoder.

- `99f6ef2` — prediction before measurements or implementation.
- `7a7e97a` — independent housekeeping contract and 52 complete oracle-only observations.
- `f8370af` — expose existing cache-tree parser identities without mutation.
- `90c4842` — verified orphan pack publication recovery.
- `9d6c065` — typed closure, bounded housekeeping/validator, independent clients and regressions.
- `3e902a3` — explicit immutable refusals for unmeasured repack forms.
- `54c912e` — mandatory CI gate, strict packed-fsck parity and larger writer corpus.
- `67bc352` — README-only refresh.
- `eafc082` — API map and clean-room sources.
- `a7f48a7` — rebuilt notes-only commit with the complete bank manifest instead of two approximately 98-MiB blobs.
- `a58608c` — measured absent-first/present-second parent-slot fix and regression.
- `b34baf9` — README-only validator count refresh.
- `9b23045` — corresponding MAP count.
- `4cd291e` — parent-slot proof and replacement-gauntlet recipe; final functional head.
- `0eb5712` — final bank-bound counts, size table, log and unchanged-input proof only.
- `08223f9` — CI-budget prediction and per-file measurement of the cancelled labelled run (R-vc14-4).
- `62f7eaa` — Linux every-gate job `timeout-minutes` 60 → 90 and its planner invariant (T4).
- `2864f53` — per-file CI timings, comparison summary and the planner red/green proof.

### Implemented recommendations and boundaries

**R-vc14-1: conservative duplicate-only retirement now; gc remains distinct.** `repack -a -n -q`, optionally -d, selects the typed closure from refs, HEAD, both reflog endpoints and index entries/cache trees. Construction, publication, read-back and removal are separate. Every replacement passes the existing reader before removal. Without -k, an old packed object outside the replacement causes a prepublication refusal; -k with -d retains all old loose/packed objects. A synced retirement record supports restart after pack-before-idx removal, revalidating replacement and old index bindings. Empty old packs may be retired without a replacement. Foreign temporaries and incomplete/foreign records are preserved and refused. Ordinary den lookup may refuse on an obsolete idx without its pack until repack recovery; the verified replacement remains independently readable. No multi-file atomicity is claimed.

`prune-packed` verifies packed copies before loose removal and removes empty fanout directories. Publication recovery can restore a missing idx only by validating the existing orphan pack against the newly constructed idx. GC expiry, reflog expiry, ref packing and commit-graph writing are not silently implemented by repack.

**R-vc14-2: preserve physical enumeration where it is observable.** Prune-packed dry-run uses ascending hex prefixes and raw within-directory order. Two copied directories can enumerate differently, so both read-only tools run on one immutable physical fixture. Outputs are not sorted or normalized. Housekeeping retains every raw file/mode snapshot; R4c compares validated pack pairs, per-pack object membership and canonical all-object bytes rather than pack hash/encoding identity. Optional reverse-index representation remains recorded; every nonrepresentation path is exact.

**R-vc14-4: raise only the Linux every-gate budget, 60 → 90 minutes; keep every new gate.** The labelled run 40790946960's every-gate job was cancelled at `timeout-minutes: 60`, not failed by a test. Per-file windows from its log against trunk's (notes/vc14-evidence/ci-budget-per-file.tsv, ci-budget-comparison.json): vc14's additions measured **17m43s** — housekeeping gate **7m01s** (420.541 s), expanded writer rows **7m21s** (440.697 s across both tiers), new command fixtures **3m22s** (201.925 s). Unchanged gates ran **1.053×** (median of 15 comparable windows, range 1.023–1.214); shared writer rows 1.004/1.031, shared command fixtures 1.000/0.988. The displacement is the added coverage, not a uniform runner slowdown. Projections: 62m25s (scaled tail), 66m02s (doubled tail); 90 leaves about 24 minutes over the latter, without claiming a guaranteed CI time. Fixtures, modes, comparisons and captures are retained; nothing is split or trimmed. Planner proof: `ci/tiers-test.py` with the updated T4 invariant fails exactly one check (`T4 Linux full gauntlet has a 90-minute budget`) against a workflow at 60 and passes every check at 90 (ci-budget-planner-red.log / -green.log; reproduced byte-identically from `git archive 2864f53`). Production code, pins, tools/gate and differential expectations are unchanged; the next labelled CI run is the completion verdict for the setting.

**R-vc14-3: bounded validator diagnostics, not a blanket fsck claim.** Single-file commit graphs validate framing, required chunks, OID fanout/order, parent/EDGE positions, generation overflow, checksum and canonical commit metadata. Missing/corrupt/type/root diagnostics preserve measured exit bits. The absent-first/present-second parent-slot witness originally returned a false clean verdict; it now matches Git's exit 16 and early-termination diagnostic. Multiple dangling/missing ordering, multiple broken-link ordering, malformed refs and unmeasured combinations remain named, as do split/Bloom/unknown chunks and strict/configured fsck. The main packed fsck row now requires exact parity.

Named remaining: gc, incremental repack, -A, server-info updates, nonquiet repack, -k without -d, unique unreachable-object retirement without preservation, thin packs, multi-pack-index, bitmaps, cruft/.keep policy and transports. All inherited M2/M3/editor/merge/replay/blame/stash/notes limitations remain open. **No M4-complete claim.**

## Prediction

The committed prediction remains unchanged. Shared parsers and the existing writer/reader sufficed; no second delta encoder was needed. Closure and verified publication/removal are separate, and the larger fixtures remain under every 1.5 size gate. The first 1,000-file repack rows measured about 1.6–2.0 s; final native verified-deletion/repeated-read rows topped out at 13.966 s, release at 10.268 s. New rows were measured before gate integration. The Linux CI timeout stayed at 60 minutes until the labelled run was cancelled by it; notes/vc14-evidence/ci-budget-prediction.txt (`08223f9`) predicted, before the change, that the updated T4 assertion fails against 60 and passes at 90, which held (R-vc14-4).

Misses retained rather than hidden: Git removes empty loose fanout directories and redundant empty packs; dry-run ordering is physical rather than sorted; graph generation/parent/fanout diagnostics needed additional observations; diagnostic paths use .git at the repository root. Multiple dangling ordering changed between loose, packed and duplicate storage and remains refused. The post-gauntlet malformed-parent probe exposed a real false-clean bug, so the coordinator required a code fix and replacement full gauntlet. The initial exploratory probe omitted GIT_EXEC_PATH and is retained separately; only the corrected complete pinned environment supplied the exit-16 oracle result.

## Evidence index

### Final-head verification and lossless banks

The original full gauntlet was green at the subsequently rewritten notes-only head. Rebuilding that notes commit changed **zero of 392 non-notes inputs**, verified independently from both Git trees against the original SHA256 manifest; rewrite-input-equality.json retains both maps. It removed the two large blobs from the vc14 ancestry, not merely from the tip. Exactly one force-with-lease published that requested rewrite. Before the final ordinary push, the introduced object set contained **no blob over 10 MiB**; that same checked head was published.

The parent-slot code fix then required a replacement full run, explicitly authorized by the coordinator. Final functional head `4cd291e`, hasu block B, **2026-10-28 22:34:26–23:14:54 UTC (40m28s)**:

```
VC14 GAUNTLET-V2 EXIT 0
VC14 FUNCTIONAL INPUTS UNCHANGED 392
VC14 FINAL-V2 EXIT 0 2026-10-28T23:14:54Z
```

notes/vc14-evidence/final-v2.log, final-v2.exit, gauntlet-v2.exit and final-inputs.json bind this result. `0eb5712` changes notes/evidence only; a zero non-notes diff against `4cd291e` preserves that coverage. No further production/test/gate edit followed the run. Since then the head moved only by R-vc14-4: `.github/workflows/ci.yml` (one `timeout-minutes` line) and `ci/tiers-test.py` (its T4 invariant), plus notes/vc14-evidence/ci-budget-*; the local gauntlet does not exercise a CI setting, so the planner red/green and the next labelled run carry that change. README was read and refreshed in its own commits.

The original bank at /home/mfwolffe/lanes/vc14/evidence-bank/ is unchanged. Its 6,100 complete files were verified by two matching SHA256 reads and lossless decompression. The **new head-specific bank** is /home/mfwolffe/lanes/vc14/evidence-bank/4cd291ef291242b7d2c215aba1b08979834df554/: **6,614 complete files**, 2,345,421,346 original bytes stored losslessly in 36,480,032 bytes. It includes root and nested reports, all target/runs artifacts, raw component logs and reproduction inputs. No row, comparison, file-state path or output byte was dropped.

The small committed bank-manifest-v2.json.xz (290,692 bytes) contains every bank path, size, both SHA256 reads and original size/hash; bank-summary-v2.json explains reconstruction. Its SHA256, read twice identically, is 657ea4a0e4bbbe86e2afe0946514804596a0c5b48e57d757610f9c272c1ef9c7. Decompress the manifest, then `xz -dc` any listed path to reconstruct the whole original. The original bank-manifest hash remains 593a0909692563f41f85af877d682ce0b677a30a9381e1795fb40e09534c76ef. Banks and the hasu checkout must be preserved.

final-v2-counts.py derives counts only from SHA-bound replacement reports; final-v2-counts.json records the complete census. final-v2-pack-sizes.tsv includes every fixture/mode on both tiers, including each no-delta/default-Git ratio. A reviewer can spot-check the new malformed-parent row in the bank's repository/target/validator-native-final.json.xz: label `absent first parent with present second slot`, Git and den exit 16, identical diagnostics and immutable state.

Static Linux builds repeated identically: full **16,157,968 bytes**, SHA256 e253b1f11cd6a1ca74846b8428970c49242458cffe0d9bb6d5463bff2c406444; stripped **2,583,928 bytes**, SHA256 36a6f0be5a9d4bef18df14eafb49a2dfdf85a5f8e5f32e293ac1f4dd1c3d9419.

### New/pack proof — per native and release tier

| Proof | Final count |
|---|---:|
| Source fixtures / none-OFS-REF pairs / canonical object comparisons | 61 / 183 / 15,207 |
| Complete writer process captures | 1,578 |
| Exact immutable pack-command comparisons / separate named refusals | 1,538 / 30 |
| Publication failure/repeat and CLI process captures | 14 (8 failure/repeat cases + CLI publication) |
| Adversarial cases / process captures | 22 / 415 |
| Real chain witnesses | OFS 75 objects and REF 75 objects, each depth 50 |
| Housekeeping command/semantic-state rows | 56 exact + 4 named immutable refusals |
| Fsck validator commands / independent metadata clients | 41 exact immutable / 3 |
| Recovery process captures | 72; five interruption phases, two foreign-file cases, repeated cleanup, orphan publication, closure and seven option refusals |
| Strict batch framing vectors | 24 |
| New actual-checked parser | exit(0), six bounded groups; zero skips |

Recovery captures are not 72 porcelain-parity claims. Every new replacement is independently validated; loose duplicates cannot mask pack corruption. Complete read-only batches still compare every object and retain before/after state once per actual process.

### Inherited differential fixtures — each storage mode, per native and release tier

| Family | Loose | Packed | Named per mode |
|---|---:|---:|---:|
| Stash/notes cases / exact processes | 104 / 395 | 104 / 395 | 39 (44 separate captures) |
| Stash/notes clients | 19 | 19 | 0 |
| Blame commands / clients | 291 / 6 | 291 / 6 | 10 |
| Revision commands / clients | 183 / 49 | 183 / 49 | 8 |
| History commands / clients | 576 / 3 | 576 / 3 | 7 |
| Ref command/state rows | 632 | 632 | 17 |
| Merge/revert command/state rows | 132 | 132 | 12 |
| Replay scenarios / exact processes | 96 / 137 | 96 / 137 | 20 (157 total process captures per mode) |

Each stash/notes mode retains 20 original-corpus cases. Pack reading independently compares **2,442/2,442 objects across 34 fixtures**, with **141/141** structural/corruption/limit cases and all six entry kinds, including 33 OFS and 33 REF entries per tier. Main matrix: **190 = 183 parity + 6 named not-yet + 1 version-shape**.

### Other final component families — per native/release tier

- Merge-file 1,521/1,521; merge bases 84/84; sequencer importing client 136 rows; refs client 14 rows.
- Similarity 1,534/1,534: initial 123, random 300, hash 522, structural 90, equivalence 301, wrap 174, new-collision corpus 24. Pairing 267; complete-state consumers 1,044/1,044.
- Basic diff 336; endpoints/pathspecs 575; terminal widths 90; external API 12; refresh 66. Hunk bytes **676/684**, with the original eight named differences, not parity.
- Binary bodies **154/250**, with 96 capture-bound representation differences. All 250 forward/reverse applications and 250 CLI envelopes pass; four corrupt bodies rejected, 85 base85 symbols covered. The strict byte report remains visibly red/report-only, not recast as a pass.
- Index 212 command rows / 36 independently proven stat rows, plus five bounded checked programs. Ignore 840/840 plus the independent filesystem client. Worktree 207/207.
- Commit formatting 150 API comparisons (not CLI parity); commit 51 exact CLI rows; ref/publication harness 35 captured process records. Config 67 read-only CLI assertions per tier plus scalar init integration and checked parser; these are scripted assertions, explicitly not Git-oracle measurements.
- Codec 52 vectors / 2,272 calls; 1,099 loose objects + 31 pack entries, 1,130 rewrites, 32 corrupt refusals over the rebuilt 16-repository corpus. Fuzz 250 rounds / 1,250 calls per tier; the same seed/input hash, 78 accepted and 672 rejected mutations. Four checked codec programs pass.
- Object integration: 14 captured integration rows, 22 malformed rows, 16 racing-writer iterations per tier, with independent API/e2e checks. The corpus rebuilt twice with identical OIDs.
- All 34 top-level retained checked verdicts and the nested config checked verdict are exit(0). The inherited local TLS checked mem-budget result remains unsupported, not a pass. No new skip was introduced.

### Every per-fixture pack size

Native/release tables are identical. Each cell is **den bytes / Git bytes (ratio)**. N is no-delta against Git explicitly given --window=0 --no-reuse-object; O/R use default-window/default-depth OFS Git. All matched-mode ratios are <=1.5. Only .pack bytes are tabulated; companions are independently validated. **REF's inherited worst remains 1.399425 (1,461/1,044), only 0.100575 below the ceiling.** The diagnostic no-delta/default-Git ratios remain visible in the TSV: similarity 12.254789 and new binary 25.296093 are not default-compression successes.

| Fixture | Objects | N den/Git (ratio) | O den/Git (ratio) | R den/Git (ratio) |
|---|---:|---:|---:|---:|
| binary | 5 | 553/554 (0.998195) | 553/554 (0.998195) | 553/554 (0.998195) |
| empty | 2 | 162/162 (1.000000) | 162/162 (1.000000) | 162/162 (1.000000) |
| linear | 31 | 2407/2415 (0.996687) | 2043/2415 (0.845963) | 2318/2415 (0.959834) |
| m2-amend | 9 | 771/772 (0.998705) | 528/561 (0.941176) | 596/561 (1.062389) |
| m2-edited-rename | 5 | 264/267 (0.988764) | 264/267 (0.988764) | 264/267 (0.988764) |
| m2-ignore | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| m2-index-v4 | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| m2-modes | 6 | 359/360 (0.997222) | 359/360 (0.997222) | 359/360 (0.997222) |
| m2-staged-rename | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| m2-unborn | 0 | 32/32 (1.000000) | 32/32 (1.000000) | 32/32 (1.000000) |
| merge | 12 | 1082/1086 (0.996317) | 757/882 (0.858277) | 868/882 (0.984127) |
| packed | 31 | 2407/2415 (0.996687) | 2043/2415 (0.845963) | 2318/2415 (0.959834) |
| rename | 6 | 479/481 (0.995842) | 408/481 (0.848233) | 445/481 (0.925156) |
| symlink | 5 | 298/299 (0.996656) | 298/299 (0.996656) | 298/299 (0.996656) |
| thousand | 1002 | 37693/36739 (1.025967) | 37693/36739 (1.025967) | 37693/36739 (1.025967) |
| two | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| similar | 24 | 12794/12821 (0.997894) | 1026/1044 (0.982759) | 1461/1044 (1.399425) |
| den-origin | 9 | 653/653 (1.000000) | 543/653 (0.831547) | 580/653 (0.888208) |
| vc14-repetitive | 128 | 264037/267891 (0.985614) | 4635/13194 (0.351296) | 7047/13194 (0.534106) |
| vc14-binary | 128 | 6146976/6147616 (0.999896) | 50597/243001 (0.208217) | 53008/243001 (0.218139) |
| vc14-mixed | 128 | 3205506/3207754 (0.999299) | 52640/153176 (0.343657) | 55031/153176 (0.359266) |
| vc09-0-ofs | 5 | 553/554 (0.998195) | 553/554 (0.998195) | 553/554 (0.998195) |
| vc09-0-ref | 5 | 553/554 (0.998195) | 553/554 (0.998195) | 553/554 (0.998195) |
| vc09-1-ofs | 2 | 162/162 (1.000000) | 162/162 (1.000000) | 162/162 (1.000000) |
| vc09-1-ref | 2 | 162/162 (1.000000) | 162/162 (1.000000) | 162/162 (1.000000) |
| vc09-10-ofs | 12 | 1082/1086 (0.996317) | 757/884 (0.856335) | 868/884 (0.981900) |
| vc09-10-ref | 12 | 1082/1086 (0.996317) | 757/884 (0.856335) | 868/884 (0.981900) |
| vc09-11-ofs | 31 | 2407/2415 (0.996687) | 2043/2415 (0.845963) | 2318/2415 (0.959834) |
| vc09-11-ref | 31 | 2407/2415 (0.996687) | 2043/2415 (0.845963) | 2318/2415 (0.959834) |
| vc09-12-ofs | 6 | 479/481 (0.995842) | 408/481 (0.848233) | 445/481 (0.925156) |
| vc09-12-ref | 6 | 479/481 (0.995842) | 408/481 (0.848233) | 445/481 (0.925156) |
| vc09-13-ofs | 5 | 298/299 (0.996656) | 298/299 (0.996656) | 298/299 (0.996656) |
| vc09-13-ref | 5 | 298/299 (0.996656) | 298/299 (0.996656) | 298/299 (0.996656) |
| vc09-14-ofs | 1002 | 37693/36739 (1.025967) | 37693/36739 (1.025967) | 37693/36739 (1.025967) |
| vc09-14-ref | 1002 | 37693/36739 (1.025967) | 37693/36739 (1.025967) | 37693/36739 (1.025967) |
| vc09-15-ofs | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-15-ref | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-16-ofs | 91 | 10924/10358 (1.054644) | 5245/6734 (0.778883) | 6339/6734 (0.941342) |
| vc09-16-ref | 91 | 10924/10358 (1.054644) | 5245/6736 (0.778652) | 6339/6736 (0.941063) |
| vc09-2-ofs | 31 | 2407/2415 (0.996687) | 2043/2415 (0.845963) | 2318/2415 (0.959834) |
| vc09-2-ref | 31 | 2407/2415 (0.996687) | 2043/2415 (0.845963) | 2318/2415 (0.959834) |
| vc09-3-ofs | 9 | 771/772 (0.998705) | 528/561 (0.941176) | 596/561 (1.062389) |
| vc09-3-ref | 9 | 771/772 (0.998705) | 528/561 (0.941176) | 596/561 (1.062389) |
| vc09-4-ofs | 5 | 264/267 (0.988764) | 264/267 (0.988764) | 264/267 (0.988764) |
| vc09-4-ref | 5 | 264/267 (0.988764) | 264/267 (0.988764) | 264/267 (0.988764) |
| vc09-5-ofs | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-5-ref | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-6-ofs | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-6-ref | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-7-ofs | 6 | 359/360 (0.997222) | 359/360 (0.997222) | 359/360 (0.997222) |
| vc09-7-ref | 6 | 359/360 (0.997222) | 359/360 (0.997222) | 359/360 (0.997222) |
| vc09-8-ofs | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-8-ref | 4 | 252/253 (0.996047) | 252/253 (0.996047) | 252/253 (0.996047) |
| vc09-9-ofs | 0 | 32/32 (1.000000) | 32/32 (1.000000) | 32/32 (1.000000) |
| vc09-9-ref | 0 | 32/32 (1.000000) | 32/32 (1.000000) | 32/32 (1.000000) |
| vc12-stashed-loose | 23 | 2289/2297 (0.996517) | 1350/1547 (0.872657) | 1573/1547 (1.016807) |
| vc12-stashed-packed | 23 | 2289/2297 (0.996517) | 1350/1547 (0.872657) | 1573/1547 (1.016807) |
| vc12-noted-loose | 19 | 1705/1710 (0.997076) | 1250/1514 (0.825627) | 1378/1514 (0.910172) |
| vc12-noted-packed | 19 | 1705/1710 (0.997076) | 1250/1514 (0.825627) | 1378/1514 (0.910172) |
| vc12-fanned-loose | 498 | 263578/263391 (1.000710) | 32981/48290 (0.682978) | 36841/48290 (0.762912) |
| vc12-fanned-packed | 498 | 263578/263391 (1.000710) | 32981/49906 (0.660862) | 36841/49906 (0.738208) |

### Isolated CI plants

Draft #35, graph-checksum inversion, run **40770619458**, intended validator `root valid` assertion. Draft #36, omitted duplicate removal, run **40770750891**, intended `large-mixed-source-False-2` nonrepresentation-state assertion. Each is the committed correct line plus one deliberate break on its own vc14-plant branch, never part of this PR. The coordinator observed both intended CI reds and owns their unmerged closeout. The lane read each initial run once, did not wait or label, and removed both clean plant worktrees individually.

## Done-when

- [x] Prediction first, documentation-only clean room, twice-verified unchanged pins.
- [x] Shared typed closure, separate verified construction/publication/removal, restart/foreign-file/repeat witnesses.
- [x] Single-file graph validation and exact bounded diagnostics; post-run false-clean counterexample fixed and independently regressed.
- [x] Native/release clients and complete captures, six actual-checked groups, larger repetitive/binary/mixed corpus and every 1.5 gate.
- [x] Original run retained; coordinator-authorized replacement full gauntlet green at final functional inputs; 392 unchanged hashes; repeated identical static build.
- [x] Complete lossless head-specific bank, each SHA read twice, original bank unchanged; oversized blobs absent from branch ancestry; final push ordinary.
- [x] README-only refreshes, MAP/SOURCES, all fixture-family counts and every size row recorded.
- [x] Main PR #37 run ID read once immediately: **40790315850**, observed in_progress at head 0eb5712f34b7617682b68282d6fb4d1295b7a091. No CI wait or label.
- [x] Labelled run 40790946960 cancelled by the 60-minute Linux budget; R-vc14-4 measured and applied (`08223f9`, `62f7eaa`, `2864f53`); planner T4 red at 60, green at 90.
- [x] PR #37 run ID at head 2864f5339513a2744af1771233565b756ef2f5c1 read once: **40813941202**, in_progress. No CI wait or label.
- [x] Clean main Mac worktree removed individually. Canonical audit invoked exactly once, exit 1; exact last line: **AUDIT FAIL (footprint: cross-cutting)**. Only pending merge-gate requirements failed: head CI still running, no completed green tier, and coordinator-owned full-matrix label absent. Ancestry, attribution, footprint, PR head, five sections, untouched spec, 19 cited SHA resolutions, worktree/orphan checks passed.
- [ ] Coordinator verifies PR-tier green, adds full-matrix at the final head, watches full tier, performs a bank-artifact spot-check and handles plants #35/#36.
- [ ] Named: gc/expiry/ref-packing, remaining repack forms, unique unreachable retirement, complex fsck ordering/forms and all inherited follow-ons. No milestone-completion claim.

No issue filed or closed; none newly requested for this bounded pass. Preserve /home/mfwolffe/lanes/vc14/den and both evidence banks. The completed jobs have exited and block B is released. No .md lane report was written; this five-section body is the materialization source.

### vc15 draft

Continue M4 before transports. From Git documentation and the same pinned binary, measure and implement the remaining housekeeping policy in distinct stages: incremental repack and -A/unreachable loosening, server-info and nonquiet output, then gc's ref packing, reflog expiry, recent-object protection, object expiry and commit-graph-writing effects. Never turn gc into an alias for repack or silently drop the last readable copy. Keep the duplicate-only safe subset until each broader retention/expiry policy has a complete witness, including failure ordering and restart/concurrent-publication cases. Add options only when their behavior has been measured; preserve .keep/cruft/bitmap/multi-pack-index/thin/transport refusals until separately contracted.

Expand the bounded validator with measured multiple dangling/missing ordering across loose/packed/duplicate stores, malformed refs and remaining typed-link diagnostics, parent-count/edge combinations and split/Bloom graph policy. Reuse the same object/index/ref/reflog/graph parsers and delta encoder. Keep the absent-first/present-second regression and all immutable error captures. Retain all 61 writer fixtures, the narrow REF 1.399425 headroom warning and every per-fixture 1.5 gate; profile any new per-object row on the largest fixture before integration so the Linux job stays within its 90-minute budget (R-vc14-4). Native/release external clients, actual-checked bounded units, isolated CI plants and final-head full proof remain mandatory. Bank complete large captures losslessly with twice-read hashes and small manifests; do not place oversized blobs in Git history. All inherited M2/M3 and stash/notes follow-ons remain named, and no M4-complete claim precedes those measured gates.


