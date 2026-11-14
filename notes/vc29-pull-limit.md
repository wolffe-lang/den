# vc29 — pull stops with "fatal: limit" (den#100)

`den pull origin trunk` in a checkout of a mid-sized repository printed nothing for a few tens of seconds and then `fatal: limit`. Reproduced with the den the issue was reported with: a true-merge pull beside one unrelated untracked file of 1,500,000,000 bytes prints the fetch lines and then `fatal: limit`, exit 128, HEAD unchanged; the pinned Git pulls in about 0.01 s. The bound was the work tree scan's 1,000,000,000-byte read of a single file: before planning a merge, den read the body of every untracked and ignored file in the work tree. Now merge, checkout, switch, reset, pull and the replay commands read no untracked or ignored body, attribute files that set nothing den acts on are accepted, and every bound fetch, pull, clone, merge and checkout can reach prints as `fatal: limit: <the bound and its value>`.

Footprint: module

## Forbidden

Clean room: Git's documentation (git-pull, git-merge, git-checkout, gitignore, gitattributes) and black-box runs of the pinned Git 2.56.0 only. No Git or other implementation source was read. Organisation code read: den, and the wolf language specification's memory model (regions and the ambient allocation rule). No CI, pin or shared tooling changed. The submodule authoring files are untouched.

## Inputs, verified

- **Base:** den trunk `2ca9d1f`, unchanged at the final head; den#100.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58, wolf-std `d4a4d4c`, archives checked against `wolf-toolchain.toml`.
- **Oracle:** Git 2.56.0, executable SHA-256 `c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`, checked by every row.
- **The reported den:** the binary the issue was reported with, built from `a749692` with wolf 0.2.36, executable SHA-256 `e01b760da49e195bd1e2da680e0273f9eb28f3e98bbdd861659ad2435562ba1f`.

## Prediction

Written before each change and kept with the lane's evidence.

- The reported den reads the body of every untracked and ignored file before a merge or a fast-forward, and stops at the scan's per-file bound (1,000,000,000 bytes), its aggregate (1,000,000,000 bytes) or its count (1,000,000 paths); a true merge prints a bare `fatal: limit`, a fast-forward `den: not yet implemented: merge safety: limit`. Git succeeds in every such case and reads none of those bodies. **Measured as predicted** (below).
- A transition needs tracked files' ids and the paths it writes. Comparing tracked files by their index stat (or a hash taken as the file streams), keeping one opaque entry for an untracked directory with no tracked path below it and looking up target paths below it by name, and leaving ignored paths out, makes every scan row equal Git's output and HEAD, with den reading at most a few kilobytes beside 1.5 GB of untracked or ignored data. Existing refusals for untracked files in the way, and the protection below nested repositories, stay exact.
- Ignored rows were counted as local changes by the true merge and by cherry-pick, so any ignored file in the work tree refused a true-merge or rebase pull; leaving ignored paths out of the transition scan ends that.
- An attribute file that sets only attributes den need not act on behaves in Git exactly as no attribute file; accepting those, and refusing the rest by the attribute's name, makes status, `commit -a`, every pull and a switch equal Git's in such a repository.
- Every bound reachable from fetch, pull, clone, merge and checkout can name itself; a static census keeps the code those commands run free of unnamed bounds.
- With no ancestry walk or tree load for equal tips, one pack reader per walk and only the compared bodies loaded, an up-to-date pull of a repository the issue's size takes about as long as its fetch, and a moved pull stays far under the 3.2 GiB and four minutes measured before.

## Evidence index

### What the reported den and Git do

Each case is a pull beside material the merge does not need, the seed committing a `.gitignore` so no case dirties a tracked file. Git exits 0 in every case in 0.009 to 0.026 s and reads at most 47 KB.

| beside the pull | the reported den, true merge | the reported den, fast-forward | bytes den read |
|---|---|---|---|
| one untracked 1,500,000,000-byte file | `fatal: limit`, exit 128 | `den: not yet implemented: merge safety: limit`, exit 2 | 1,000,066,358 |
| the same file, ignored | the same | the same | 1,000,066,358 |
| an ignored tree of three 400,000,000-byte files | the same (the aggregate bound) | the same | 1,200,052,559 |
| 1,000,001 empty files, untracked or ignored | the same (the count bound) | the same | 52,559 (each file opened) |

Reading a 1,000,000,000-byte body peaked at 2.0 GB resident, the ignored tree at 3.5 GB and the million files at 8.5 GB. HEAD is unchanged in every case. A bare `fatal: limit` comes only from the true merge; a bound the fetch reaches printed `den: wire: Unsupported(pull fetch: limit)`.

