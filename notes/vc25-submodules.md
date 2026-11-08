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

The rows are `tools/submodule-test.py` through `tools/check-submodule`, native and release. Every row runs one argv for each tool in an identical copy of a seeded world, at the same path, and compares the process result and the complete world afterwards: the superproject, `.git/modules/*`, every submodule worktree and the bare remotes. Loose objects compare by oid and inflated bytes (R4a). Every index compares byte for byte except the six timing and identity words each tool proves against its own lstat (`tools/index-proof.py`), extended for gitlinks by R-vc25-13. The only named difference is den's reflog identity (R-vc18-2): a row whose only differences are reflog files under a gitdir's `logs/` is KNOWN and never counted as parity. The plain-clone rows are `tools/clone-work-test.py` (bytes, upstream and refusals families, every transport), also through `tools/check-submodule`. The units are `src/gitmodules_test.lu` (the 171 relative URLs the pinned Git resolved, insteadOf, suspicious names and the layout's paths), natively, in release and on the checked machine.

### What changed, by item

- **Reading gitlinks (item 3):** `ls-tree` and `ls-files -s` (new, bounded); a gitlink diffs as `Subproject commit <id>`, `-dirty` for modified content; `--submodule=short|log|diff`, `diff.submodule`, `--ignore-submodules` and `submodule.<name>.ignore`; status's long, short and porcelain v1 forms with Git's `(new commits, modified content, untracked content)`, ` M`/` m`/` ?` and the extra hint; `show REV:<gitlink>` says `fatal: bad object`.
- **Clone and the submodule command (item 4):** `clone --recurse-submodules[=<pathspec>]`, `submodule status [--cached] [--recursive]`, `init`, `update [--init] [--recursive] [--force] [-N]`, `sync [--recursive]` and `foreach [--recursive] [-q]`; the layout `.git/modules/<name>`, the worktree's `.git` file and `core.worktree`, as Git writes them; relative URLs as Git resolves them; a recorded commit no ref reaches is fetched by id.
- **Transports (item 5):** `url.<base>.insteadOf` and `pushInsteadOf` for every den transport, and `protocol.allow` / `protocol.<name>.allow` with `GIT_PROTOCOL_FROM_USER`, so file submodules refuse by default exactly as Git's do while a typed file clone works. Anonymous https already asked for credentials only on a 401.
- **Working in the repository (item 6, first half):** `add`, `commit -a`, `reset`, `checkout`, `switch` and `rm` with gitlinks, never entering a submodule's worktree. The rows found Git's index policy for a gitlink and den now follows it: `add` writes no object and leaves an unchanged gitlink's entry alone, stat included; commit never refreshes one; a transition keeps an unchanged gitlink's entry, gives a gitlink moved over its existing directory no stat at all, and gives one whose directory it makes that directory's lstat; a staged gitlink kept through a switch leaves its trees invalid. Commit's status shows a submodule's modified content but never its untracked content; reset lists a submodule only for new commits; `rm` counts untracked content as a local modification; `add` of a path inside a submodule is refused as Git refuses it. `stash` in a superproject is a named refusal.
- **Hostile inputs (item 8):** suspicious names, dash URLs and paths, a missing URL or commit, gitlinks with no entry, invalid `.gitmodules`, invalid values, case-colliding paths, names with `/`.

### Found by the rows, beyond submodules

- den's clone over a URL transport wrote loose remote-tracking refs, quoted every URL in `config` and left an empty `hooks/`, where Git packs the refs, quotes only when needed and has no `hooks/` (with the empty template). Earlier rows compared refs and config semantically; byte comparison found it.
- den's switch and checkout printed neither the local changes (`M\t<path>`) nor the tracking lines Git prints on stdout.
- For an unterminated config section header Git reports the next line, having read the newline.
- `checkout`, `switch` and `reset` refused in any repository whose branches have upstreams, which is every clone and so every superproject. They now run there (R-vc25-14); making a tracking branch, from a remote-tracking start point or by guessing a remote's branch of the same name, stays a named refusal. `tools/clone-work-test.py` holds this outside submodules, in a plain clone made over every transport (a local path, `file://`, `git://`, ssh and https): `switch` and `checkout` to new, existing, behind and ahead branches and detached, `checkout <tree-ish> -- <paths>` (new: den took only `checkout -- <paths>` before), and `reset --soft`, `--mixed` and `--hard`, each tool cloning and then running the same steps, compared byte for byte; and the two refusals by name. Those rows were red at vc24's head, where den still refused (`notes/vc25-evidence/clone-work-red-at-vc24.txt`: 60 of 60 work rows failed by name).
- The same harness compares a plain clone and a bare clone over every transport byte for byte: packed refs, `config` and its quoting, HEAD, the pack with its idx and reverse index, the index and the worktree. Git writes the same bytes over each transport, and den now does too.
- `submodule update` clones every submodule before checking any out, and the first clone that fails twice ends it, so the others stay cloned but not checked out, as in Git.

## Done-when

- [x] Census and prediction first; the census aggregates only in tracked text.
- [x] Every family red first at the base by name, then green.
- [ ] The final gauntlet, the plant and the audit at the head: their records and every END line are in the PR body.

### Applied R-list

- **R-vc25-1 = A, as ruled:** no vc25b item moved in; `submodule add` is vc25b's first item.
- **R-vc25-2:** Git's defaults: `submodule.recurse` false, clone not recursive, fetch on demand, push `no`.
- **R-vc25-3:** push under `submodule.recurse=true` refuses by name (second half).
- **R-vc25-4:** the tracked timed row is wolf-web; the largest census superproject (about 485 MB, its largest submodule llama.cpp) is measured locally and described by shape.
- **R-vc25-5:** bounded `ls-tree` and `ls-files`.
- **R-vc25-6:** an internal describe for `submodule status`: an annotated tag, else any ref, else the abbreviated id.
- **R-vc25-7:** checkout-only updates; `none` skips; `merge`, `rebase` and `!command` refused.
- **R-vc25-8:** `status.submoduleSummary` and `submodule summary` refused by name.
- **R-vc25-9:** one-sided gitlink merges pass through; both moved refuses by name (second half).
- **R-vc25-10:** the protocol policy on every transport, as git-config(1) describes it: `user` admits a file clone the user typed and refuses it inside submodule recursion.
- **R-vc25-11:** an untracked nested repository is shown as Git shows it; `add` of one stays refused.
- **R-vc25-12:** a recorded commit no advertised ref reaches is fetched by id; the server's refusal is relayed.
- **R-vc25-13 (new):** a gitlink's index entry keeps its directory's stat from when the superproject's checkout made it, before the submodule filled it, in Git as in den, so its time words cannot match the directory afterwards. The harness counts such an entry proven when its dev and ino equal its directory's and its times are no later than the directory's; mode, uid, gid and size stay exact. Options: (a) as built; (b) zero both sides' gitlink time words without a proof (rejected: weaker than R4a); (c) refresh gitlink stat after population (rejected: Git does not).
- **R-vc25-14 (new):** `checkout`, `switch` and `reset` where branches have upstreams. Options: (a) as built: they run, reading an upstream only for the report Git prints, while upstream setup and the remote branch guess are named refusals; (b) keep den's refusal and strip the upstream from the rows' clones (rejected: the rows would never meet a superproject as a clone leaves it); (c) implement upstream setup and the guess (rejected: not this lane's).
- **R-vc25-15 (new):** case-colliding submodule paths on a case-insensitive file system. The pinned Git's rows on Linux prove them; on macOS the field Git observes `core.ignorecase`, which den does not implement. Options: (a) as built: field mode excludes those seven rows by name, printed and counted as excluded, never as passes; (b) implement `core.ignorecase` (rejected: every command, not this lane's); (c) drop the rows (rejected: Linux proves them).

### Remaining limits

`submodule add`, `deinit`, `set-url`, `set-branch`, `summary` and `absorbgitdirs`; `push --recurse-submodules` in every form; clone's `--shallow-submodules`, `--remote-submodules`, `-j` and `--reference`; `update --remote`, `--merge`, `--rebase` and those update modes; `shallow = true`; `status.submoduleSummary`; `mv` of a submodule; `restore` of a gitlink path; `stash` with a gitlink; `blame` of a gitlink path; `status --porcelain=v2` with a submodule; `extensions.submodulePathConfig`; old-form submodules for update and sync; `foreach` without `/bin/sh`. `stash` in a superproject; upstream setup from a remote-tracking start point and the remote branch guess in `checkout` and `switch`. `--raw`, `--summary`, `log --name-status` and `reset` with paths are den limits for every repository, not only superprojects.
