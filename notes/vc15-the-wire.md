# vc15 — the wire

Materialised by the orchestrator from PR #39's body at the merge (trunk `de407e61`, 2026-11-03).

Footprint: cross-cutting

## Forbidden

Documentation and pinned-binary clean room only; no Git/libgit2/other VCS implementation source or sample-hook content read. Den's parsers, codecs, object/ref decisions and checkout remain wolf code. File endpoints execute an argv-vector service, never a shell command. Independently compiled native den services prove self-hosted clone/push with empty PATH/GIT_EXEC_PATH. No pins changed, host packages installed, attribution trailer, label, merge, tag or issue action.

## Inputs verified

Base `13bc2caa`; unchanged wolf 0.2.36 `5adf3d91`, lupin 0.1.58 tag `6240efe5`, std `78b9d3cb`, Git 2.56.0 executable SHA256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`. Fresh release/tag metadata, whole Linux/Mac archives and staged binaries/runtime/std were verified twice; every std file matches the pinned Git tree. `notes/vc15-evidence/pins/` retains inputs, procedure, both platform manifests and summaries. The Mac oracle entry is a checksum of the copied Linux executable, not a Mac oracle execution.

Published manuals: gitprotocol-common/v2/pack/capabilities, gitformat-pack, and the existing packed-ref/repository layout specification. `docs/SOURCES.md` records sections. Shared object/tree/header/ref/index/checkout/hash/inflater/delta code remains the data path.

- `0c9fc7e` — prediction first.
- `780c278`, `4aeda63` — precommitted framing/received-stream rows and decoder.
- `24923ed`, `0a8aa5b`, `1eab60c` — atomic prediction, independent failure client, single commit point.
- `6a30496`, `114d9ab` — push/receive policies/status and deletion/capability constraints.
- `375aaed`, `dcf79dc`, `b623b99` — shared normal checkout, include-tag, explicit write-service opt-in.
- `84a994b`, `c475957` — native service peers without external tools on PATH.
- `31ae4b4`, `55d109b` — mandatory wire gate and real Git OFS/REF/thin/malformed streams.
- `19ab458` — bound URLs before acquiring transport resources.
- `1d185d7`, `d599a7b`, `df3bc84` — README, API map and sources.
- `c3e389f` — positive fast-forwards, non-atomic sibling outcomes, packed atomic targets/deletes, stale/foreign-lock immutability and export/write confinement.
- `c5e8037` — mandatory PR planner wire invariant/path coverage; superseded intermediate head.
- `405875f`, `ea2e0ee` — R4 prediction and observed-red custom-namespace rewind row.
- `58d4c77`, `7c6b3dc` — retained creation/delete/no-op/force assertions and the conservative guard.
- `51208a4`, `de407e6` — README/source-policy follow-on note; final source head `de407e6118f93e3e2d2fb4ee16be10ddb29c12a3`.

## Prediction

Implemented recommendations:

- **R-vc15-1:** emit canonical outbound LF, accept optional inbound LF. Alternative server-rejection assertions were rejected because the manual requires acceptance. The plant fails the declared outbound-byte policy by name; both real peers also accept missing input LF.
- **R-vc15-2:** conservative explicit bounds/refusals, no unsupported optional capability advertised. Alternative broad compatibility claims from happy paths were rejected. Atomic is withdrawn for the unimplemented reflog policy; URL bounds precede descriptor acquisition.
- **R-vc15-3:** one packed-ref logical commit point, not sequential loose renames called atomic. Reserve every target and packed-refs; preserve all old target values while removing equivalent loose shadows; rename the prepared new snapshot once. Precommit failure leaves every logical ref old. No reflog transaction, crash-lock recovery or reader snapshot-isolation claim.
- **R-vc15-4/A:** refuse non-forced updates outside refs/heads and refs/tags by name until the broader typed commit/tag/tree/blob peeling policy is measured. Creations, deletes, unchanged values and explicit `--force`/`+` remain. The alternative full policy is a follow-on for the coordinator to file at merge; no issue was filed by this lane.

The M5 contract superseded vc14's advisory M4 draft. Existing M2/M3/M4 gaps remain open. This is bounded explicit URL/refspec/quiet transport support, **not an M5-complete or general Git CLI/error-message parity claim**.

## Evidence index

### Verified targeted proof

At `de407e6`, kasumi's locked rootless Linux container: **46 named peer/policy groups per native and release tier**, plus **17 received-stream groups per tier** (four real Git none/OFS/REF/external-base thin modes and thirteen malformed/strict-input cases). Every `tools/check-wire` step was exit 0. Both actual-checked programs reached run and returned `exit(0)`, zero warnings/diagnostics/skips.

The peers cover file/git clone/fetch/push in both directions; normal checkout; quiet success bytes; canonical object bodies, refs, index/worktree and fsck; positive fast-forwards, force, deletes and mixed no-op/delete requests; atomic versus non-atomic server policy outcomes; loose/packed atomic targets, mixed delete/update, precommit injection, stale IDs and preserved foreign locks; include-tag without a tag want; optional input LF; native self-hosting without external tools; and canonical export/administrative escape, export-marker and write-opt-in refusal.

Complete raw argv/selected environment/stdin/stdout/stderr/status, daemon teardown, streams and fixture repositories remain under `target/runs/wire-*` / `wire-pack-*`. Quiet success bytes are distinct from object/ref comparisons. Error text and wider porcelain/configuration policy are named limits, not exact-parity rows. Git index-pack's trailing-stdin behavior is recorded separately from den's exact-stream API refusal.

No earlier red was relabelled green: initial missing modules, missing comments, E0401 byte narrowing, affine map/list ownership, explicit take modes and borrow scopes have complete retained preflight logs. The named plant diagnostic is explicit because native assertion traps omit custom assertion messages.

### R4 red first and replacement final head

The regression at `ea2e0ee` failed in its own peer row, after every earlier build/unit/service step passed:

```
AssertionError: unforced custom-namespace rewind must refuse
END native-wire-peers exit=1
END wire-surface exit=1
END r4-red-reboot1 exit=1
```

The raw process captures prove the counterexample: pinned Git rejected `refs/heads/old:refs/custom/item` with exit 1/non-fast-forward; old den accepted that same rewind with exit 0 and empty output. The guard was committed only after reading that red. The new `r4-green` run at de407e6 passes both complete peer tiers and both actual-checked programs, including retained creation, deletion, unchanged-value and explicit-force behavior.

The c5e8037 full inherited gauntlet completed green after reboot requeue, but is **intermediate and superseded**, not evidence for the later guard. Its `full-gauntlet`, `final-inputs-after`, `final-lossless-bank` and `host-final` END lines are all exit 0. Its complete bank is retained under `/home/mfwolffe/lanes/vc15/evidence-bank/c5e8037462993becd8486768f78b8120a1ffc900/`: 1,337,528,876-byte archive, both SHA256 reads `b89da81649649c1b59fedeaaa98abc25d194fe5cfbc2908867afb2a8575a1a14`. CI 41532892251 is the coordinator-observed green for that old head, not this new one.

New frozen head: `de407e6118f93e3e2d2fb4ee16be10ddb29c12a3`. One replacement complete gauntlet is being submitted as `final-de407e6`, with log `/home/mfwolffe/lanes/vc15/final-de407e6.log`, marker `/home/mfwolffe/lanes/vc15/final-de407e6.exit` and head-specific bank `/home/mfwolffe/lanes/vc15/evidence-bank/de407e6118f93e3e2d2fb4ee16be10ddb29c12a3/`. It checks committed inputs before/after execution and retains a twice-hashed lossless target/notes bank. **Replacement final-head full gauntlet is GREEN**, marker 0; runner PID 1548012 and lock holder 1548026 have completed. All 439 committed inputs match before/after. The complete bank has 616,281 members and a 1,298,840,815-byte archive; both SHA256 reads are `9b668d9402b5cbacde8a4d3fb2b293acb0bc73dadb3a84716d1684f99ab101e9`. Final completion: 2026-11-03T03:47:39Z. New-head tier-pr run [41569027591](https://github.com/wolffe-lang/den/actions/runs/41569027591) was read once as in_progress and its watch handed off.

### Every final END line

The missing-wire planner invariant is the deliberately observed scratch red; its verification step is 0. All real final steps are 0.

```
END final-inputs-before exit=0
END final-unchanged-pins exit=0
END planner-missing-wire-invariant exit=1
END final-planner-red exit=0
END native-wire-build exit=0
END native-wire-unit exit=0
END native-pack-stream-build exit=0
END native-pack-stream-unit exit=0
END native-wire-client-build exit=0
END native-atomic-client-build exit=0
END native-upload-service-build exit=0
END native-receive-service-build exit=0
END native-wire-peers exit=0
END native-received-pack-peers exit=0
END release-wire-build exit=0
END release-wire-unit exit=0
END release-pack-stream-build exit=0
END release-pack-stream-unit exit=0
END release-wire-client-build exit=0
END release-atomic-client-build exit=0
END release-upload-service-build exit=0
END release-receive-service-build exit=0
END release-wire-peers exit=0
END release-received-pack-peers exit=0
END actual-checked-wire exit=0
END actual-checked-pack-stream exit=0
END full-gauntlet exit=0
END final-inputs-after exit=0
END final-lossless-bank exit=0
END host-final exit=0
```

Static Linux builds repeated identically: full **17,134,120 bytes**, SHA256 `f1f527f08e756b3ebf761d19b303fe7faf5e4c771beeea2f6cae53a551364b6a`; stripped **2,960,632 bytes**, SHA256 `3dede74ad5f0b02313d4687664ad3e83ecb2b9e8e945d46fb901521fbf6e4ab0`.

### Isolated plant

`vc15-plant-want` / draft #40 changes only want encoding to omit LF, off the main line. Old head 1596c73 has an exact local named red and coordinator-observed CI named red 41533675798 in Linux/tier pr. It was re-cut once on the new final head: `791305e699a408b950737cb26493041e2beb32f1`. New run [41569146558](https://github.com/wolffe-lang/den/actions/runs/41569146558) was read once as in_progress and its watch handed off without a lane CI wait. No claim that Git rejects optional LF is made.

## Done-when

- [x] Prediction first, documentation-only clean room, unchanged pins twice verified.
- [x] Native/release protocol/object/ref/checkout peers and independent clients; actual checked parsers; zero new skips.
- [x] README read completely and refreshed in its own commit; API map and sources current.
- [x] Source/test concerns committed separately; no attribution trailers or oversized introduced blobs.
- [x] Draft main PR; no label or merge requested.
- [x] Published isolated missing-LF draft #40; old-head named red observed locally and in CI.
- [x] New-head plant pushed once; run 41569146558 watch handed off.
- [x] Complete final-head inherited gauntlet, every END line and lossless bank verified.
- [x] Final head run 41569027591 read once; CI watch handed off.
- [ ] Canonical lane audit exactly once at final head.
- [ ] Coordinator owns PR/full-tier verdicts, label, merge and plant closeout.

No issue filed or closed. Remaining named: broader typed-peeling/update policy outside heads/tags, remote-name/default-refspec/pull forms, general failure-output parity, configured hook/non-bare receive and atomic reflog policies, unadvertised wants, shallow/filter/URI/HTTPS transports, encoded/other URL forms, linked worktrees and SHA-256 repositories. Existing M2/M3/M4 limitations remain unchanged.

