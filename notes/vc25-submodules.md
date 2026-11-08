# vc25 — submodules, cloned and worked in as with Git

den reads, clones and works in repositories with submodules the way the pinned Git does: gitlinks in every reader, status and diff of submodule worktrees, `clone --recurse-submodules`, `submodule status|init|update|sync|foreach`, relative URLs, `url.<base>.insteadOf` and `pushInsteadOf`, the protocol policy, and the hostile inputs Git guards against. The authoring commands (`submodule add`, `deinit`, `set-url`, `set-branch`, `absorbgitdirs`), `push --recurse-submodules` and `--shallow-submodules` stay named refusals for a following lane.

Footprint: cross-cutting (tools/gate, tools/gate-record and ci/tiers-test.py gain the submodule step)

## Forbidden

Clean room: Git's documentation and the pinned Git run as a black box, and nothing else. No Git, libgit2, JGit or other implementation source was read. Pages read: gitsubmodules(7), git-submodule(1), gitmodules(5), gitrepository-layout(5) (`modules/`), git-clone(1), git-config(1) (`submodule.*`, `submodule.recurse`, `extensions.submodulePathConfig`, `url.<base>.insteadOf`, `pushInsteadOf`, `protocol.allow`, `protocol.<name>.allow`, `fetch.recurseSubmodules`, `push.recurseSubmodules`, `diff.submodule`, `status.submoduleSummary`), git-status(1), git-diff(1), git-fetch(1), git-pull(1), git-checkout(1), git-switch(1), git-reset(1), git-rm(1), git-add(1), git-commit(1), git-ls-tree(1), git-ls-files(1), git-push(1), all at 2.56.0. The census read public repository metadata only, through the GitHub API; nothing was cloned for it, and the per-repository table stays outside the repository. Live rows use public repositories of this organisation only.

## Inputs verified

- **Base:** den trunk `474a926`, branch `vc25`.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58 and wolf-std `d4a4d4c`, unchanged.
- **Oracle:** Git 2.56.0, executable `c4848492…`, read twice before each take. A field Git 2.56.0 on macOS serves development rows and the macOS record's leg (the harness's field mode, which the gate never sets): a field observation, never oracle parity.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, 46 GiB | the oracle probes (a two-CPU light slot, no network), builds, rows and records on a six-CPU block holding both of its locks, in the pinned oracle container |
| Apple silicon laptop, macOS arm64 | editing, native builds behind the build lock, field-mode rows against the field Git, the macOS record |
| a second Apple silicon laptop, macOS arm64 | native builds behind its own build lock while the first one's was held; the binaries ran their field rows on the first |

## Prediction

`tests/vc25-prediction.txt`, committed first (`e0761d7`), after two black-box probes of the pinned Git (`notes/vc25-evidence/oracle-probe-1.jsonl`, 383 steps; `-2.jsonl`, 118 steps) and the census (`notes/vc25-evidence/census.json`, aggregates). What held and what did not is under each item below.

## Evidence index

