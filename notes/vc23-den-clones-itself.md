# vc23 — den clones itself

den clones and fetches a pack of any size over every transport, and clones its own public repository (a pack over 300 MB) over https, compared with Git's clone (den#61). The fetch response streams to a temporary under `objects/pack` and is indexed there, as `git index-pack` does; memory follows the largest object, not the pack. The live push row keeps the private fixture's URL off every child's argv (R-vc22b-1 (a)), and the Homebrew leg's intermittent commit rows have a named cause and a fix (den#66).

Footprint: module

## Forbidden

Clean room: git's documentation and the pinned Git, a field Git and the pinned OpenSSL run as black boxes. No Git, libgit2, JGit or other implementation source was read. Organisation code read: den itself, the wolf book's chapters on lists and regions, and wolf-std's `fs`. The private fixture's token and URL lived only in the environment of the process that used them, reached the container on its stdin, and never reached a file, a log or an argv; every take ended with a secrets scan of the take's files, the lane directory and the checkout (0 hits each time). No host name appears here; the hardware table stands in.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, 46 GiB | every build and row, in the pinned oracle container on a six-CPU block holding both of its locks (12 GiB cap), or a two-CPU light slot (6 GiB) for the memory probe |
| Apple silicon laptop, macOS arm64 | editing, commits, and den#66's field-Git witness (no den build) |

## Inputs verified

- **Base:** den trunk `ac2332b`, branch `vc23`.
- **Toolchain:** wolf 0.2.36 and lupin 0.1.58 and wolf-std `d4a4d4c`, unchanged; the archives' digests checked by `tools/fetch-toolchain`.
- **Oracle:** Git 2.56.0, executable `c4848492…`; OpenSSL 3.0.13 from the oracle image, checked by digest before each TLS fixture and the live advertisement read.
- **Field Git:** Homebrew's Git 2.56.0 on the Mac, for den#66 only.

## Prediction

`tests/vc23-prediction.txt`, committed first (`11ea75e`), with the measurements taken before any change.

- **Before:** trunk den cloning a 110,135,503-byte pack under its caps took 32.05 s and 6,623,028 KiB (git 2.17 s, 112,268 KiB): about 60 times the pack. A wolf probe showed why the code shape mattered: a `List` slice is a copy, also as a call argument (two hundred slices of a 64 MiB list ran a 6 GiB container out of memory), and only a region frees.
- **P1, what held memory:** held as a description; the streamed path no longer has any of those components.
- **P2, the bound:** held. The large fixture (largest object 48 MiB) peaked at 274,040 to 287,144 KiB in release, inside the 400 MiB bound, and cloned under `prlimit --as` at that bound. den's own repository peaked at 374,852 KiB, inside its 652 MiB bound but above the predicted 230 MiB: the checkout's reader holds four copies of each blob and the 98 MiB whole blob costs about 2.1 times itself while indexing, so the estimate of the actual peak was low; the bound held.
- **P3, the time:** den cloned its own repository in 206.2 s release (39.2 s of CPU), against Git's 131.1 s (4.1 s) on the same link, 1.57 times; predicted 165 s and 1.3 times. The CPU was a third higher than predicted, and den's phases run one after another.
- **P4, the rows:** held; every row was red on trunk by name and is green (below). Not predicted: Git writes a reverse index beside every pack it indexes, and den now keeps the pack it receives, so the `--no-local` clone rows compared the two and found it missing (below).
- **P5, the URL off argv:** held. Git passes a configured remote's URL to `git remote-https` on argv (measured with `GIT_TRACE`), so the row reads the server's advertisement itself (R-vc23-3).
- **P6, den#66:** held in its cause, not in where the fix went. `maintenance.autoDetach=false` turns the child into `--no-detach`, but the pinned environment's global config is bound into reviewed rows (`configured-lease-delete-match` fingerprints it), so a change there voids their reviews. The fix went into the oracle's own Git runs instead (`-c maintenance.autoDetach=false`), and the oracle refuses an invocation whose maintenance detaches.
- **P7, the rulings:** implemented as recommended (below).

## Evidence index

### Commits

- `11ea75e` the prediction.
- `5cfead7`, `845ae34`, `b9909a0`, `bfa675c` the red rows: the live argv watcher, the live self-clone row, `tools/large-pack-test.py`, and its step in `tools/check-http`. `3bfedf5` clones with Git before den in those rows (the TLS fixture is one byte stream, and a client that stops early leaves the rest to the next one).
- `63df02a` the fixture URL off every child's argv.
- `c7d0eb5`, `1172e5b` den#66: the oracle's refusal of a detached maintenance child, red, then `maintenance.autoDetach=false` on the oracle's own Git runs.
- `aa2343a` the large-pack harness: the fixture and the TLS fixture in their own processes, the memory row first, no fixture bitmap, the fetch seed following no remote HEAD.
- `aec0f0b` sized inflate; `d96f51c` table CRC-32 and reserved delta application; `4b15d91` SHA-1 over a prefix.
- `4827504` the ingest units, then `1cb04a1` the streamed indexer (`src/pack/ingest.lu`).
- `535c778` the reader's object cap and read-only sessions; `262bdc4` the opened object reader.
- `fa7a94e` streamed HTTP bodies; `fdab3c8` streamed responses on every transport.
- `ea1e73f` receive, publish and the closure check; `a3ce882` clone and fetch through them; `60a4f3b` the local clone's copy cap; `13aa28f` the checkout's regions.
- `560ea3b`, `b696785`, `f43302d`, `add68b9` SOURCES, MAP, the README and the CHANGELOG.
- `f77c4f9` this note.
- `c7d36bf` the unit row requiring a reverse index, red; `a0c8dd7` the reverse index; `1c33e69` its formatting; `48aa8ba` the `--no-local` rows' comment; `431c183`, `1c9c9fe`, `b6da436` MAP, the README and the CHANGELOG.

### Red first, on trunk's sources

At `bfa675c` (the rows, den's sources still trunk's), each tier:

| row | red by name |
|---|---|
| `large-pack-local`, `-file`, `-git`, `-ssh`, `-https`, `-fetch` | `den: wire: limit`, exit 2 |
| `large-pack-memory` | aborted under the cap (`memory allocation of 65520 bytes failed`) |
| `large-pack-object-limit` | `den: wire: limit`, not `den: wire: Unsupported(pack object size limit)` |
| `http-live-self` | `den: wire: limit` at 99.7 s |
| `http-live-argv` | 9 of 11 children held the fixture URL or token on argv |

### The large-pack rows

The fixture is built by the pinned Git from a seeded generator: a 1 MB text file rewritten over forty commits (40 deltas, deepest chain 14), three 48 MiB random blobs, a second branch and an annotated tag. Its one pack is 151,885,014 bytes. Every row compares process bytes and status, refs, HEAD, every reachable object's bytes, the remote configuration and the worktree, and runs the pinned Git's `fsck --full` and `status` on den's clone.

| row, release | den | git |
|---|---|---|
| local path | 10.97 s, 267,400 KiB | 0.70 s |
| file:// | 12.63 s, 274,224 KiB | 2.86 s |
| git:// | 12.38 s, 274,040 KiB | 3.01 s |
| ssh | 12.52 s, 274,164 KiB | 2.91 s |
| https | 14.53 s, 285,832 KiB | 3.51 s |
| fetch (configured, file://) | 12.68 s, 275,852 KiB | 3.46 s |
| memory, under `prlimit --as=419430400` | 12.48 s, 273,992 KiB | |
| object limit (one blob of 536,870,913 bytes) | refused by name in 0.1 s, nothing left | indexes it |

Natively den takes about twice as long (24 to 34 s). Peak RSS readings start at the harness's own RSS (an exec keeps the high-water mark), which the rows record as the spawn floor (about 39,000 KiB).

### den's own repository

`http-live-self`, release: den 206.2 s, 374,852 KiB, 39.2 s user; Git 131.1 s, 302,492 KiB, 4.1 s user; 4,937 objects; refs, HEAD, objects, configuration and worktree equal; Git's `fsck --full` and `status` clean on den's clone. Git's pack was 312,146,413 bytes.

### The streamed indexer

- **Receive:** the packfile section is read one pkt-line at a time, each in its own region; band 1 goes to `objects/pack/tmp_pack_den_*`, band 2 is dropped, band 3 is fatal. An HTTP body streams through the connection's one 64 KiB buffer with no whole-body cap.
- **Pass 1:** each entry is read by offset into a window sized from its declared size (grown by doubling only on truncation), inflated into a list reserved to that size, and covered by the CRC-32 and the pack's SHA-1. Whole objects are named; deltas record their base and declared target size, and a target over the cap refuses.
- **Pass 2:** deltas resolve depth-first from the whole objects; the bodies on the path stay under 96 MiB, and a deeper subtree waits for its own reconstruction (at most base, delta and result at once).
- **Install:** the idx v2 is byte-identical to the pack writer's for the same pack (the unit row checks this for none, OFS and REF packs). It is read back through the unchanged reader before `pack-<checksum>.pack` and `.idx` are published. A clone keeps the pack, and so does a fetch of 100 objects or more; a smaller fetch is rebuilt into loose objects.
- **Closure:** commits, trees and tags are read one at a time; blobs in the received pack are typed from its table, never read.

### The reverse index (found by the first full record)

The first full record, at `f77c4f9`, went red at `everyday`. Four local-path rows failed on both tiers: `local-clone-no-local-absolute`, `-loud-absolute`, `-relative` and `-loud-relative`. Each had `canonical_objects_equal=True` and one differing path, `objects/pack/pack-<checksum>.rev`, which Git's clone held and den's did not. Before vc23 these rows were reviewed (Git keeps a pack, den kept loose objects). Now den keeps the same pack and the same idx, byte for byte, so only the reverse index differed. gitformat-pack(5) documents the `.rev` format, and git-config(1) says `pack.writeReverseIndex` defaults to true, for every pack Git writes outside fast-import and bulk checkin. den now writes it beside every received pack: 'RIDX', version 1, SHA-1, each object's idx position in pack order, the pack checksum and its own. The unit row requiring it was red at `c7d36bf` (`no reverse index`). At `a0c8dd7` `tools/check-everyday` passes on both tiers, and the four rows pass exactly, no longer reviewed.

### den#66

The witness is in the field leg's evidence (trunk run 42241737464). In the failing `m2-commit-paragraphs` row, Git's snapshot holds `.git/objects/maintenance.lock` (empty, 0644) and den's does not. The index differs only in stat fields the index proof canonicalizes, and the loose object only in its zlib bytes. Git's commit starts `git maintenance run --auto --quiet --detach` (`GIT_TRACE2_EVENT`, field Git 2.56.0), and the oracle can snapshot while that child holds its lock. With `maintenance.autoDetach=false` the child is `--no-detach`; the oracle passes it on its own Git runs only, since the pinned environment's global config is part of reviewed rows' bindings. Polling for 100 ms after each commit returned, on the Mac with the field Git, the lock appeared after 2 of 1,200 commits with the default and after none of 1,200 with the fix: rare, as the leg's two single-row failures were, and gone. The oracle's probe is red at `c7d0eb5` and green at `1172e5b` with the field Git, and runs at the start of every oracle run, the field leg's included. A repeat count on the hosted runner is CI's.

## Done-when

- [x] Prediction first.
- [x] Rows red first on trunk by name, then green on both tiers: every transport, fetch, memory under a hard cap, the per-object refusal, den's own repository.
- [x] Streaming indexer, bounded delta resolution, no whole-pack cap, a per-object cap, nothing left behind on failure.
- [x] The fixture URL off every child's argv, held by `/proc/<pid>/cmdline`.
- [x] den#66: witness, cause and fix.
- [ ] The final gauntlet, the plant and the audit at the head: their records and every END line are in the PR body.

### Applied R-list

- **R-vc23-1 = (A), applied:** the whole-pack wire cap is gone. Memory no longer scales with the pack, so the cap protected only the disk, and the disk check is the write itself: a failed write refuses by name (`pack write failed`) and the temporary goes. Discovery, `ls-refs` and push responses keep their caps. Option (B), a larger stated cap, would have kept a size Git does not have.
- **R-vc23-2 = 512 MiB, applied:** the per-object cap is Git's `core.bigFileThreshold` default, the size above which Git itself stops treating an object as an in-memory delta candidate. At the cap the bound is about 2.7 GiB, inside a 6 GiB container. The pack reader's object cap rises from 16 MiB to the same value, or a clone could not check out what it indexed (den's HEAD has 19.9 MB blobs). Counts follow the idx reader's 400,000; delta depth stays 64. Options: 128 MiB (the old payload cap; den's own 98 MiB blob fits with little room), 512 MiB (recommended), 1 GiB.
- **R-vc23-3 = (a), applied:** Git cannot keep the fixture URL off argv over https (it passes it to `git remote-https`, per gitremote-helpers(7)), so the live push row no longer runs Git against the fixture. It reads the server's own ref advertisement through the pinned OpenSSL client, with the request and its credential on that client's stdin. Options: (a) as built; (b) keep `git ls-remote` through `GIT_CONFIG_*` and accept the helper's argv; (c) a local proxy that rewrites the path, which is more fixture than the row needs.

### Remaining limits

den's configured fetch does not create `refs/remotes/<name>/HEAD` as Git 2.56 does; the large fetch row configures `followRemoteHEAD=never` for both tools. A pack bitmap is still refused by name, so a plain local path clone of a repository with one refuses. The older whole-stream decoder keeps its 16 MiB and 128 MiB bounds for its own callers, as do push's pack writer and the other per-command caps. Delta depth stays at 64 and counts at 400,000. Peak readings start at the harness's RSS.
