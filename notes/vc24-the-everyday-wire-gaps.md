# vc24 — the everyday wire gaps

Six gaps a person meets in den's first days on the wire, each held to the pinned Git byte for byte: a push to a branch the remote does not have yet (den#71), a clone with no directory (den#72), `ls-remote` (den#68), `rev-parse` (den#69), a fetch of a configured remote with explicit refspecs (den#70), and clone memory against history length (den#63). Two of them stopped a session at a PAX console.

Footprint: module

## Forbidden

Clean room: git's documentation and black-box runs of the pinned Git and a field Git only. No Git, libgit2, JGit or other implementation source was read. The rules a row holds to (git-clone(1)'s "humanish" name, git-push(1)'s placement of a short destination, the fetch report's form after a rejection, which tags a fetch follows) were measured black-box and are written below in den's own words. Organisation code read: den, burrow's `tools/measure-den` fixture generator (den#63's fixture, used by value), the wolf book's chapters on lists and regions, wolf-std's `list`. Submodule code (gitlinks, `.gitmodules`) was not touched; clone's operand parsing changed only where the destination is set for one operand, and the option loop keeps its shape. No toolchain pin, CI file or shared tool changed. Every fixture is generated; none is a person's repository.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, 46 GiB | every Linux build and row, in the pinned oracle container on a six-CPU block holding both of its locks (12 GiB cap), or a two-CPU light slot (6 GiB) for the memory probes, each under `prlimit --as` |
| Apple silicon laptop, macOS arm64 | editing, commits, native builds behind the build lock, every family's rows against the field Git, the macOS record |
| Apple silicon laptop (a second one) | native builds while the first laptop's lock was held; the binary was copied back and run on the first |

## Inputs verified

- **Base:** den trunk `474a926`, branch `vc24`.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58 and wolf-std `d4a4d4c`, unchanged; archives checked by digest by `tools/fetch-toolchain`.
- **Oracle:** Git 2.56.0, executable `c4848492…`, checked by digest by every row script; OpenSSL 3.0.13 from the oracle image for the TLS fixture.
- **Field Git:** Homebrew's Git 2.56.0 on macOS, for the macOS rows (`--field`).
- **Pages:** git-push(1), git-clone(1), git-ls-remote(1), git-rev-parse(1), git-fetch(1), gitrevisions(7), gitglossary(7), gitprotocol-v2(5) (`ls-refs`), git-config(1) (`advice.pushUnqualifiedRefname`, `lsrefs.unborn`, `remote.<name>.fetch`), git(1) (`GIT_CEILING_DIRECTORIES`). `docs/SOURCES.md` (vc24) lists them by section.

## Prediction

`tests/vc24-prediction.txt`, committed first (`b3d4432`), with every measurement taken before any change.

- **P1, den#71:** held, with one finding. On trunk, `den push origin trunk` and `-u` into an empty bare remote already created the branch on every transport; the rows confirm it (`push-infer-heads-*`, `push-upstream-*` pass on trunk). The issue's `push destination requires full refname` was den's answer for a source that names no local branch or tag. Every refusal and remote-match row was red on trunk and is exact now. Below, "den#71's console session" says what reproduces the issue's text exactly.
- **P2, den#72:** held. The humanish rule as predicted, from 35 name rows over every URL form plus full clones on five transports. Not predicted: Git looks for a local source as `PATH`, `PATH/.git` and `PATH.git`, and den did not (`1ef5a48`).
- **P3, den#68:** held; 144 rows on four transports on macOS, five on Linux.
- **P4, den#69:** held, with two details not predicted. Git prints a short name that matches two refs as an error and no output under `--abbrev-ref`. Git prints the argument before a missing path's error, but not before an upstream error. Rows outside a repository need `GIT_CEILING_DIRECTORIES`, which den now honours (`61b2d2d`), since every row runs inside a checkout.
- **P5, den#70:** held, with three details measured rather than predicted: a report holding a rejection is printed with its summary column unpadded; a negative refspec still downloads the excluded ref's objects, so a tag pointing into them is followed; a short destination is always under `refs/heads/`.
- **P6, den#63:** held. The quadratic at the issue's commit reproduced (358,780 KiB at 30 commits, 3,466,008 KiB at 120) and was gone at trunk; what remained was linear at about 3 KiB an object (`--bare`) and 6 KiB with a checkout, from the pack index. After the fix the 80,000-object clone peaks at 101,920 KiB with a checkout (bound 185,536 KiB; trunk 488,344) and 97,360 KiB bare (bound 145,536 KiB; trunk 243,380), each under `prlimit --as` at its bound plus 128 MiB. Below, "den#63".
- **P7, PAX:** drafted below for a px lane; no PAX session was run here.
- **P8, the refusals that remain:** as predicted, plus a new one (R-vc24-6).
- **P9, the gate:** as predicted; the records are in the PR body.
- **P10, the checkout's reader (a second change):** the cap held and the estimate did not. After the reader alone den's clone CPU was 8.3 times Git's on macOS, not about 5: the per-file syncs' system time, which the estimate left out, was most of the difference. After P11's change too, 6.5 times. Below, "The checkout's cost".
- **P11, the checkout's syncs:** held. The pinned Git's pelt clone makes 3 sync calls, all on the received pack; den's fell from 19,390 to 20, none on the worktree. On a disk under strace den's clone fell from 294.4 s to 11.0 s; it was not measured in a tmpfs here.
- **P12, den#73's bounds and their costs:** held, with two findings not predicted. Every path completes at 50,000 objects with Git's result; serving a clone and den's own clone through den's server cost 8.2 and 9.6 times Git's CPU on macOS, under the 30-times cap and under 10; each den process stays under 64 MiB plus 1 KiB an object. The prediction's order held, and the reader's cache was a lever it did not name: a read along a delta chain rebuilt and hashed every base. The findings: receive walked each tip's history twice, and the transfer walks refused i3's history with fsck's identity checks (den#75 since removed them from the transfer walks). Below, "The bounds at scale".
- **P13, the rows:** as predicted, and red first by name at PR 2's head (8 of 10 on macOS; `scale-clone-git-server` is the regression row).

## Evidence index

### Commits

- `b3d4432` the prediction.
- `8267721` the rows (`tools/wire-gaps-test.py`: push, clone, ls-remote, fetch, memory), red; `791bbbf` two harness corrections (the name rows' ssh fails for both tools; a non-repository is described by its files); `1caec0b` rows for a missing source.
- `c9c05de` den#71: sources resolved by gitrevisions(7)'s order before connecting, short destinations placed against the advertisement, Git's refusals.
- `58b367c` den#72: the humanish name, an existing empty destination, Git's occupied-destination and empty-repository messages, named operand refusals; `1ef5a48` a local source found as `PATH/.git`, `PATH` or `PATH.git`, and `lsrefs.unborn` honoured.
- `83de961` the rev-parse rows (`tools/rev-parse-test.py`), red; `61b2d2d` `GIT_CEILING_DIRECTORIES`; `f1a975f` `B@{upstream}` in the revision grammar; `d6d8e41` `rev-parse` (den#69); `cd1c280` the oracle's `rev-parse` case held to parity and `rev-parse-parseopt` as the strict not-yet witness (R-vc24-4).
- `b33ff1c` the ls-remote rows' outside directory; `90d46a9` `ls-remote` (den#68).
- `b0d40a8` the fetch selector takes exact names; `be65308` an unpadded report after a rejection; `c62eb64` `fetch REMOTE REFSPEC...` (den#70).
- `b4fe7f1`, `d151ea8`, `212783a` den#63: a lean idx parse, tree walks in regions, the closure walk by rank.
- `a5086c5`, `7d52d98` the rows in `tools/check-http` and `tools/check-revision`.
- `0bcba26`, `3808c67`, `c960529`, `235f235`, `8b4d328`, `5023de3` README, SOURCES, MAP, CHANGELOG, MAP and README for den#63.
- This note.

### den#71's console session

The refusal is raised in `push_specs` before any connection, so no server advertisement can cause it; the explicit form `trunk:refs/heads/trunk` reads the same local ref through the same lookup, so in one repository state both forms succeed or both fail (both run on Linux's release tier, file:// and ssh, from `den init` and `den switch -c trunk`: both succeed). The issue's text is reproduced exactly by `push-empty-remote-no-unborn-*`: a clone of an empty repository from a server that does not advertise `unborn` in `ls-refs` names the local branch from `init.defaultBranch`, so a commit lands on `main`, and `den push origin trunk` printed `push destination requires full refname` where Git prints `error: src refspec trunk does not match any`. With the source resolved first, den now prints Git's lines and exit 1. A clone from a server that advertises `unborn` (`push-empty-remote-unborn-*`) names the branch from the remote's HEAD, as Git does, and the push succeeds. Not measured here: whether the hosted service in that session advertised `unborn`.

A related difference outside this lane: with no `init.defaultBranch` configured, `den init` and a clone of an empty repository with no `unborn` name the branch `main` silently, where Git names it `master` and prints its initial-branch hint (R-vc24-6).

### den#63

The issue's figures are commits (30 to 300), not thousands. Its fixture (burrow's generator) and a long-history one (one small file rewritten a commit, four objects a commit) were measured with each den run's peak RSS read by `wait4` in a small launching process (floor about 7 to 8 MiB), file://, release, in the oracle container (12 GiB), each run under `prlimit --as`:

| fixture | den at the issue's ef0bb0c | trunk 474a926 | this head |
|---|---|---|---|
| issue, 30 commits, `--bare` | 358,780 KiB | below the floor | |
| issue, 60 commits, `--bare` | 981,496 KiB | below the floor | |
| issue, 120 commits, `--bare` | 3,466,008 KiB | below the floor | |
| issue, 300 commits and 40 incompressible 256 KiB files, clone / `--bare` | | 26,892 / 21,944 KiB | 21,920 / 22,032 KiB |
| long, 1,000 commits (4,000 objects), `--bare` | 1,085,072 KiB | 15,472 KiB | |
| long, 2,000 commits (8,000 objects), `--bare` | 4,137,620 KiB | | |
| long, 20,000 commits (80,000 objects), clone / `--bare` | | 488,344 / 243,380 KiB | 101,920 / 97,360 KiB |

At ef0bb0c the whole-pack decoder inflated each entry from a copy of the rest of the pack (about entries times pack over two), quadratic in history; vc23's streamed indexer (den#61) replaced it. At trunk an RSS timeline of the 80,000-object clone (VmRSS and open files every 5 ms) split the rest: receive 4.5 MiB; the indexer's tables +32 MiB; install +18 MiB; the closure's reader parsing the idx +56 MiB; the closure walk +78 MiB (`--bare` ends there); about a dozen further idx parses kept during checkout setup, about 20 MiB each, +245 MiB; each checked-out file parsing the idx again, reclaimed. The idx parse built a hex string, an id and a slice for every entry in the caller's region, and its merge sort copied its order list on every pass; tree walks opened readers whose parses outlived them; the closure queue kept every link's name.

The fix (`b4fe7f1`, `d151ea8`, `212783a`): the idx parse reserves its lists to the count, decodes each name in its own region and merges without a copy a pass; `tree_id` and `flatten_tree` walk in a region and keep only their result; the closure walk queues received objects by rank with an int for the type it expects, and does each step in a region. The rows (`memory-long-20000`, `-bare`, `memory-issue-300-40`, `-bare`) hold the bound of P6 d, 64 MiB plus 1.5 KiB an object with a checkout (1 KiB bare), under `prlimit --as` at the bound plus 128 MiB, and compare each clone with Git's and its `fsck --full`. CPU for the 80,000-object clone fell from 21.1 s to 15.6 s with a checkout; Git takes 0.5 s. The checkout still parsed the idx once for each object it writes (reclaimed), so its CPU grew with files times objects; the second change, below, threads one reader through it.

### The rules, as measured

- **The humanish name (den#72).** Take the URL without its scheme and its authority's user information (scp-like `user@` too); drop trailing whitespace and slashes, then one trailing `/.git`, then slashes again; when no `/` is left, drop a `:port` of digits, possibly none; take what follows the last `/` or `:`; drop one `.git`; collapse runs of whitespace and control characters into one space and trim. Nothing left refuses (`No directory name could be guessed.`). `--bare` appends `.git`. A local source is checked before the name is guessed.
- **A short push destination (den#71).** The source resolves first (the full name itself, `refs/X`, `refs/tags/X`, `refs/heads/X`, `refs/remotes/X`, `refs/remotes/X/HEAD`, two of which refuse; else any revision; else `does not match any`). With no colon the destination is the source's ref, or the source as typed for any other revision. A destination outside `refs/` is the one remote ref it names by the same spellings; two refuse; none takes the source's `refs/heads/` or `refs/tags/` (an attached HEAD lends its branch); else Git's refusal, whose hint names the source's type (commit: "create a new branch", `refs/heads/`; tag: "create a new tag"; tree or blob: "tag a new tree" or "blob", `refs/tags/`), omitted under `advice.pushUnqualifiedRefname=false`.
- **Explicit fetch refspecs (den#70).** A source is a full name, a short one by the same spellings (so a name both a tag and a branch is the tag), or a one-star glob over the remote's refs in the server's order; a negative refspec excludes glob matches from the destinations but not from the download; `tag NAME` is `refs/tags/NAME:refs/tags/NAME`; a short destination is under `refs/heads/`. Every explicit entry goes to FETCH_HEAD for merge; tags pointing into the download follow only when some refspec stores a ref; a source the remote's configured wildcard maps also updates that remote-tracking ref, listed after the tags. A report holding a rejection pads no summary.
- **`ls-remote` (den#68).** The server's order; a peeled `^{}` line after each annotated tag (fully peeled) unless `--refs`; HEAD unless `--refs`, `--heads` or `--tags`; patterns are globs matched against the whole name or any tail after a `/`, with `*` crossing `/`, the peeled line by its own name; `From URL` on stderr only when the default remote is used.

### R-list, as applied

- **R-vc24-1 = (A):** clone's operand errors are named refusals, `den: wire: Unsupported(clone requires a repository)` and `Unsupported(clone takes a repository and at most one directory)`, exit 2. Option (B), Git's `fatal:` line and usage block (exit 129), would print an option list den does not take.
- **R-vc24-2 = (A):** `ls-remote --get-url`, `--sort` and `-o`/`--server-option` refuse by name (`Unsupported(ls-remote option …)`); `-h` alone, which is Git's help, refuses by name too. `--get-url` waits for `url.<base>.insteadOf`, which is another lane's.
- **R-vc24-3 = (A):** `rev-parse` takes the forms scripts use (P4) and a few neighbours; any other option is `den: not yet implemented: rev-parse (M3, vc10)`.
- **R-vc24-4 = (A):** the oracle's `rev-parse` case is a parity row (`require_parity`); a new `rev-parse-parseopt` case keeps `tools/oracle --filter rev-parse --strict` red, so `tools/gate`, `tools/gate-record` and `ci/tiers-test.py` are unchanged.
- **R-vc24-5 = (A):** `fetch --prune` with explicit refspecs refuses by name.
- **R-vc24-6 (accepted for a follow-up lane after vc25; not applied here):** with no `init.defaultBranch`, Git names a new repository's branch `master` and prints its initial-branch hint; `den init`, and a clone of an empty repository whose server does not advertise `unborn`, name it `main` silently. Options: (A) a follow-up lane holds `init` and the empty clone to Git without the pinned configuration (recommended: it is the PAX console's case, where no global configuration exists); (B) keep `main` as a reviewed difference.

- **R-vc24-7 (asked by the second change's prediction; ruled to match the pinned Git):** worktree files are not synced, as the pinned Git syncs none.

### The checkout's cost (den#63, a second change)

From px108: `den clone https://github.com/wolffe-lang/pelt.git` at a PAX console took 70.2 s of user and 44.9 s of system time where Git takes 1.37 s; on Linux the same clone took 103 s into a tmpfs and 287 to 295 s on a disk. Predicted in P10 and P11 (`tests/vc24-prediction.txt`) before each change was built. Two terms, each measured before its change:

1. **CPU, the index parsed twice a file.** The checkout reads each blob twice, to check every blob before writing any and then to write it, and each read went through `read_object`, which parses the pack index (356 KB for pelt: its SHA-1, its offset sort, its reads, its names). A macOS `sample` of the clone put most of its CPU there.
2. **Wall time, two syncs a file.** The checkout synced each file and then its directory: 19,390 syncs in Linux's census of the clone below, and 86 percent of the checkout's wall time in a macOS sample once the first term was gone. The pinned Git's clone of the same repository makes three sync calls, on `objects/pack`'s temporary idx, rev and pack, at the end of the receive and none during the checkout; git-config(1)'s `core.fsync` names no component for worktree files.

The change: `object.reader_batch` opens one reader for a checkout, a restore or a merge abort, and `install` reads through it (`c559c10`); a read through an opened reader re-checks its pack's size, header and trailer binding and rescans the index's offsets only when the size moved (`5749abf`); a reader whose packs cannot open up front serves loose objects and fails a packed read with a single read's error (`e69f732`). `install` syncs neither its file nor its directory (`0f25864`); the pack, refs, index and configuration keep their syncs.

The rows, `tools/check-http`'s `release-clone-cost` step: `clone-cost-pelt` clones pelt's trunk at `b80d657` (12,038 objects, 9,685 files; a bundle pinned by its digest, repacked by the pinned Git on one thread, served by the pinned git daemon), the pinned Git then den, three times in turn, and holds den's least CPU (user plus system, from `wait4`, children included) to at most ten times Git's, with both clones checked out and equal; `clone-syncs-pelt` (Linux) counts each client's sync calls through a preloaded census library (`tools/sync-census.c`) by what they sync, and holds den's worktree syncs to Git's (none) and its total to at most 24 more than Git's. The batch reader's re-check has its own rows in `tools/pack-test.py` (`session-*`): a pack replaced under an opened reader, by the same bytes, shorter, longer, a changed header, count, trailer or entry, answers as a fresh read of it does.

pelt's clone, release, the least CPU and the least wall time of three runs each:

| | den CPU | Git CPU | ratio | den wall | Git wall |
|---|---|---|---|---|---|
| macOS arm64, field Git, before (`304757b`) | 115.62 s | 0.92 s | 125.7 | 186.1 s | 0.8 s |
| macOS, after the reader only (outside the pinned environment) | 8.12 s | 0.98 s | 8.3 | 79.8 s | 0.9 s |
| macOS, after both changes | 6.00 s | 0.93 s | 6.5 | 6.1 s | 0.8 s |

Linux's system call census of the same clone (strace `-f -c`, a light slot, on a disk; one run each, so its times include strace's):

| | calls | pread64 | statx | openat | brk | getdents64 | fsync | wall under strace |
|---|---|---|---|---|---|---|---|---|
| the pinned Git | 70,504 | 5,916 | 10,718 (newfstatat) | 20,262 | 85 | 20 | 3 | 1.5 s |
| den before (`304757b`) | 863,457 | 255,369 | 213,881 | 116,939 | 38,639 | 38,762 | 19,390 | 294.4 s |
| den after | 457,091 | 139,157 | 155,776 | 68,517 | 418 | 24 | 20 | 11.0 s |

The Linux timed rows' figures, before and after, are the gauntlet's and are in the PR body.

**The next term** is den's own per-object work: each blob is inflated and hashed in wolf when the received pack is indexed, again when the checkout checks it and again when it writes it (each through its delta chain), and the written file is read back and hashed once more, where Git inflates each object once. On macOS a bare clone (the receive alone, which neither change touches) took 2.4 s of CPU against Git's 0.32 s, and the sample of the whole clone is led by SHA-1, inflate and delta application. In system calls, den's checkout still makes about 16 `statx`, 14 `pread64` and 7 `openat` a file where Git makes about 1, 0.6 and 2: the pack is opened and re-checked for each of a blob's two reads, each ancestor directory is checked before a file is written, and the written file is read back.

### The bounds at scale (den#73, a third change)

den#73: serving a clone, den's clone from den's server, fetch, push and receive each stopped at a fixed count of 10,000 objects, and each count sat in front of work that grew with the square of the objects (P12, `tests/vc24-prediction.txt`, measured before any change: refusals after about 244 s of CPU each at 50,000 objects). Predicted and committed first (`ef88130`); the rows (`e616060`) red first by name at PR 2's head.

What changed, in the order P12 gave:

1. **The closure walk** (`walk_plan`) reads through one batch reader and keeps its queued, typed and omitted names in a hashed set (`pack.NameSet`), each object as its name's 40 bytes, a type code and a size, each step in its own region. Include-tag walks the wants once and then only the tags it adds; it walked the whole closure twice before the pack's own walk.
2. **The reader's cache** (`pack.Cache`): a read along a delta chain rebuilt every base from the pack and hashed each one, so a tree 25 deltas deep cost 25 inflates and 25 SHA-1s for every read of it. Rebuilt bases are kept by pack and offset (256 slots of at most 16 KiB) and only the object returned is hashed.
3. **The writer** (`pack.Writer`) writes the pack to a temporary one object at a time, weighing the last ten objects of its type below fifty links: the shortest raw delta is deflated and kept when smaller than the whole object, a base stops being weighed once it cannot beat the best so far, and the trailer is summed by reading the file back. Serving sends the file in side-band windows; push streams it to a stream peer.
4. **Receive** finds the pack's end as it arrives (`pack.scan_more`, each entry inflated once), indexes it with the streamed indexer and keeps it as a pack at 100 objects or more, as Git's receive-pack does; a thin pack falls back to the whole-stream decoder.
5. **The counts**: the protocol's wants, haves, refs and push commands, the received closure's bound on objects already present, the decoder's 10,000 and every walk's are gone; a request stays bounded by its bytes.
6. **The codec**, each with the same bytes as before (rows against the first forms and against zlib): deflate keeps its 64 Ki-entry match tables across a writer's objects instead of building them for each; the Huffman join takes two queues instead of scanning every node; inflate reads a byte's worth of bits at once and decodes fixed blocks without building their tables; the delta encoder indexes its base by open addressing and rolls its fingerprint.

The rows, `tools/wire-gaps-test.py` family `scale` (both tiers; in `tools/check-http`'s wire-gap steps) and two timed rows in family `cost` (the `release-clone-cost` step), each held to the pinned Git's result (refs, reachable objects and their digest), each den process launched from a small parent and its peak RSS held under P12's bound, 64 MiB plus 1 KiB an object (on Linux also under `prlimit --as` at the bound plus 128 MiB):

- `scale-serve-clone`: the pinned Git clones 50,000 objects (12,500 commits, 25,000 trees, 12,500 blobs, from fast-import) through den upload-pack;
- `scale-clone-den-server` and `scale-clone-git-server`: den clones them through den's and Git's upload-pack;
- `scale-fetch-history`: den fetches 46,000 new objects into a 4,000-object repository; `scale-fetch-wide`: one commit over a 15,000-blob flat tree den already holds;
- `scale-push`: den pushes the 50,000 into an empty repository through Git's receive-pack; `scale-receive`: Git pushes them into den receive-pack;
- `scale-clone-i3`, `scale-push-i3`: i3's public history (41,341 objects; a bundle of `next` at `8a97b0f`, pinned by its sha256, cloned offline) cloned through den upload-pack and pushed into an empty repository;
- `scale-serve-cost` and `scale-den-cost` (release): the pinned Git's clone through den upload-pack and den's clone through den upload-pack, each at most 30 times the pinned Git's clone through Git's upload-pack, CPU of the whole process tree, three runs in turn, the least.

At 50,000 objects on macOS (release, the field Git; each figure CPU of the row's process tree from `wait4`, and the peak RSS of its largest process, the bound 115,536 KiB; i3's 106,877 KiB):

| row | before (PR 2's head) | after | peak RSS after |
|---|---|---|---|
| scale-serve-clone | refused after 243.5 s | 6.50 s | 76,272 KiB |
| scale-clone-den-server | refused after 244.0 s | 7.50 s | 76,176 KiB |
| scale-clone-git-server | 7.9 s | 1.81 s | 58,224 KiB |
| scale-fetch-history | refused after 243.6 s | 2.52 s | 79,440 KiB |
| scale-fetch-wide | refused after 1.0 s | 1.09 s | 31,920 KiB |
| scale-push | refused after 245.8 s | 6.30 s | 65,344 KiB |
| scale-receive | refused at once | 1.97 s | 73,888 KiB |
| scale-clone-i3 | refused (`fsck identity diagnostics`) after 128.9 s | 60.17 s | 100,832 KiB |
| scale-push-i3 | refused (the same) after 131.4 s | 53.94 s | 93,456 KiB |

The cost rows, the least of three runs each in turn: serving 6.43 s against the field Git's 0.78 s, 8.2 times; den's own clone through den's server 7.50 s, 9.6 times; both under 10, so the 30-times cap holds with room. pelt's clone (PR 2's row) fell from 6.4 to 4.7 times with the codec changes. Linux's figures are the gauntlet's, in the PR body.

Each process's peak is the largest of its tree's (for the serving and receiving rows, Git's processes too); the launcher's own floor, `den --version` from the same parent, is about 2,000 KiB. On Linux every den process also runs under `prlimit --as`.

**Not predicted, found on the way.** Git's `receive-pack` keeps a push's pack, and so does den now; but den's receive checked each pushed tip's closure twice, once in the received closure (`closure_received`) and once more by walking all of history into a list of names, which was most of its memory (119,328 KiB against the 115,536 KiB bound in the first take, red by name); the second walk now runs only for a thin pack, whose decode checks nothing (`42f66c2`). i3's history refused at PR 2's head with `fsck identity diagnostics`: the transfer walks checked identities as fsck's did, which Git's transfers leave to `transfer.fsckObjects`, off by default (Git's `fsck --full` reports nothing in i3). den#75, merged first, took identity checks out of the shared link parser, so these walks keep `packcmd.links` and i3 passes on its trunk.

**Where den's CPU goes now** (macOS `sample` of the release processes, top-of-stack samples by class; blocking reads left out):

| class | serving 50,000 (den upload-pack) | den's clone of them (client) | serving i3 |
|---|---|---|---|
| reading objects: opens and preads, the cache, unpack | 35.0% | 49.4% | 11.9% |
| inflate | 3.7% | 15.9% | 17.9% |
| delta application | 1.5% | 4.5% | 14.2% |
| SHA-1 | 1.8% | 8.6% | 4.1% |
| delta search | 19.5% | — | 31.7% |
| deflate | 19.8% | 2.3% | 13.4% |
| writing the pack (and its trailer read back) | 5.0% | — | 3.8% |
| indexing the received pack | — | 4.8% | — |
| memory moves and the rest | 13.7% | 14.6% | 2.9% |

At 50,000 small objects the largest single term is system calls: each read opens the object's loose path (absent) and then its pack, and re-checks the pack's bounds, so a serve opens about 200,000 files. On i3's history, with 5,569 blobs over 16 KiB (beyond the cache) and chains averaging 6.8 deltas, rebuilding blobs (inflate and delta application) and weighing ten bases for each are most of it.

**The next step: copying stored entries.** Git serves a clone by copying each stored entry, its delta included, whose base is also sent; den rebuilds every object, deflates it and searches its window again. Copying the entries would remove the delta search, the deflate and the write side's reads (about half of the reading, inflate, delta application and SHA-1 terms), leaving the walk's reads and the copying: predicted about 60 percent of serving 50,000 objects (6.5 s to about 2.6 s, some 3 times Git's) and about 70 percent of serving i3 (54 s to about 16 s, some 10 times Git's 1.6 s), and the pack would be Git's size (den's i3 pack is 34.7 MB to Git's 15.9 MB, as its window pairs objects by size, not by path). Reading the pack index by offset, and probing packs before loose paths in a batch, would take the opens out of the 50,000-object figures.

### On PAX: a px lane's items (drafted, not run)

1. Pin den at this lane's merge in `user/den.pin` and rebuild `/bin/den` with `tools/mkden`, twice, refusing two digests, as the pin's earlier sweeps did.
2. A loopback fixture inside the image: `den daemon --enable-receive-pack` over an export base holding `fix.git` (a few commits, an annotated tag) and `empty.git` (empty, bare, HEAD naming `trunk`), started on an image whose kernel brings its network stack up.
3. Typed at the console, each line's output held to the same keys typed on Linux against the same fixture and den build:
   - `den clone git://127.0.0.1:9418/fix.git` (no directory: `Cloning into 'fix'...`), then, inside `fix`, `den rev-parse --abbrev-ref HEAD` and `den ls-remote origin`;
   - `den clone git://127.0.0.1:9418/empty.git` (Git's empty-repository warning), a commit, `den push origin trunk` (`* [new branch] trunk -> trunk`), `den push -u origin trunk:other`, `den fetch origin trunk:refs/scratch/t`, `den ls-remote --heads origin`;
   - the refusals: `den push origin nosuch` and `den clone git://127.0.0.1:9418/fix.git fix` into the occupied `fix`.
4. Follow-ons for the networked stick: the same clone with no directory over https and over ssh through burrow, against a public repository.

### Remaining limits

- Push to an unconfigured local path stays `missing remote PATH`; a deletion whose short destination names no remote ref refuses as Git does (`unable to delete`), and any other unmatched deletion keeps its old named refusal.
- Explicit fetch refspecs need the remote's configured refspec to be the default branch wildcard (or none); another configured mapping refuses by name. `--prune` with explicit refspecs refuses by name (R-vc24-5). Tag following walks history through the shared closure, which has no count bound since den#73.
- `ls-remote --get-url`, `--sort` and `-o` refuse by name (R-vc24-2).
- `rev-parse` options other than P4's are not yet implemented (R-vc24-3); `GIT_DIR` and `GIT_WORK_TREE` overrides are not row-tested.
- Clone's operand errors are named refusals, not Git's usage text (R-vc24-1).
- `init` and an empty clone with no `init.defaultBranch` (R-vc24-6).
- A clone's CPU after the second change is about six times Git's on macOS, in den's own inflate and SHA-1 (above, "the next term"); 4.7 times after den#73's codec changes.
- The bounds that remain after den#73, each with its reason:
  - `pack.encode`, the in-memory writer behind `pack-objects` and `repack`: 10,000 objects, 16 MiB a body and 128 MiB in all. These local commands hold every body; moving them to the streaming writer is a follow-on, and no clone, fetch, push or serve uses them now.
  - A thin pushed pack (one whose deltas name bases outside it, as Git's push sends when the receiver holds the bases) falls back to the whole-stream decoder, which holds the stream and its bodies: 128 MiB of each, 16 MiB a body and 64 links (its count bound is gone). The streamed indexer does not yet resolve outside bases. A push into an empty repository, as in the rows, is never thin.
  - receive-pack holds the pushed pack in memory, to 2 GiB, before feeding the indexer in 1 MiB windows: the pack follows the commands on one stream and is read whole. Feeding the indexer as the pack arrives is the follow-on.
  - Push over smart HTTP sends its request body whole, so the pack is held in memory there, to the HTTP client's 140,000,000-byte request cap (over every other transport it streams from the temporary).
  - A pack holds at most 400,000 objects: the reader parses an index whole, from a file of at most 16 MiB, and keeps a string a name, and the streamed indexer keeps the reader's limit so that every index it writes reads back (vc23). A larger pack refuses by name (`pack index object count limit`); the rows' 50,000 objects are an eighth of it. Reading the index by offset, as the pack is read, would lift both.
  - A local path clone copies at most 100,000 files of the source's object directory (a file count, not an object count: a pack is three files).
  - One object is at most 512 MiB; the delta encoder takes bodies up to 16 MiB and stores larger ones whole; the reader's cache keeps objects of at most 16 KiB.
  - A fetch request is read whole to 2 MiB (about 40,000 `have` lines a round), as before; every count inside it is gone.
  - Outside the wire: `fsck`'s 10,000 roots and objects, the commit-graph's 10,000 objects, the object inventory's 10,000 loose objects and the walker's 100,000 nodes stay as they were; den#73 named the wire.
- den hardens a clone's refs, index and configuration, which Git's default leaves to the system: pelt's clone makes 20 sync calls against Git's 3, by `clone-syncs-pelt`'s classes: 9 on the repository's own files (its configuration, reflogs and directory), 6 on refs, 4 on the pack and its directory, 1 on the index.

## Done-when

- [x] Prediction first (`b3d4432`).
- [x] Rows red first on trunk's sources, then exact: push (den#71) on five transports into empty bare repositories, `-u`, the remote-match rows and every refusal; clone with no directory (den#72) for every URL form, `--bare`, existing destinations, the empty-repository warning and the named operand refusals; `ls-remote` (den#68); `rev-parse` (den#69); `fetch REMOTE REFSPEC...` (den#70).
- [x] den#63: the memory rows under a hard cap at the predicted bound.
- [x] PAX: the px lane's items drafted above.
- [ ] The final gauntlet, the plant and the macOS record at the head: their records and every END line are in the PR body.
- [x] The checkout's reader and syncs (den#63, second change): predicted (P10, P11), the rows red first at `304757b`, then green.
- [x] den#73's bounds (third change): predicted (P12, P13), the rows red first at PR 2's head, then green on both tiers; the remaining bounds listed with their reasons; the CPU broken down and the next step named with its predicted gain.