The rows are `tools/submodule-test.py` through `tools/check-submodule`, native and release. Every row runs one argv for each tool in an identical copy of a seeded world, at the same path, and compares the process result and the complete world afterwards: the superproject, `.git/modules/*`, every submodule worktree and the bare remotes. Loose objects compare by oid and inflated bytes (R4a). Every index compares byte for byte except the six timing and identity words each tool proves against its own lstat (`tools/index-proof.py`), extended for gitlinks by R-vc25-13. The only named difference is den's reflog identity (R-vc18-2): a row whose only differences are reflog files under a gitdir's `logs/` is KNOWN and never counted as parity. The plain-clone rows are `tools/clone-work-test.py` (bytes, upstream and refusals families over every transport, and the report family over a local path), also through `tools/check-submodule`. The units are `src/gitmodules_test.lu` (the 171 relative URLs the pinned Git resolved, insteadOf, suspicious names and the layout's paths), natively, in release and on the checked machine.

### What changed, by item

- **Reading gitlinks (item 3):** `ls-tree` and `ls-files -s` (new, bounded); a gitlink diffs as `Subproject commit <id>`, `-dirty` for modified content; `--submodule=short|log|diff`, `diff.submodule`, `--ignore-submodules` and `submodule.<name>.ignore`; status's long, short and porcelain v1 forms with Git's `(new commits, modified content, untracked content)`, ` M`/` m`/` ?` and the extra hint; `show REV:<gitlink>` says `fatal: bad object`.
- **Clone and the submodule command (item 4):** `clone --recurse-submodules[=<pathspec>]`, `submodule status [--cached] [--recursive]`, `init`, `update [--init] [--recursive] [--force] [-N]`, `sync [--recursive]` and `foreach [--recursive] [-q]`; the layout `.git/modules/<name>`, the worktree's `.git` file and `core.worktree`, as Git writes them; relative URLs as Git resolves them; a recorded commit no ref reaches is fetched by id.
- **Transports (item 5):** `url.<base>.insteadOf` and `pushInsteadOf` for every den transport, and `protocol.allow` / `protocol.<name>.allow` with `GIT_PROTOCOL_FROM_USER`, so file submodules refuse by default exactly as Git's do while a typed file clone works. Anonymous https already asked for credentials only on a 401.
- **Working in the repository (item 6, first half):** `add`, `commit -a`, `reset`, `checkout`, `switch` and `rm` with gitlinks, never entering a submodule's worktree. The rows found Git's index policy for a gitlink and den now follows it: `add` writes no object and leaves an unchanged gitlink's entry alone, stat included; commit never refreshes one; a transition keeps an unchanged gitlink's entry, gives a gitlink moved over its existing directory no stat at all, and gives one whose directory it makes that directory's lstat; a staged gitlink kept through a switch leaves its trees invalid. Commit's status shows a submodule's modified content but never its untracked content; reset lists a submodule only for new commits; `rm` counts untracked content as a local modification; `add` of a path inside a submodule is refused as Git refuses it. `stash` in a superproject is a named refusal.
- **Working in the repository (item 6, second half):** fetch on demand, after `fetch` and before `pull`'s merge: a submodule is fetched when a fetched commit records a commit its repository lacks, in path order, nested ones too, and one that has only its repository is fetched there; `--recurse-submodules[=yes|on-demand|no]`, `fetch.recurseSubmodules`, `submodule.<name>.fetchRecurseSubmodules` (the command line wins) and `submodule.recurse` (as yes); Git's `Errors during submodule fetch:` list and exit 1, and a pull that then stops before its merge. Unlike the clone in an update, Git's submodule fetch keeps the user's protocol policy, so a `file://` submodule is fetched by default, and den's does too. `pull` merges a gitlink one side moved through, as a fast-forward or a true merge, with the gitlink's line in the diffstat (R-vc25-9); one both sides moved is refused by name. With `--recurse-submodules` or `submodule.recurse`, checkout, switch, a hard reset and pull move each active submodule whose recorded commit changed, detached; a submodule file the move would overwrite refuses the checkout first with Git's `Entry ... not uptodate` lines unless `-f`; a submodule the target drops is emptied (files, index, `core.worktree`; its repository stays) and filled again on the way back; pull prints update's `Submodule path` lines, nested ones only with the option (with `submodule.recurse` each submodule's own checkout recurses and prints nothing). A soft or mixed reset leaves worktrees alone. The rows are the `fetch` and `recurse` families.
- **Hostile inputs (item 8):** suspicious names, dash URLs and paths, a missing URL or commit, gitlinks with no entry, invalid `.gitmodules`, invalid values, case-colliding paths, names with `/`.

### Found by the rows, beyond submodules

- den's clone over a URL transport wrote loose remote-tracking refs, quoted every URL in `config` and left an empty `hooks/`, where Git packs the refs, quotes only when needed and has no `hooks/` (with the empty template). Earlier rows compared refs and config semantically; byte comparison found it.
- den's switch and checkout printed neither the local changes (`M\t<path>`) nor the tracking lines Git prints on stdout.
- For an unterminated config section header Git reports the next line, having read the newline.
- `checkout`, `switch` and `reset` refused in any repository whose branches have upstreams, which is every clone and so every superproject. They now run there (R-vc25-14); making a tracking branch, from a remote-tracking start point or by guessing a remote's branch of the same name, stays a named refusal. `tools/clone-work-test.py` holds this outside submodules, in a plain clone made over every transport (a local path, `file://`, `git://`, ssh and https): `switch` and `checkout` to new, existing, behind and ahead branches and detached, `checkout <tree-ish> -- <paths>` (new: den took only `checkout -- <paths>` before), and `reset --soft`, `--mixed` and `--hard`, each tool cloning and then running the same steps, compared byte for byte; and the two refusals by name. Those rows were red at vc24's head, where den still refused (`notes/vc25-evidence/clone-work-red-at-vc24.txt`: 60 of 60 work rows failed by name).
- The same harness compares a plain clone and a bare clone over every transport byte for byte: packed refs, `config` and its quoting, HEAD, the pack with its idx and reverse index, the index and the worktree. Git writes the same bytes over each transport, and den now does too.
- Git prints `Updating files` progress on a piped stderr once a reset or a recursive move runs past `GIT_PROGRESS_DELAY` (git(1): two seconds by default), so on a loaded machine a row's stderr changed. Both harnesses now set the delay out of reach. Other harnesses that run `reset --hard` against Git carry the same exposure.
- A seed world's indexes were written in the same clock tick as its files, so every entry was racily clean (its mtime equal to the index's). Refreshing a racily clean entry in a nested submodule, Git kept or replaced its stat by timing: one diff row's nested index differed from run to run on a loaded machine, with Git's own entry left stale and den's refreshed. `tools/submodule-test.py` now dates each seed's indexes a second after its newest file, leaving their bytes as Git wrote them.
- `submodule update` clones every submodule before checking any out, and the first clone that fails twice ends it, so the others stay cloned but not checked out, as in Git.

### The live self-clone row and den's origin

`http-live-self` (vc23's row, in the http leaf) clones den's own public repository with both tools and compares the clones ref for ref. A clone takes HEAD, every branch and every tag, so the row's guard holds all of them: a lane pushing any branch to den's origin while the row runs moves what the two clones took, and the row fails by name (`den's refs moved during the row`), as a development take of this branch did. The guard also counted GitHub's `refs/pull/*`, which no clone fetches and which GitHub rewrites on its own; it no longer does (`tools/http-live-test.py`'s `http-live-guard` self-check, red first). A record therefore needs a quiet window on den's origin, with no branch or tag pushed there, while the http leaf runs.

### Finals found red: the list after a move, and a config line

The first full gauntlet at this branch's head failed in the refs leaf on one row, `extra-dirty-7`: after `switch -c new` with a modified file, Git prints nothing on stdout and den printed `M\ta`. A bisect between vc24's head, where the row is parity, and this branch's head names the commit that made checkout and switch print the local changes, "Print checkout's local changes and tracking lines as Git does": red there, parity at its parent. Rebased onto vc24's head, the commits between the clone-path changes and their two later build fixes do not build alone, so the bisect gave each such commit those two fixes, which touch only `src/wiregit/fetch.lu` (`notes/vc25-evidence/refs-extra-dirty-7-bisect.txt`).

Probed black-box against Git 2.56.0: Git lists no local changes after `switch` names no start point (`-c`, `-C` or `--detach` alone) or after `checkout -b` names none, while `checkout -B` and `checkout --detach` without one still list them; the tracking lines print either way. The same probes found two more differences. Git lists a staged change too, by how the worktree differs from HEAD (`M`, `A`, `D`; a staged rename as its two paths, `D` then `A`; nothing for a path added and then deleted), where den listed only unstaged changes. And a staged change that a switch keeps leaves its trees invalid in Git's index, where den wrote a valid tree over it (only a kept gitlink was left invalid before). All three are fixed. The report family of `tools/clone-work-test.py` holds them in 22 rows, each tool cloning and then making the same edit and move: 12 rows failed before the fixes, the 8 staged rows still failed on the tree extension alone with only the list fixed, and none fail after (KNOWN rows differ only in den's reflog identity; `notes/vc25-evidence/report-rows.txt`). To compare those rows the harness proves an index entry that a row's own edit left stale by the lstat its tool saw before the edit, the same file by device and inode.

