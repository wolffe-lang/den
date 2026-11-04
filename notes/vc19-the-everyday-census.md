# vc19 — the everyday census

Footprint: module

## Forbidden

No den verb changed. Git was used only as a black-box oracle in the Linux container; no Git implementation source was read. All repositories, identities and peers are synthetic and local. The measurement had no network, no zone database, no inherited `EMAIL`, and an explicit scratch `HOME`. No system Git configuration, keys, services or user repositories were changed.

## Inputs verified

- PAX revision `13bc2ca`, trunk `584b18a`, and candidate `554aa4458f0a1af8a0ef5760899ed110f84c1d0d`, each built natively from a separate committed checkout. These are Linux measurements of those revisions, not executions on PAX itself. The candidate input was obtained by a fresh clone, not by moving its checkout.
- Git 2.56.0, binary SHA-256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`. Its installed services, not the container's distribution Git, were first on `PATH`.
- Wolf 0.2.36, Lupin 0.1.58, bundled std `78b9d3cbc41d51db44d18c40b6694403644d1c83`. Copied compiler/runtime/oracle identities were read twice and matched their source inputs.
- Den's Ubuntu oracle image `f59d9fe871ff769948fb33a83d9eb8e16bea271b17a6c2a10f50043a314d928e`, from the pinned Ubuntu base `534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55`; 12-GiB memory cap, both core-block locks, CPUs 6–11 pinned inside the container, and a 7,100-second bound after lock acquisition.
- Source census tool `b4ac03733af1b637ca3794417c6b8a0a0f399c8c`. The completed capture contains **92 checkpoints × four columns**, with raw stdout/stderr/exit, full before/after file-byte/mode manifests, and retained content-addressed bytes.

Selected commits:
- `a4f6fb7`: predict checkpoints and strict byte comparisons before implementation.
- `322f630`: add the single scenario script, `tools/census-everyday`.
- `b4ac037`: exercise filesystem snapshots, PTY streams and timeouts.
- `8bfc66c`: record the machine table and byte-difference diagnoses.
- `4646f78`: distinguish missing reflogs from packed-ref storage layout.

## Prediction

Expected improvements were no-zone dates, terminal decorations and config writes at `554aa44`; remotes/transports between PAX's revision and trunk; and an upstream-status refusal remaining in all three columns. The observation supports those predictions, but **`config --list` still refuses at `554aa44`**. A bare local path is not interchangeable with `file://` in clone/fetch.

This is an **oracle-advanced checkpoint census**, not an uninterrupted den onboarding session. Each candidate receives the identical raw input at the identical pathname; only Git's result advances the week. Otherwise an early refusal would hide most later verbs. Fixture edits, including conflict resolution and identity-file preparation, occur between recorded commands. Git's intentional merge-conflict exit 1 is not a refusal.

Identity by environment and by repository config, `HOME/.gitconfig`, XDG config and the selected system config file is accepted in every den column, with process output identical to Git. The raw identity-step differences are object compression/index metadata, not rejected author settings. The system-file row selects an owned file through `GIT_CONFIG_SYSTEM`; it does not separately witness the literal default `/etc/gitconfig` pathname. No identity-free/autodetection claim is made.

Use these isolated checkpoints for breadth, not as a continuous den session. The owned system-file override and its default-path limitation are intentional isolation choices.

## Evidence index

The [machine table](vc19-evidence/table.json) contains every row, exact process bytes in base64, exit status, raw state-manifest digests, every changed path with both file hashes/modes, and `state_difference_kinds` for **every `differs` cell**. `process_same` means stdout, stderr and exit all match. No index word, compressed stream, directory or other path was excluded from the strict verdict.

| Column | same | differs | refused | differs with identical process | byte-layout-only differs |
|---|---:|---:|---:|---:|---:|
| PAX `13bc2ca` | 13 | 51 | 28 | 50 | 49 |
| Trunk `584b18a` | 19 | 53 | 20 | 52 | 50 |
| `554aa44` | 30 | 55 | 7 | 54 | 52 |
| Git 2.56.0 | 92 | 0 | 0 | — | — |

These are strict raw-byte counts, **not 55 usability failures in the candidate**. No timings from this fixture-restoration rig are offered as a benchmark for #50.

### The first five PAX refusals, in checkpoint order

