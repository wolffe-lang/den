# vc16 — the wire porcelain

The lane's report, from PR #47 (merged at `8b698fe8`, 2026-11-03): remotes and tracking, configured fetch and push, `pull`, force-with-lease, the measured update policy (den#44), and ssh through the system client.

Footprint: cross-cutting

## Forbidden

Clean-room implementation: published Git manuals/specifications and black-box runs of the pinned executable only; no Git, libgit2 or other VCS implementation source was read. Test repositories are isolated local fixtures, never GitHub remotes. System SSH uses validated argv vectors and separately quoted literal remote arguments; no SSH configuration or keys were changed. No protocol-v0 fallback was added.

## Inputs verified

- Git 2.56.0, executable SHA-256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`.
- Wolf 0.2.36 (`5adf3d91`), Lupin 0.1.58 (tag `6240efe5`, embedded revision `a5378e3`), std `78b9d3cbc41d51db44d18c40b6694403644d1c83`.
- Fresh offline toolchain/oracle caches; release archives and staged binaries checked twice. The std source matches the pinned archive tree; two bundled-only licence files are recorded separately.
- Linux containers have a 12-GiB cap and taskset inside the assigned core block. Each leaf takes both block locks independently, with a bounded hold. Network access is disabled for portable leaves. Live SSH reserves its remote CPU slot before taking the macOS build lock; disk/memory gates run inside that lock.

Selected changes:
- `04b6a1f`: validated system-SSH transport and shared byte pipes.
- `ff2f39e`: configured pull delegated to existing merge/rebase engines.
- `fb7f58a`: measured pull CLI/config precedence.
- `919bbf6`: deterministic fetch/push/pull startup diagnostics.
- `e3361ba`: both CI routing proofs and every inherited gate leaf retained.
- `7e4568d`, `8b698fe`: red-first proof and command-scoped fix for background Git maintenance in the vc14 recovery fixture.

## Prediction

`tests/vc16-prediction.txt` was committed before implementation and expanded explicitly as new cases were measured. This adds scalar-URL remote management, tracking configuration and refs, configured/default fetch/push, prune, upstream setup, leases, push status reports, M3-backed pull and local SSH interoperability. Addresses #44 without claiming M5 completion.

Per native/release tier, the portable gate contains **892 fixture groups**:

| Family | Groups | Comparison |
|---|---:|---|
| Remote and tracking | 48 | Exact process/config/ref/reflog/state results |
| Typed push policy | 770 | Acceptance and resulting refs; raw failure bytes/status retained, not called exact parity |
| Configured fetch/push, leases and failures | 48 | 47 exact; one exact-input-bound service stderr REVIEW |
| Pull | 26 | Exact process results and complete repository state with independently proved index-stat words |

Twelve live macOS-to-Linux SSH groups are additional: URI/scp clone, normal checkout, space/quote/shell-literal paths, incremental fetch, URI/scp push, stale/matching leases and protocol-v0 refusal. Canonical objects are independently checked against pinned server bodies; macOS Git is not an oracle. Pure config/SSH units, actual-checked verdicts and 352 rejected review-binding mutations are counted separately.

### #44 policy table

| Namespace | Creation | Changed unforced value | Force |
|---|---|---|---|
| `refs/heads/*` | Raw commit only | Commit fast-forward | Rewind allowed; still raw commit only |
| `refs/tags/*` | Measured object types | Replacement rejected | Replacement allowed |
| `refs/notes/*`, `refs/custom/*`, `refs/remotes/*` | Measured object types | Both values must peel to commits and fast-forward; distinct/nested tags of the same commit are allowed | Changed tree/blob values allowed |
| `refs/stash` | Remote update rejected as `funny refname` | Remote update rejected; local stash unchanged | Does not bypass receiver rejection |

Unchanged values remain client no-ops. The 770-group matrix covers Git→Git, den→Git and Git→den-service roles; it does not equate all rejection exit codes or diagnostic bytes.

## Evidence index

Complete raw argv, effective environment, stdin, stdout, stderr and exit status are retained beside named row summaries. Remote/configured/pull comparisons retain complete repository state; no arbitrary snapshot paths are excluded. The inherited six permitted index-stat words are independently checked against each tool's own worktree. SSH captures retain independent canonical object/ref checks and normal reservation teardown.

### Final-head green

`final-green.record` covers head `8b698fe8b9d65fa23e6b6072bf51967da27971b3`. Every column-zero END is zero. The recorder independently re-parsed this record and the plant together.

```text
RECORD repo=den head=8b698fe8b9d65fa23e6b6072bf51967da27971b3 tree=276149034cdc396c88b887e0aa087ce502cb9819 host=nomad boot={_sec_=_1792959699,_usec_=_593641_}_Sun_Oct_25_16:21:39_2026 start=2026-11-03T12:08:12Z
END runner-test exit=0 secs=1
END planner exit=0 secs=1
END local-gate-routing exit=0 secs=1
END fetch-toolchain exit=0 secs=1
END fetch-oracle exit=0 secs=0
END format exit=0 secs=1
END build exit=0 secs=52
END wire exit=0 secs=354
END housekeeping exit=0 secs=262
END blame exit=0 secs=56
END stash exit=0 secs=220
END revision exit=0 secs=15
END history exit=0 secs=66
END refs exit=0 secs=103
END merge exit=0 secs=73
END replay exit=0 secs=81
END diff-units exit=0 secs=1
END hash-checked exit=0 secs=1
END tls-local exit=0 secs=7
END corpus exit=0 secs=2
END packed-read exit=0 secs=342
END packed-write exit=0 secs=841
END codec exit=0 secs=19
END objects exit=0 secs=29
END config exit=0 secs=51
END index exit=0 secs=20
END ignore exit=0 secs=6
END worktree exit=0 secs=42
END commit exit=0 secs=50
END delta exit=0 secs=3
END rename exit=0 secs=146
END diff-corpus exit=0 secs=44
END binary-reviewed exit=0 secs=19
END binary-strict-native exit=0 secs=5
END binary-strict-release exit=0 secs=4
END oracle-selftest exit=0 secs=1
END oracle exit=0 secs=7
END oracle-negative exit=0 secs=0
END static exit=0 secs=91
END ssh-interop exit=0 secs=4066
END collect-evidence exit=0 secs=3
RECORD-END worst=0 steps=41 end=2026-11-03T14:06:19Z
```

The inherited binary strict-byte reports remain explicitly expected RED inside their validated report-only wrappers; reviewed representation differences and named not-yet refusals are not exact parity passes.

### Isolated plant

Branch `vc16-plant-lease`, head `fdcc5f5653f766287be18534f4942265357e559b`, has one commit, one file and one hunk on the green head. It disables the expected-old lease comparison for valid destinations, outside the main line. There is no plant PR.

`plant-red1.record` names `configured-lease-explicit-stale`: pinned Git rejects with exit 1 while planted den incorrectly accepts with exit 0. Both complete resulting states are retained. Raw FAIL lines remain at column zero inside the failed step.

```text
RECORD repo=den head=fdcc5f5653f766287be18534f4942265357e559b tree=7690b966b144cf52d2fb1a822fa2d9e25d21057e host=nomad boot={_sec_=_1792959699,_usec_=_390863_}_Sun_Oct_25_16:21:39_2026 start=2026-11-03T14:10:02Z
PLANT base=8b698fe8b9d65fa23e6b6072bf51967da27971b3 branch=vc16-plant-lease
PLANT-ROW configured-lease-explicit-stale
START plant-den-build
END plant-den-build exit=0 secs=11
START plant-configured-leases
FAIL configured-lease-plain-stale
FAIL configured-lease-explicit-stale
FAIL configured-lease-expect-absent
FAIL configured-lease-missing-tracking
FAIL configured-lease-expect-revision
FAIL configured-lease-delete-stale
END plant-configured-leases exit=1 secs=2
START record-wrapper
END record-wrapper exit=1 secs=0
RECORD-END worst=1 steps=3 end=2026-11-03T14:10:15Z
```

### Recovery-fixture determinism

The earlier full run exposed a disappearing `maintenance.lock` during the vc14 fixture's setup snapshot. The fix uses command-scoped `gc.auto=0`, `maintenance.auto=false`, `gc.autoDetach=false` and `maintenance.autoDetach=false`; it neither rewrites fixture config nor ignores a path. The named proof first failed at `7e4568d`, then passed at `8b698fe`. Trace2 observes an automatic maintenance child in a forced, foreground-joined counterfactual; the same forced defaults start no automatic helper once the setup controls apply. This relies on the documented automatic-work controls, not a claim that they stop arbitrary explicitly launched foreign writers. The proof runs in both recovery tiers.

## Done-when

- [x] Remote add/remove/rename/list/-v/get-url/set-url and branch upstream configuration.
- [x] Configured/default fetch/push, tracking refs, prune and `push -u`.
- [x] Plain/explicit force-with-lease, per-ref reports and measured typed update policy.
- [x] Pull merge/rebase, conflicts, CLI/config precedence and divergent-policy refusal through existing engines.
- [x] Deterministic missing-remote, wrong-URL/ref and auth-free daemon failure rows.
- [x] Native/release portable corpus, actual-checked config/SSH programs and both CI routing tests.
- [x] Same-head live SSH leg: 12/12, reservation cleanup exit 0.
- [x] Full final-head gauntlet: 41/41 zero ENDs; independently verified one-hunk plant red by name.
- [x] README/MAP/SOURCES refreshed.
- [ ] Full-matrix CI and final audit.

### Applied R-list

- **R-vc16-1 — out of scope:** no GitHub SSH interoperability test. A future test needs separate authorization for a disposable test repository and synthetic disposable refs; no such test was performed.
- **R-vc16-2 — applied:** fixture pushes remain confined to owned local repositories; publication is separate from fixture traffic.
- **R-vc16-3 — applied:** exact tracking rows pin explicit identities. Original no-override captures and HOME/global-config visibility reproduction remain retained. Auto-identity is a named non-parity limit; no hostname is synthesized.
- **R-vc16-4 — applied:** `lease-delete-match` has one concrete input/output/status/state-bound service stderr REVIEW. Side-band-64k diagnostic prefix/padding remains separate work; a changed input or outcome fails the review binding.
- **R-vc16-5 — applied:** explicitly selected owned service wrappers export protocol v2 and execute pinned services. Ordinary sshd protocol v0 is refused; no SSH configuration changes or fallback.

### Remaining limits

Scalar URLs and ordinary wildcard tracking maps are bounded. Repeated URL assignments, continued/CRLF/BOM config, inline header assignments, inherited-only editing, broader refspec/default/config forms and existing unconfigured local-path transport remain named limits. Literal service selectors are executable paths, not shell command languages.

Pull retains rewritten-upstream/fork-point and octopus/refspec-selection refusals, plus every inherited conservative merge/replay/editor limit. SSH protocol v0/v1, encoded/IPv6 SSH forms, HTTPS, shallow/filter/URI fetches, broader transport configuration and general failure-output parity remain incomplete. The auto-identity and receive-service stderr differences above are explicit limits, not blanket exclusions. Existing object/pack/resource bounds remain in README and MAP. No M5-complete claim is made.