The next final, with that fixed, failed in the config leaf on one row, `config-file-bad-local-preflight`: for a `.git/config` whose last line is `[broken`, Git reports `bad config line 6` and den reported line 7. Both tools read the same bytes; den counted the newline after an unterminated section name, a rule taken from one `.gitmodules` row ("Count the newline an unterminated config header stops on") and wider than Git's. The row is red at that commit and parity at its parent, each built with the same later fetch fix (`notes/vc25-evidence/config-row-bisect.txt`). Measured against the pinned Git on 28 broken headers (`notes/vc25-evidence/config-header-lines.tsv`): a newline, or CRLF, right after a subsection's closing quote is counted as a line, a newline after a section name or after a blank is not, and the end of the file right after a closing quote is counted; a newline inside the quotes is reported on its own line, and Git takes no blank between the closing quote and the bracket. Units in `src/gitmodules_test.lu` hold 25 of them: 13 failed before the fix, none after, and the whole config leaf passes. The three left out end the file right after a section name (`[bad`): Git reports the next line there, while `tools/config-test.py`, which states den's expectations without running Git, expects the same line, and den keeps it.

The next two finals passed every row and failed at the last leaf, the guard over CI's evidence upload (`tools/evidence-modes.py`): the plain-clone https fixture wrote its test CA and leaf keys under `target/runs`, at mode 0600, so unreadable and private keys in the upload. The guard is right that no key goes into evidence, a test key included. The fixture now keeps its keys under `target/pki`, as the wire fixtures do.