| First encounter | PAX result | `554aa44` result |
|---|---|---|
| Day 1, `log-pipe` | exit 128, `fatal: invalid\n` | same as Git |
| Day 1, `log-terminal` | exit 2, `den: not yet implemented: history decorations\n` | same as Git |
| Day 1, `log-decorate` | exit 2, `den: not yet implemented: log option --decorate\n` | same as Git |
| Day 1, `show-first-week` | exit 128, `fatal: invalid\n` | same as Git |
| Day 2, `show-merge` | exit 2, `den: not yet implemented: show combined merge diff\n` | refused identically |

This list intentionally includes the second encounter with `fatal: invalid`. If counting distinct diagnostic strings instead, the fifth is day 4 `cherry-pick`: `fatal: invalid_date\n`; the candidate's process matches Git, with a strict state-only difference. The exact messages below, not guessed milestone assignments, are authoritative.

### Every refusal: exact bytes, first day and frequency

Frequency is command checkpoints per column, not repeated log lines. String literals below preserve newline bytes. A milestone of “none” means the message did not name one, even when its implementation area is known.

| ID | First day | PAX / trunk / 554aa44 hits | Exit | Exact stdout | Exact stderr | Milestone named |
|---|---:|---|---:|---|---|---|
| F1 | 1 | 5 / 5 / 0 | 128 | `""` | `"fatal: invalid\n"` | none |
| F2 | 1 | 2 / 2 / 0 | 2 | `""` | `"den: not yet implemented: history decorations\n"` | none |
| F3 | 1 | 1 / 1 / 0 | 2 | `""` | `"den: not yet implemented: log option --decorate\n"` | none |
| F4 | 2 | 1 / 1 / 1 | 2 | `""` | `"den: not yet implemented: show combined merge diff\n"` | none |
| F5 | 4 | 1 / 1 / 0 | 128 | `""` | `"fatal: invalid_date\n"` | none |
| F6 | 4 | 5 / 5 / 0 | 2 | `""` | `"den: not yet implemented: config (only --get <key> is supported) (M2, vc03)\n"` | M2 |
| F7 | 4 | 0 / 0 / 1 | 2 | `""` | `"den: not yet implemented: config options (M2, vc03)\n"` | M2 |
| F8 | 5 | 3 / 0 / 0 | 2 | `""` | `"den: not yet implemented: remote (M5, vc14)\n"` | M5 |
| F9 | 5 | 2 / 0 / 0 | 2 | `""` | `"den: not yet implemented: push (M5, vc14)\n"` | M5 |
| F10 | 5 | 3 / 3 / 3 | 2 | `""` | `"den: not yet implemented: status upstream tracking\n"` | none |
| F11 | 5 | 2 / 0 / 0 | 2 | `""` | `"den: not yet implemented: clone (M5, vc15)\n"` | M5 |
| F12 | 5 | 0 / 1 / 1 | 2 | `""` | `"Cloning into 'path-clone'...\nden: wire: Unsupported(transport requires file://, git:// or ssh)\n"` | none |
| F13 | 5 | 2 / 0 / 0 | 2 | `""` | `"den: not yet implemented: fetch (M5, vc13)\n"` | M5 |
| F14 | 5 | 0 / 1 / 1 | 2 | `""` | `"den: wire: Unsupported(missing remote /lane/census-first/world/peer.git)\n"` | none |
| F15 | 5 | 1 / 0 / 0 | 2 | `""` | `"den: not yet implemented: pull (M5, vc15)\n"` | M5 |

### Byte-only findings, separate from onboarding blockers

`init`, `add`, `commit` and the identity commands do **not** become onboarding blockers merely because their raw repository bytes differ. Every differing cell has a per-path diagnosis in the machine table, including the following occurrence counts across den columns:

- **152 index path occurrences:** original index SHA-1 checksums verified; after masking only ctime seconds/nanoseconds, mtime seconds/nanoseconds, device and inode, all remaining index bytes match. The original entry words for both tools are recorded. This diagnoses the differing fields; it is **not** a fresh per-file lstat proof and does not turn a strict `differs` into parity.
- **102 shared loose-object path occurrences:** both complete zlib streams validated, inflated bytes equal, independent SHA-1 equals the pathname OID, and inflated SHA-256 values recorded. Compression is different; object content is equal.
- **80 directory-layout occurrences:** absent/present directories, including the empty hooks directory and clone object fan-outs. These are retained in the raw verdict, not counted as refused commands.
- **Two config-file occurrences:** the clone's remote URL is quoted by den and unquoted by Git; the scalar value is equal for this escape-free fixture URL.
- **88 clone storage/ref path occurrences:** den's loose objects/refs versus Git's packed storage. Namespace equivalence has **not** been independently proved here, so these are explicitly `clone-storage-layout-unproved`, not a representation-only pass and not an asserted data-loss finding.

