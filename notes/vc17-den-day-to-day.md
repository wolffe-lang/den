# vc17 — den day to day

Dates with no zone database (#45), history decorations (#46) and config writes: the three gaps a person meets in den's first minutes of everyday use. Each is compared byte for byte with the pinned Git. The remaining wire limits in #48 are unchanged.

Footprint: module

## Forbidden

The work is clean-room. Its inputs were Git's published manuals (git-config(1), git-log(1) and Git's documented TZ handling) and black-box runs of the pinned executable in containers. No Git, libgit2 or other VCS implementation source was read. No verb outside the three items changed. No SSH configuration or keys, protocol fallback, toolchain pin or CI workflow changed. Test repositories and the SSH endpoint are owned local fixtures, never GitHub remotes.

## Inputs verified

- Git 2.56.0, executable SHA-256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`, checked by digest on every host before use.
- Unchanged pins: wolf 0.2.36 (`5adf3d91`), lupin 0.1.58 (tag `6240efe5`) and std `78b9d3cbc41d51db44d18c40b6694403644d1c83`.
- The machines:

| Host | Machine | Used for |
|---|---|---|
| nomad | Apple silicon laptop, macOS arm64, 48 GB | targeted builds and oracle rows on macOS, the live SSH client |
| kasumi | CachyOS desktop, i9-11900K, 31 GiB | the red takes, the components take and the first five full takes, on CPUs 4–7 |
| satoyama | EndeavourOS laptop, i7-10870H (8 cores, 16 threads), 31 GB | the last full takes, the plant and the live SSH peer, on CPUs 0–3 and 8–11 with the host to itself |

Linux leaves run in the `r41-toolchain` image under a 12 GiB cap, with taskset inside the container, no network and read-only pin mounts. `/usr/share/zoneinfo` and `/etc/localtime` are mounted empty, so the no-database rows have no database to find. satoyama throttles at 100 °C, and its CPU temperatures are logged beside every leaf; its timings are compared only with its own.

Selected changes:
- `682458a`, `972ce47`: UTC rendering without a zone database, the missing-zone fallback and the ambiguity-hint dates.
- `6f02fcd`, `1deb3b6`: terminal-aware decorations in ref order, with Git's default terminal colours.
- `5cd19df`, `6060533`, `aec1d57`, `9190d24`: scoped config writes under an exclusive lock and atomic rename, symlinked targets edited in place, and the `~/.config` fallback when `XDG_CONFIG_HOME` is empty.
- `a4f11f5`, `f1c7aba`: unproven index differences kept as named failures, complete captures, and publication witnesses.
- `fd43560`, `cd1b4f1`: an explicit owner for SSH fixtures, with the vc16 default byte-identical.
- `5b6226c`…`56ab7c7`: pruning of finished workspaces driven by the plan's remaining inputs.
- `c36cc1e`, `6472a7b`, `344feea`, `141f1d5`: the live SSH host and fixture root taken from the explicit plan.

## Prediction

`tests/vc17-prediction.txt` was committed at `d321c09`, before any implementation, and each later supplement was committed before its fix. It predicted the following:

- Missing zones fall back to UTC without changing stored numeric offsets.
- `auto` decorates only at a terminal.
- Config edits preserve unrelated bytes and modes, use an exclusive lock and an atomic rename, and keep system writes refused by name.
- The harness rows would be red first: the pruning dependency, the planned SSH host and the relocated SSH client.

The scope stays bounded. There is no reflog-management verb, no system or worktree config writes, no value-pattern or regexp editing, and no custom decoration palette or filter.

## Evidence index

Per native and release tier the gate holds 18 date rows, 82 decoration rows and 70 config rows. Each row keeps the complete argv, environment, stdin, stdout, stderr, exit status and the resulting repository or file state. Terminal rows run in an owned pty, and default ANSI bytes are compared, never stripped. An index difference that neither side's own stat proof explains stays a named failure. Symlink and hardlink witnesses tell an edit of the target apart from a replacement of the link.

Every family was red by name before its code:

| Rows | Red at | Green at |
|---|---|---|
| dates, decorations, config (18, 82 and 61 captures) | `a4f11f5`, kasumi | `7533178` (components take) |
| `config-symlink-target` | `f1c7aba` | `aec1d57` |
| ambiguity-hint dates in the strict no-database container | full take 1 at `76ed228` | `972ce47` |
| `config-global-empty-xdg` | `972ce47` | `9190d24` |
| `ssh-peer-*` owner rows | `fd43560` | `cd1b4f1` |
| `runner-prune-future-input` | `59612e5` | `56ab7c7` |
| `runner-planned-ssh-host` | `c36cc1e` | `6472a7b` |
| `runner-ssh-owned-plan` | `344feea`, satoyama | `e4a341e` |

The final-head gauntlet record and the plant record cover the head that holds this note, so they cannot be part of it. Both are in the pull request's body, with every END line.

## Done-when

- [x] Strict physical no-database date rows, native and release.
- [x] Pty and pipe decorations, `log.decorate` precedence and the default ANSI palette.
- [x] Scoped config bytes, creation, locks, modes and the checked-machine units.
- [x] The live SSH leg's host and root come from the plan, refused before network access otherwise.
- [x] README, MAP, SOURCES and the CHANGELOG say what moved.
- [ ] The full exact-head gauntlet with the live SSH leg, every END zero (the PR body).
- [ ] A one-commit, one-file, one-hunk plant red by name (the PR body).

### Applied R-list

- **R-vc17-1, applied:** an unproven, unequal index is a kept, named difference, never an abort, and the commit rows use a differing `--date` so the date summary shows (`a4f11f5`).
- **R-vc17-2, applied:** `tools/ssh-peer.py --lane` names the fixture's owner. The vc16 default is byte-identical, and mismatched or escaping owners are refused by name (`fd43560`, `cd1b4f1`).
- **R-vc17-3 to R-vc17-5, applied:** the full takes on kasumi kept a disk guard under a lane ceiling, which ended at 16 GiB with a 15 GiB guard and per-leaf cleanup. Each stop was a fresh, complete take, never a composite.
- **R-vc17-6, applied:** pruning derives "finished" from the planner's remaining inputs (`56ab7c7`), red first at `59612e5`.
- **R-vc17-7, applied:** `ssh-test.py` takes its host and root from the explicit plan, with its safety checks against the planned root (`141f1d5`), red first at `344feea`. The same commit lists every other literal `kasumi` or `/lanes/vc16/` under `tools/` and the fixtures.
- **R-vc17-8, recommended and applied (defer):** the installer in `tools/ssh-peer.py` still writes the vc16 host's reservation lock name. A fixture on another host keeps its own lane-owned reserve wrapper. A lock parameter would change the fixture's control digest and needs its own red-first row, so it is left for later work.

### Remaining limits

System config writes, worktree config scope and value-pattern or regexp edits remain named unsupported options, and `include`/`includeIf` are named refusals. Dangling symlinks and nonregular config destinations are refused by name. Remote and tracking edits keep their continued-line, CRLF, BOM, inline-assignment and multiple-URL limits. Custom decoration filters and palettes are outside this surface. The SSH installer's reservation lock name is the vc16 host's. Every inherited wire, merge and object limit in README and MAP stands.