The macOS record now also runs the gate's own leaves over the commands this branch changes that run against a field Git (refs, merge, replay, diff units, index, ignore, worktree and commit) and the config leaf's units and `tools/config-test.py`, besides the submodule and plain-clone families. The stash, revision, history, everyday and status-speed leaves, and the config leaf's day-to-day rows, assert the pinned Linux Git's digest, so they run in the Linux final only, and a check against the pinned Git runs the config and refs leaves whole before each final.

### Live rows (public wolffe-lang superprojects)

`tools/submodule-live-test.py`, natively through `tools/check-submodule`, over https against github.com, read-only: `live-wolf-web` clones wolf-web with `--recurse-submodules` by each tool (four submodules two levels down, names unlike their paths) and compares the process bytes and, for the superproject and every repository under `.git/modules`, refs, HEAD, every reachable object, the config file's bytes and the worktree; its guard holds what the clones take, the superproject's and every submodule remote's branches and tags, and retries once. `live-wolf-interp-gitlinks`, `live-wolf-std-gitlinks` and `live-wolf-lsp-gitlinks` read the commit that last moved each release-pinned gitlink (`submodule status` and `--cached`, `ls-tree` at that commit, its parent and HEAD, `ls-files -s`, `cat-file -p` of its tree, `rev-parse <commit>:upstream`) in one clone, by both tools, byte for byte. These repositories carry `.gitattributes`, so `log -- <path>`, `diff` and `status` there meet den limits for every repository (path-limited history, worktree attributes) and are left out of the rows. `live-wolf-std-ssh` runs only with `DEN_LIVE_SSH=1`, where an ssh key for github.com answers, and is a named SKIP otherwise. Every row is a named SKIP without github.com or a root bundle.

### Measured (item 10)

All on the Apple silicon laptop, each tool's clone interleaved with the other's, behind the build lock, against the field Git 2.56.0; wall time and the clone's own CPU from wait4 (`tools/submodule-live-test.py --timed`). A measurement, not a gate.

| clone (`-q --recurse-submodules`) | runs | Git wall | den wall | wall ratio | Git CPU | den CPU | CPU ratio |
|---|---|---|---|---|---|---|---|
| wolf-web, den with this lane's own transition reader | 3 | 95.4 s | 492.7 s | 5.17x (4.70 to 5.67) | 25.2 s | 240.1 s | 9.54x (9.48 to 10.10) |
| wolf-web, den with vc24's checkout reader instead | 1 | 68.6 s | 302.6 s | 4.41x | 25.7 s | 221.8 s | 8.63x |
| a public superproject of about 485 MB whose largest submodule is llama.cpp, two scp-like URLs through `url.https://github.com/.insteadOf`, vc24's reader | 1 | 192.2 s | 430.5 s | 2.24x | 37.3 s | 294.9 s | 7.92x |

Medians, with the spread over the three runs. Peak RSS: Git about 130 MB and den about 750 MB for wolf-web; about 333 MB and 651 MB for the larger one.

Against the prediction (wall 1.6x, from 1.3x to 2.2x; CPU 9x, from 6x to 13x): CPU falls inside it, wall falls outside it for wolf-web. The cause of the wall gap is not profiled. Git's clone here is mostly waiting on the network while den's is mostly computing (240 of 493 s), so den's https and pack-indexing CPU is the likely place, not proven. Before either reader, a transition loaded the pack index once per blob, and den's wolf-web clone did not finish in 27 minutes (25,777 files): that is the cost vc24's checkout reader removes, and this lane's own reader for it is dropped in favour of vc24's.

### A refusal during the work

Before the timed row ran, I asked to stop my own queued timed job (it was only waiting for the build lock) so the row families could run first on the new build. The session's permission classifier refused it ("Interfere With Workloads"). The job was left to run, and the families were run after it instead, so neither perturbed the other's timing; no other way of stopping it was tried.

### PAX: the px lane's items (item 9, draft)

A px lane wires a submodule witness into the next stick. Its items, for that lane to take as written or amend:

1. **Fixture:** a superproject with two submodules, one of them holding a nested submodule, built on the Linux host with the pinned Git and served from the stick's own file system (no network), with relative URLs for the nested one and an absolute `file://` URL for the other, as `tools/submodule-test.py`'s remotes are.
2. **Session:** a typed session on a dev image runs the image's den: `clone --recurse-submodules` with `protocol.file.allow=always`, then `submodule status --recursive`, `status`, and `diff --submodule=log` after a commit moved in one submodule.
3. **Held to Linux's den byte for byte:** the session's stdout and stderr, and the whole clone (superproject, `.git/modules/*` at both depths, the worktree files and `.git` files, `core.worktree`), against the same commands run by den on Linux over the same fixture at the same path. Reflogs differ only by den's own identity on both sides, so they are compared too.
4. **Red first:** the stick's witness is red against an image whose den predates submodule support (`den: not yet implemented: submodule`), then green.
5. **Limits carried over:** everything named in this note's remaining limits; no network transport on the stick.

## Done-when

- [x] Census and prediction first; the census aggregates only in tracked text.
- [x] Every family red first at the base by name, then green.
- [ ] The final gauntlet, the plant and the audit at the head: their records and every END line are in the PR body.

### Applied R-list

- **R-vc25-1 = A, as ruled:** no vc25b item moved in; `submodule add` is vc25b's first item.
- **R-vc25-2:** Git's defaults: `submodule.recurse` false, clone not recursive, fetch on demand, push `no`.
- **R-vc25-3:** push under `submodule.recurse=true` refuses by name.
- **R-vc25-4:** the tracked timed row is wolf-web; the largest census superproject (about 485 MB, its largest submodule llama.cpp) is measured locally and described by shape.
- **R-vc25-5:** bounded `ls-tree` and `ls-files`.
- **R-vc25-6:** an internal describe for `submodule status`: an annotated tag, else any ref, else the abbreviated id.
- **R-vc25-7:** checkout-only updates; `none` skips; `merge`, `rebase` and `!command` refused.
- **R-vc25-8:** `status.submoduleSummary` and `submodule summary` refused by name.
- **R-vc25-9:** one-sided gitlink merges pass through; both moved refuses by name.
- **R-vc25-10:** the protocol policy on every transport, as git-config(1) describes it: `user` admits a file clone the user typed and refuses it inside submodule recursion.
- **R-vc25-11:** an untracked nested repository is shown as Git shows it; `add` of one stays refused.
- **R-vc25-12:** a recorded commit no advertised ref reaches is fetched by id; the server's refusal is relayed.
- **R-vc25-13 (new):** a gitlink's index entry keeps its directory's stat from when the superproject's checkout made it, before the submodule filled it, in Git as in den, so its time words cannot match the directory afterwards. The harness counts such an entry proven when its dev and ino equal its directory's and its times are no later than the directory's; mode, uid, gid and size stay exact. Options: (a) as built; (b) zero both sides' gitlink time words without a proof (rejected: weaker than R4a); (c) refresh gitlink stat after population (rejected: Git does not).
- **R-vc25-14 (new):** `checkout`, `switch` and `reset` where branches have upstreams. Options: (a) as built: they run, reading an upstream only for the report Git prints, while upstream setup and the remote branch guess are named refusals; (b) keep den's refusal and strip the upstream from the rows' clones (rejected: the rows would never meet a superproject as a clone leaves it); (c) implement upstream setup and the guess (rejected: not this lane's).
- **R-vc25-15 (new):** case-colliding submodule paths on a case-insensitive file system. The pinned Git's rows on Linux prove them; on macOS the field Git observes `core.ignorecase`, which den does not implement. Options: (a) as built: field mode excludes those seven rows by name, printed and counted as excluded, never as passes; (b) implement `core.ignorecase` (rejected: every command, not this lane's); (c) drop the rows (rejected: Linux proves them).

### Remaining limits

`submodule add`, `deinit`, `set-url`, `set-branch`, `summary` and `absorbgitdirs`; `push --recurse-submodules` in every form; clone's `--shallow-submodules`, `--remote-submodules`, `-j` and `--reference`; `update --remote`, `--merge`, `--rebase` and those update modes; `shallow = true`; `status.submoduleSummary`; `mv` of a submodule; `restore` of a gitlink path; `stash` with a gitlink; `blame` of a gitlink path; `status --porcelain=v2` with a submodule; `extensions.submodulePathConfig`; old-form submodules for update and sync; `foreach` without `/bin/sh`. With recursion: `reset --keep` and `--merge`, `checkout` of paths and `--orphan`; a recorded commit still missing after a submodule's on-demand fetch is asked for again by den's ordinary fetch, not by its id. `stash` in a superproject; upstream setup from a remote-tracking start point and the remote branch guess in `checkout` and `switch`. `--raw`, `--summary`, `log --name-status` and `reset` with paths are den limits for every repository, not only superprojects.
