# vc18 — the everyday refusals

The refusals a person meets in den's first days of ordinary use, each compared byte for byte with the pinned Git:

- upstream tracking in `status` and `branch` (#49, #58);
- `status` speed (#50);
- `config --list` (#51);
- plain local paths for `clone` and `fetch` (#52);
- `show` of a merge commit (#53);
- the merge-in-progress guidance in `status` (#54);
- writing descriptors 1 and 0 instead of reopening `/dev/stdout` and `/dev/stdin` (#55).

Footprint: cross-cutting (tools/gate, tools/gate-record and ci/tiers-test.py gain the everyday and status-speed steps)

## Forbidden

The work is clean-room. Its inputs were Git's published manual pages and black-box runs of the pinned executable in containers. No Git, libgit2 or other VCS implementation source was read, and nothing was fetched from Git's source repository during this lane's implementation. No verb outside the seven items changed, beyond what a fix needs and says below: the pack read path and the SHA-1 block function, which `status` needed to be fast. No toolchain pin, CI workflow file or remote changed. Every fixture is generated; none is a person's repository.

## Inputs verified

- Git 2.56.0, executable SHA-256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`, checked by digest by every row script before use.
- Unchanged pins: wolf 0.2.36 (`5adf3d91`), lupin 0.1.58 (`6240efe5`).
- Manual pages (published at `https://git-scm.com/docs/<page>`): git-status(1), git-branch(1), git-config(1), git-clone(1), git-fetch(1), git-show(1), git-diff(1) with its combined-diff format and the `-c`/`--cc`/`--diff-merges` options, and gitformat-index(5) for the cache-tree extension's valid and invalidated records.
- The racy-clean rule is cited by URL, not re-read: `https://git-scm.com/docs/racy-git`. Its rule: an entry whose cached mtime is at or after the index file's own mtime must be content-checked. The implementation is conservative by construction, as below.
- FIPS 180-4 §6.1.2 for the SHA-1 restructuring; the vendored rounds' provenance header is unchanged.

| Machine | Used for |
|---|---|
| Linux desktop, i7-12700KF, 46 GiB | every build and row, in the `r41-toolchain` image under a 12 GiB cap (6 GiB for light jobs), taskset inside, no network, read-only pin mounts; timed rows only on a six-CPU performance block with nothing beside it |
| Linux laptop, i7-10870H (8 cores), 31 GB | the laptop ratio rows, on one slot (CPUs 0-3 and 8-11) with the machine to itself and its temperatures logged beside the run; it throttles at 100 °C, so its timings are compared only with its own |
| Apple silicon laptop, macOS arm64 | editing and commits only |

An earlier baseline take on the laptop was voided by a reboot before it ran, and nothing from it is used.

## Prediction

`tests/vc18-prediction.txt` was committed before any change. Status hypotheses and what the profile found:

| Predicted | Measured |
|---|---|
| repeated packed-store full checksums | confirmed, and dominant: every packed read hashed the whole 19 MB pack again, about 335 ms a read, so 6.0 s for HEAD's 18 trees |
| unnecessary blob hashing | confirmed: every tracked body was read and hashed, with no use of the index's stat data |
| untracked content reads | confirmed, and worse: every untracked and ignored body (the 168 MB ignored `build/`) was read and kept, and an insertion sort copied whole file states with their bodies. Memory grew past a 12 GiB cap in three minutes, and the baseline's `status` is killed by the OOM killer, cold and warm |
| linear `Map` and path lookups | confirmed: the runtime `Map` is a linear scan (2,500 string keys, 2.9 ms to insert), which made each idx parse quadratic; index, tree and file lookups were linear scans |
| not predicted | SHA-1 ran at about 65 MB/s, the floor of the cold case; and every untracked path reloaded every ignore source |

## Evidence index

- **Red first.** Each family's rows were committed and seen red before its code:
  - upstream, config, merge, descriptors and local-path rows, at the baseline counterpart `a1bcd613`;
  - the configured-clone upstream rows (25), against trunk `ef0bb0c`'s den;
  - the non-bare and loud local-clone rows, before the `done.` fix;
  - the combined-diff rows, before their code;
  - the ratio row, which is red at the baseline because den's `status` is OOM-killed under a 4 GiB cap, cold after 18.1 s CPU and warm after 19.0 s.
- **Rows** (`tools/everyday-test.py`, `tools/local-path-test.py`, `tools/check-everyday`, native and release):
  - upstream: 109 rows. Thirteen `status` and `branch` forms over equal, ahead, behind, diverged, a merge DAG and a gone upstream; dirty v2, a local `.` upstream and detached HEAD; and 25 from a configured clone through push and fetch;
  - config: 51 listing forms over every scope, `--file` and XDG;
  - merge: conflict guidance with and without hints, resolved guidance, and `show` of merges (below);
  - descriptors: 3 rows, `status` and `check-ignore` writing an inherited fd 1, and `check-ignore --stdin` reading fd 0, where reopening by name is denied;
  - local paths: absolute and relative, bare and checkout clones, quiet and loud, `--no-local`, explicit and configured fetch.
- **Status ratio** (`tools/status-measure.py` through `tools/check-status-speed`):
  - the fixture: 454 tracked files, 42 untracked, a 19 MB pack and a 187 MB worktree;
  - the method: cold (copied stat words) and warm (refreshed) indexes, interleaved samples, child user+system CPU above a 0.2 s floor, `GIT_OPTIONAL_LOCKS=0`, process bytes compared on every sample.

## Done-when

- **Upstream (#49, #58):** every row exact.
- **Config `--list` (#51):** every row exact, including `--show-origin`, `--show-scope` and `--name-only`.
- **Merge guidance (#54):** every row exact.
- **Descriptors (#55):** every row exact.
- **Local paths (#52):**
  - the local strategy copies objects, never hardlinks; unreachable objects are copied as Git's local clone does;
  - quiet and loud bare clones and every fetch are exact; loose objects are compared by inflated content, per R4a;
  - `--no-local` rows are reviewed (R-vc18-1);
  - checkout clones are exact outside `.git/logs/` (R-vc18-2).
- **Status speed (#50):** measured at this head's status code on a performance block on each Linux machine, with nothing beside it, on the 454-file fixture. Each CPU figure is the smallest of three interleaved samples, each sample being the mean of as many runs as reach 0.2 s of CPU.

  | machine | state | den CPU | Git CPU | ratio | with the 1.10 guardband |
  |---|---|---|---|---|---|
  | desktop | cold (copied stat words) | 127.7 ms | 34.8 ms | 3.67 | 4.03 |
  | desktop | warm (refreshed index) | 3.50 ms | 0.97 ms | 3.59 | 3.95 |
  | laptop | cold | 177.5 ms | 50.1 ms | 3.55 | 3.90 |
  | laptop | warm | 4.37 ms | 1.09 ms | 4.01 | 4.41 |

  - All four are within 5x after the guardband, and process bytes are identical in every sample.
  - The laptop has the CPU #50 was reported on. One cut earlier its warm ratio was 4.77, which fails at 5.24 guarded; that led to the last change (one idx parse per HEAD tree lookup, and no copies status never reads).
  - Before: the baseline's `status` was OOM-killed under a 4 GiB cap after 18 s of CPU, and #50 measured 32 s against Git's 0.33 s. Peak memory is now about 11 MB.
  - The warm figures have no refresh on den's side (R-vc18-5).

- **Show of a merge (#53):** `show` and `show --cc` print the dense combined diff, `show -c` the combined diff, with `-U<n>`; `show -s` is unchanged.
  - **How:** `src/diff/combined.lu` runs den's existing line differ once per parent against the result. Each result line carries one mark per parent. Removed parent lines sit before the result line they precede, and identical removals from different parents are merged into one line, ignoring a trailing newline.
  - **Dense output:** changes fewer than the context apart form one group. A group is dropped when some parent is untouched there and every touched parent marks it the same way. The remaining groups get context and merge into hunks at most twice the context apart.
  - **Details only the pinned Git's output could fix, each held by its own rows:**
    - ranges always print `start,count`;
    - the hunk heading is the nearest earlier result line starting with a letter, `_` or `$`, searched no further back than the previous shown hunk, capped at 40 bytes, trimmed, then one byte shorter;
    - no `\ No newline at end of file` marker is printed;
    - removals at a hunk's first position are counted, but printed only when they are that hunk's own change;
    - at `-U0`, a removal next to a change on the following line joins its hunk, and a hunk with end-of-file removals reports every count one lower, so a zero count prints as 2^64-1 (R-vc18-cc-2);
    - under `--cc`, a file with no hunk left keeps its header only when it has a mode line.
  - **Rows:** 7 merge rows (3 guidance, 4 `show`) and 343 combined rows are exact. About 90 are hand-built: paths changed from one parent or both, conflict-resolved hunks, hunks `--cc` drops, files added, deleted or changed in mode, octopus merges, `-U` variants, end of file and missing newlines, binary files, and the corpus's merge. The rest come from 48 seeded random merges.
  - **Reviewed, never counted:** 6 seeded rows where den's own `diff HEAD^j HEAD` already aligns an equal-cost script differently from Git (R-vc04-3), so the combined columns inherit it (R-vc18-cc-1).
  - **Red first:** 164 rows failed before the code. Exploring with 400 seeds found 13 more failing cases, each fixed with named rows that were seen red first. At the final code, 400 seeds give 973 exact rows, 80 reviewed of the same inherited-alignment kind and 0 failures, and the seeds that once failed all pass.
  - **Refused by name:**
    - `--stat` of a merge, any pretty format but the default, and `--binary`;
    - attributes, submodules and more than 30 parents;
    - `-m`, `--diff-merges=*`, `--combined-all-paths`, `--remerge-diff`, `--dd` and `--no-diff-merges`;
    - `log -c` and `log --cc`;
    - a removed-line table over 4,000,000 cells.

### Applied R-list

- **R-vc18-1:** `--no-local` storage. Git keeps the received pack (`pack-*.pack`, `.idx`, `.rev`); den installs the same objects loose, as its wire import always has. The row is reviewed and never counted, and passes only while process bytes, refs, config and the object inventory are exact. Follow-on: keep received packs on clone (index-pack plus `.rev`).
- **R-vc18-2:** a checkout clone's reflogs use den's transport identity, a zero date and bare `clone`/`fetch` messages, on every transport. The rows are KNOWN: exact outside `.git/logs/`, each differing log path named, never counted. This goes to the metadata-fidelity lane vc19 proposed.
- **R-vc18-3:** the whole-pack checksum moves to verify-pack, fsck and installation, as in Git. A read still checks the idx's own checksum, the pack's structure, the idx-to-pack trailer binding, each entry's CRC32 and each object's reconstructed identity. pack-test's two read-path corruption rows are red by name (`pack entry CRC`, `pack index binding`), and verify-pack rows on the same packs must still say `pack checksum`.
- **R-vc18-4:** `status` trusts the stat data under the racy rule, and a valid cache-tree root equal to HEAD's tree, as Git does. All ten stat words are compared; an entry with an mtime at or after the index's own mtime, or an unknown index time, is always content-checked.
- **R-vc18-5:** `status` performs no opportunistic index refresh, so a cold index stays cold under den, where Git's first `status` rewrites it. The ratio row states it: den's warm path has no refresh, and Git's warm path follows Git's own refresh. Follow-on: the optional refresh, byte-identical to Git's index including its racy handling.
- **R-vc18-cc-1:** seeded combined rows whose per-parent two-tree diff already differs from Git's are named review rows, counted neither way (not FAIL, not dropped).
- **R-vc18-cc-2:** Git's `-U0` end-of-file count underflow is reproduced byte for byte, not corrected.
- **R-vc18-cc-3:** untested pretty formats and `--stat` of a merge are refused rather than guessed.
- **R-vc18-cc-4:** the gate runs 48 seeds; `DEN_COMBINED_SEEDS=400` explores more.

### Remaining limits

- `pull` and `push` to plain paths have no rows; this lane's contract is `clone` and `fetch`.
- `inspect`'s next-offset search (verify-pack) is still linear per entry.
- Combined diffs of a binary version print `Binary files differ`; only the all-binary case has a row.

### The re-pin

PAX should carry this PR's merge commit on trunk. A px lane does the re-pin.