There are 49 / 50 / 52 wholly byte-layout-only `differs` checkpoints in PAX / trunk / candidate. This diagnostic grouping never changes their recorded raw verdicts.

### User-visible and real-content differences

Only **one checkpoint per den column has differing stdout/stderr/exit without being refused**: `status-conflict` on day 3. Exit remains 0, but Git prints the following between the branch heading and `Unmerged paths:`; den omits it:

```text
You have unmerged paths.
  (fix conflicts and run "git commit")
  (use "git merge --abort" to abort the merge)

```

The index difference on that checkpoint is confined to the six stat words described above. This missing recovery guidance is a user-visible difference and is included in the follow-on ranking.

Two additional checkpoints have **identical processes but real metadata differences**, separately retained rather than disguised as compression:

- Day 4 `commit-ignore`, all den columns: `repo/.git/AUTO_MERGE` remains present after the commit; Git removes it. Its bytes/hash are recorded. This is stale pseudoref state, not a failure to create the requested commit.
- Day 5 `clone-file-url`, trunk/candidate: `clone/.git/logs/HEAD` and `clone/.git/logs/refs/heads/main` use `Den Transport <den@example.invalid> 0 +0000`, with `clone` / `fetch` messages. Git uses the supplied `Everyday User` identity, the supplied nonzero date and `clone: from ...`. Den lacks the oracle-created `clone/.git/logs/refs/remotes/origin/HEAD` but adds `clone/.git/logs/refs/remotes/origin/main`, which the oracle does not create. This is a real reflog-fidelity finding, alongside the unproved storage-layout difference, not a refusal or an observed checkout-content loss.

These account for all non-layout-only differing checkpoints: PAX has `status-conflict` and `commit-ignore`; trunk/candidate also have `clone-file-url`. The machine table enumerates every changed path and both byte hashes, not just these examples.

### Every checkpoint

`differs: state` means `process_same=true`; `differs: output/exit, state` means `process_same=false`. The per-path kinds and raw state differences are in the linked machine table. `F1`–`F15` refer to the exact refusal strings above. Only the selected Git result advances the fixture.