Paths in a transition's way, measured on the pinned Git for a fast-forward, a true merge and a switch: an untracked file at a target path refuses (also below an untracked directory, and also when its bytes equal the target's); an ignored file or an ignored directory at or above a target path is overwritten; an untracked or ignored file elsewhere is kept. den refused every ignored path in the way, and its true merge refused any ignored file anywhere (`merge dirty recursive recovery`); a rebase pull beside any ignored file failed in cherry-pick's own dirt check. A rebase pull refused for an untracked file printed Git's refusal without Git's last line, `error: could not detach HEAD`.

Git pulls a commit changing 4,531 paths (2,500 modified, 2,001 added, 30 renamed) with its full stat and summary, exit 0.

### den's change

- **The transition scan** (`scan_index`, used by merge, checkout, switch, reset, pull, rm, merge `--abort` and the replay commands): a tracked file is compared by its index stat, or hashed as it streams when its stat differs; its body is never held. An untracked directory with no tracked path below it is one opaque entry, never entered, as a nested repository already was; the transition looks up its own target paths below it by name, so an untracked file there still blocks, and an ignored one is overwritten. Ignored files and directories are left out entirely. An untracked file's scanned id is a placeholder no transition trusts: its path is always written. A transition verifies only the blobs it writes, and reads a written file back by streaming hash. `commit` and `stash`, which store bodies, keep the full scan.
- **Ignored paths are not local changes:** the true merge's dirt checks skip ignored rows, and the scan no longer lists them for cherry-pick, revert or rebase.
- **A rebase blocked at its first checkout** prints Git's two lines.
- **Attribute files** are read, not refused for existing: a file that sets only attributes den need not act on is accepted; any other refuses by the attribute's name (`worktree attributes: eol`), as does a macro definition.
- **Named bounds:** every bound fetch, pull, clone, merge and checkout reach is `fatal: limit: <the bound and its value>`, exit 128, from every printer those commands use, through the wrappers that used to rename it (`merge safety:`, `clone checkout:`, `pull rebase index refresh:`, the fetch's submodule tips). An empty want list was misnamed a limit; it is invalid input.
- **Bound messages are literals.** A callee allocates in its caller's current region, so a message built at run time inside a read that the caller ran within a region block was freed when the error left the block, and printing it crashed (the merge rows found this, exit -11). Each message is a literal, chosen by the constant bound where the cap varies; the object's id or the file's path is no longer in the message.
- **A merge's stat after the update:** the merge's state files are removed before the stat is printed, so a stat that reaches a bound leaves no unfinished merge, and the bound is named. The summary rows below the stat no longer count lines, which the stat already did.
- **Speed:** equal tips skip the ancestry walk and every tree and body read; a merge loads only the bodies whose ids differ, through one pack reader per walk; the change summary, and the fetch's per-ref object reads, use one pack reader each, where every read parsed every pack index. A fetch walks the closure of what it fetched only when a tag it lacks might follow, and checks a received pack's closure up to the objects the repository already held, as Git does, where both walks read every object in the repository.

### Rows

- `tools/pull-scan-test.py` (both tiers): 56 rows, a true merge, a fast-forward, a rebase pull and a switch each beside the five scan cases and nine paths-in-the-way shapes; every row equal to Git's exit status, stdout, stderr, HEAD and the in-the-way paths' bytes, with den under 64 MiB read and 256 MiB resident. Red first: 41 of the 56 failed before the fix.
- `tools/attributes-test.py` (both tiers): 85 rows, five accepted attribute files under status, short status, `commit -a`, three pulls and a switch, equal to Git's output, HEAD, index and every file's bytes (CRLF bodies included); ten refused files under status, three pulls and a switch, each refused by name with nothing changed.
- `tools/limit-test.py` (both tiers): ten rows that trip a bound through the command line (a 17 MB changed file under merge and pull; 257 packs under fetch, pull, checkout and merge; a 20 MB packed-refs under fetch; a 5,000-byte URL under clone; a 2,500-line rewrite under pull and merge, after the update is published), each `fatal: limit: …`, exit 128, no bare line.
- `tools/limit-census.py`: no statement in the code those commands run originates an unnamed bound.
- `tools/pull-scale-test.py` (native): the up-to-date, fast-forward and true-merge pulls of a generated repository the issue's size, equal to Git, under CPU and resident-set bounds; numbers below.
- The history, object and pack rows now expect the named bounds.

### Pulls of a repository the issue's size

`tools/pull-scale-test.py` builds 10,500 files in 1,000 directories and 5,000 commits, the clone's objects spread over 44 packs, and pulls with the remote 20 commits ahead (a fast-forward, and a true merge with one local commit) and with nothing to fetch. Before this change an up-to-date pull of the issue's repository took 6 min 55 s and a moved one peaked at 3.2 GiB and refused after four minutes; at the head before the last two fetch changes, the generated up-to-date pull still took 102 s of CPU (Git 0.012 s), all of it in tag following's walk of every object, and a moved pull spent minutes re-reading the whole repository after receiving its pack. The record's `pull-scale` lines give den's and Git's wall time, CPU time and peak resident set for each pull at the final head, with the bounds the row holds (10 s of CPU and 512 MiB for the up-to-date pull, 90 s and 120 s with 768 MiB for the moved ones) and the resident-set floor any child of the test's parent starts from.

### Decisions

1. **What a transition scans.** An untracked directory with no tracked path below it is one opaque entry probed by name, and ignored paths are left out and overwritten, as the pinned Git does. The alternatives were listing every untracked file's metadata (a large untracked tree still reaches the million-path count) or keeping ignored files as blockers (Git overwrites them). Recommended and implemented: the first.
2. **How a bound is printed.** `fatal: limit: <the bound and its value>`, exit 128, the exit status the bare line had: carried by `Fatal` where an error set has it and by `Unsupported("limit: …")` elsewhere, mapped by the printers of fetch, pull, clone, merge and checkout. The alternatives were a new error variant in every set on these paths (a wide change across modules other work is in), or `den: not yet implemented: limit: …`, exit 2 (a bound is not an unimplemented feature). Recommended and implemented: the first.
3. **Literal bound messages.** A message built at run time can be freed with the region its read ran in; every bound message is a literal, without the object's id or the file's path. The alternative, building each message at its call site outside any region, touches every caller of the object store. A compiler that refused an error carrying a region's bytes out of the region would remove the hazard at its source; that is outside den.
4. **Attributes.** Accept attribute files that set only what den need not act on and refuse the rest by name, rather than implementing line-ending conversion, filters and drivers here (each a lane of its own). The refusal names the attribute, not the file (decision 3).
5. **A bound the merge's stat reaches** after the update is named, and leaves no merge state behind; matching Git's unbounded diffstat and its rename limit is a follow-up.
6. **A received pack's closure** is checked up to the objects the repository already held, which are read and typed but not walked: the repository was complete before the fetch, as Git assumes. The alternative, walking every object in the repository on every fetch, was most of a moved pull's time.

### Remaining limits

- After a merge or pull has updated HEAD, its stat can still reach a bound: a file whose line diff passes 2,000 differing lines, or more than 2,000 changed paths in the summary. The command then ends with the named bound, exit 128, the update done and no merge state left; Git prints the stat (measured at 4,531 paths).
- A repository holds at most 256 packs, and each den fetch adds one.
- Three directory-and-file shapes in a transition's way still differ from Git: an untracked directory where the target has a file (Git: `Updating the following directories would lose untracked files in them`; den: `fatal: cannot overwrite directory`), an untracked file where the target has a directory (Git names the file as untracked and in the way; den: `fatal: not_found`), and an ignored directory where the target has a file (Git replaces it; den: `fatal: cannot overwrite directory`).
- A moved pull still walks the whole history of both tips to find the merge base, and the pull's own ancestry checks walk a tip's whole history when the answer is no.
- Progress output for pull, the issue's second request, is not in this change.
- `den diff` keeps its own refusal of any root attribute file.
- Messages built at run time inside region blocks elsewhere (`tree transition unreadable path …`) keep the hazard decision 3 describes.

## Done-when

- [x] The reported failure reproduced with the den it was reported with, and its bound and phase named
- [x] Formatting; pinned native and release builds
- [x] Scan rows, 56 per tier, equal to Git within the read and memory budgets; red first, 41 of 56
- [x] Attribute rows, 85 per tier
- [x] Named-bound rows, 10 per tier, and the census
- [x] Scale rows equal to Git and under their bounds
- [x] Worktree, index, ignore, commit, diff units, refs, merge, replay, stash, history, objects, pack, wire, HTTP, housekeeping, porcelain, everyday and submodule gates on both tiers, in one record
- [x] A one-file, one-hunk plant, red by name
- [x] README updated
- [ ] Progress output for pull (a separate change)