| Day / checkpoint | PAX `13bc2ca` | Trunk `584b18a` | `554aa44` | Git 2.56.0 |
|---|---|---|---|---|
| 1 / `init` | differs: state | differs: state | differs: state | same |
| 1 / `add-first-file` | differs: state | differs: state | differs: state | same |
| 1 / `commit-env-identity` | differs: state | differs: state | differs: state | same |
| 1 / `identity-repository` | differs: state | differs: state | differs: state | same |
| 1 / `identity-home` | differs: state | differs: state | differs: state | same |
| 1 / `identity-xdg` | differs: state | differs: state | differs: state | same |
| 1 / `identity-system` | differs: state | differs: state | differs: state | same |
| 1 / `log-pipe` | refused F1 | refused F1 | same | same |
| 1 / `log-terminal` | refused F2 | refused F2 | same | same |
| 1 / `log-decorate` | refused F3 | refused F3 | same | same |
| 1 / `show-first-week` | refused F1 | refused F1 | same | same |
| 1 / `status-clean` | differs: state | differs: state | differs: state | same |
| 1 / `diff-worktree` | same | same | same | same |
| 1 / `add-edit` | differs: state | differs: state | differs: state | same |
| 1 / `diff-staged` | same | same | same | same |
| 1 / `commit-edit` | differs: state | differs: state | differs: state | same |
| 2 / `branch-create` | same | same | same | same |
| 2 / `branch-list` | same | same | same | same |
| 2 / `checkout-topic` | differs: state | differs: state | differs: state | same |
| 2 / `add-feature` | differs: state | differs: state | differs: state | same |
| 2 / `commit-feature` | differs: state | differs: state | differs: state | same |
| 2 / `switch-main` | differs: state | differs: state | differs: state | same |
| 2 / `merge-fast-forward` | differs: state | differs: state | differs: state | same |
| 2 / `switch-side` | same | same | same | same |
| 2 / `add-side` | differs: state | differs: state | differs: state | same |
| 2 / `commit-side` | differs: state | differs: state | differs: state | same |
| 2 / `checkout-main` | differs: state | differs: state | differs: state | same |
| 2 / `add-main` | differs: state | differs: state | differs: state | same |
| 2 / `commit-main` | differs: state | differs: state | differs: state | same |
| 2 / `merge-three-way` | differs: state | differs: state | differs: state | same |
| 2 / `show-merge` | refused F4 | refused F4 | refused F4 | same |
| 3 / `branch-conflict` | same | same | same | same |
| 3 / `add-conflict-side` | differs: state | differs: state | differs: state | same |
| 3 / `commit-conflict-side` | differs: state | differs: state | differs: state | same |
| 3 / `switch-main-again` | differs: state | differs: state | differs: state | same |
| 3 / `add-conflict-main` | differs: state | differs: state | differs: state | same |
| 3 / `commit-conflict-main` | differs: state | differs: state | differs: state | same |
| 3 / `merge-conflict` | differs: state | differs: state | differs: state | same |
| 3 / `status-conflict` | differs: output/exit, state | differs: output/exit, state | differs: output/exit, state | same |
| 3 / `add-resolution` | differs: state | differs: state | differs: state | same |
| 3 / `commit-resolution` | differs: state | differs: state | differs: state | same |
| 3 / `tag-lightweight` | refused F1 | refused F1 | same | same |
| 3 / `tag-annotated` | refused F1 | refused F1 | differs: state | same |
| 3 / `tag-list` | same | same | same | same |
| 3 / `stash-push` | differs: state | differs: state | differs: state | same |
| 3 / `stash-list` | same | same | same | same |
| 3 / `stash-pop` | differs: state | differs: state | differs: state | same |
| 3 / `restore-worktree` | differs: state | differs: state | differs: state | same |
| 3 / `rename-file` | differs: state | differs: state | differs: state | same |
| 3 / `reset-staging` | differs: state | differs: state | differs: state | same |
| 3 / `reset-hard` | differs: state | differs: state | differs: state | same |
| 3 / `remove-file` | same | same | same | same |
| 3 / `restore-staged` | same | same | same | same |
| 3 / `restore-removed` | differs: state | differs: state | differs: state | same |
| 4 / `switch-replay` | same | same | same | same |
| 4 / `add-replay` | differs: state | differs: state | differs: state | same |
| 4 / `commit-replay` | differs: state | differs: state | differs: state | same |
| 4 / `switch-main-replay` | differs: state | differs: state | differs: state | same |
| 4 / `add-new-base` | differs: state | differs: state | differs: state | same |
| 4 / `commit-new-base` | differs: state | differs: state | differs: state | same |
| 4 / `switch-replay-again` | differs: state | differs: state | differs: state | same |
| 4 / `rebase-explicit` | differs: state | differs: state | differs: state | same |
| 4 / `switch-main-pick` | differs: state | differs: state | differs: state | same |
| 4 / `cherry-pick` | refused F5 | refused F5 | differs: state | same |
| 4 / `ignore-status` | differs: state | differs: state | differs: state | same |
| 4 / `ignore-check` | same | same | same | same |
| 4 / `add-ignore` | differs: state | differs: state | differs: state | same |
| 4 / `commit-ignore` | differs: state | differs: state | differs: state | same |
| 4 / `config-write-local` | refused F6 | refused F6 | same | same |
| 4 / `config-write-email` | refused F6 | refused F6 | same | same |
| 4 / `config-get` | same | same | same | same |
| 4 / `config-list` | refused F6 | refused F6 | refused F7 | same |
| 4 / `config-write-global` | refused F6 | refused F6 | same | same |
| 4 / `config-write-global-email` | refused F6 | refused F6 | same | same |
| 5 / `init-bare-peer` | differs: state | differs: state | differs: state | same |
| 5 / `remote-add` | refused F8 | same | same | same |
| 5 / `remote-verbose` | refused F8 | same | same | same |
| 5 / `remote-set-url` | refused F8 | same | same | same |
| 5 / `push-upstream` | refused F9 | same | same | same |
| 5 / `status-upstream` | refused F10 | refused F10 | refused F10 | same |
| 5 / `clone-local-path` | refused F11 | refused F12 | refused F12 | same |
| 5 / `clone-file-url` | refused F11 | differs: state | differs: state | same |
| 5 / `status-after-clone` | refused F10 | refused F10 | refused F10 | same |
| 5 / `fetch-local-path` | refused F13 | refused F14 | refused F14 | same |
| 5 / `fetch-configured` | refused F13 | same | same | same |
| 5 / `add-shared` | differs: state | differs: state | differs: state | same |
| 5 / `commit-shared` | differs: state | differs: state | differs: state | same |
| 5 / `push-configured` | refused F9 | same | same | same |
| 5 / `pull-configured` | refused F15 | differs: state | differs: state | same |
| 5 / `status-after-pull` | refused F10 | refused F10 | refused F10 | same |
| 5 / `blame-clean` | refused F1 | refused F1 | same | same |
| 5 / `log-week-end` | refused F2 | refused F2 | same | same |

## Done-when

### Ranked draft of next work

This is a recommendation, not an allocation. Ranking uses remaining refusals and directly user-visible output differences, their recurrence and the cost of being blocked. The byte-only findings above do not increase a lane's onboarding priority.

| Priority | Draft scope | Evidence and issue association |
|---|---|---|
| 0 | Deliver the existing dates/decorations/config-write work, then update the PAX pin in its own rollout | The candidate reduces PAX's 28 refused checkpoints to 7. All day-1 log/show refusals disappear, as do both tag refusals and the cherry-pick date failure. Config writes and configured file-URL remotes work. Existing associations: #45 and #46. The PAX pin update is outside this den change. |
| 1 | Finish the already-scoped upstream-status work and its performance gate | Three repeated refusals after push, clone and pull, including the first `status` in the clone. Existing associations: #49 and #50. This census witnesses #49, not the 454-file performance claim in #50. |
| 2 | Complete config inspection with `config --list` | One day-4 refusal remains despite working config writes/`--get`; scope ordering, duplicate values, implicit values and exact output against the oracle. No matching open issue was found; requires a new issue before a future implementation lane. |
| 3 | Accept ordinary local repository paths in clone/fetch | Two day-5 refusals: absolute bare-path clone and explicit bare-path fetch. Scope absolute/relative paths and remote-name disambiguation, with existing `file://` behavior unchanged. No matching open issue was found. This narrow scope would not settle the broader wire backlog in #48. |
| 4 | Implement default merge inspection | Day-2 `show HEAD` after a true merge still refuses combined merge diff. Scope documented combined display, differing-parent paths and exact headers/hunks; preserve existing `show -s`. No matching open issue was found. Earlier than the wire refusals, but one inspection failure rather than repeated repository-status blockage. |
| 5 | Match conflicted-status recovery guidance | One day-3 user-visible difference per column, no command refusal: restore the missing conflict-resolution and merge-abort preamble. Keep separate from the upstream/performance claim unless explicitly included in that work's scope. No matching open issue was found. |

Separately, propose a **metadata-fidelity** lane for clone reflog identity/date/messages and remote-reflog creation differences, plus a narrowly isolated stale-`AUTO_MERGE` cleanup row. These are real state discrepancies, not representation-only findings, but no extra onboarding blocker was observed here. No current issue is claimed resolved by this measurement PR. No issue was filed, labeled or closed.

Recommend the order above, leaving #48's HTTPS/protocol/shallow/filter/progress scope intact; the draft scopes without an issue need one before implementation. The decision remains open.

### Verification and handoff

- [x] Prediction committed before code.
- [x] Twenty harness assertions: refusals, byte/mode/symlink snapshots, complete columns, separate PTY streams and pipe/PTY timeouts.
- [x] Complete Linux four-column census: 92 checkpoints, zero missing columns.
- [x] Exact output/exit and complete raw-state comparisons; every `differs` has `process_same` and per-path kinds.
- [x] Independent zlib/OID and index-checksum/field diagnoses, without normalized verdicts.
- [x] README read, current: no supported verb, milestone or existing matrix count changed.

Final handoff gates:
- Final-head local record (`final-green.record`), including capture/table binding, independently repeated state diagnoses and planner tests.
- One-hunk `vc19-plant-refusal`: treating a refusal as `same` must fail `refusal-is-not-parity` in `plant-refusal.record`.
- Open PR and one local-evidence audit; no CI wait.

The final-head record and plant record accompany the handoff; they are not substituted by the earlier exploratory Linux process exit. The plant runs locally and has no PR. `tools/census-everyday --self-test` needs no compiler or oracle; a real run requires all four executable paths, a new output directory, and the no-zone Linux oracle container. `--verify` rechecks complete captures and retained raw bytes. The script never changes a den implementation verb.
