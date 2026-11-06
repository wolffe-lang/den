# den

A version control system in [wolf](https://github.com/wolffe-lang/wolf-lang),
working toward Git-compatible repositories and wire protocols. Where a wolf
keeps what it has.

**State: loose and packed objects, index/worktree commands, bounded local history operations, and experimental file/git/SSH wire services.**
This is not a replacement for Git; M2, M3, M4 and M5 remain incomplete. Log/show support
bounded loose or packed history; branches, tags, branch switching and resets share
loose/packed ref storage. Merge, single-commit revert, cherry-pick and linear
rebase cover the measured subsets below. Full replay
semantics, gc policy and wider transport policies remain unfinished. Text diff has
two recorded equal-cost alignment differences; binary patches reconstruct the
exact blobs but do not always use Git's byte representation. `den --version`
prints `den 0.0.0 (built with wolf 0.2.36)`.
See [MAP](docs/MAP.md) for API contracts and [FORMATS](docs/FORMATS.md) for
measured bytes and documentation discrepancies.

## Machines and pins

| Role | Machine / identity |
|---|---|
| Behavioral oracle | Git 2.56.0, signed kernel.org tarball; default build, Ubuntu 24.04 image pinned by digest |
| Development witnesses | hasu core blocks for local object/history work; kasumi CPUs 4–7 for wire protocols and 12–15 for the initial census; Linux x86-64, rootless containers under core locks |
| CI PR gate | ubuntu-24.04, pinned container and oracle, including planner tests |
| CI full field leg | macOS arm64 with Homebrew Git; nonblocking observation, not the oracle |
| Toolchain | wolf 0.2.36 5adf3d91, lupin 0.1.58 tag 6240efe5 (binary embeds a5378e3), bundled std 78b9d3cb |

Archive and oracle pins are in `wolf-toolchain.toml` and `den-oracle.toml`.
Downloads fail on a digest mismatch. Both release-metadata reads are retained
in `notes/vc15-evidence/pins/`, including archive/staged-runtime and complete std
comparisons for Linux and Mac. Earlier reads are in `notes/vc14-evidence/pins/`
and `notes/vc13-evidence/pins/`; the original signature verification and matching
oracle builds are in `notes/vc00-evidence/`.

## Commands implemented so far

| Area | Commands and supported surface |
|---|---|
| Objects | `init`, `hash-object`, `cat-file -p/-t/-s`, `mktree`, `commit-tree`, `mktag` |
| Wire | `clone [-q] [--bare] URL DIRECTORY`; explicit `fetch -q URL SRC:DST`; configured/default `fetch [--prune]`, `pull` merge/rebase and `push`, `push -u`, plain/explicit `--force-with-lease`, `--force` and `--atomic`; `upload-pack`, bare `receive-pack`, and one-session loopback `daemon` within the limits below |
| Packs | `pack-objects` from stdin object IDs to `objects/pack/pack`, OFS/REF deltas or no deltas; `verify-pack [-v]`; `count-objects [-v]`; bounded `fsck --full`; `repack -a -n -q [-d] [-k]` and `prune-packed [-n] [-q]` within the limits below |
| Index | `write-tree` over nested index v2/v3/v4 entries; exclusive `index.lock` writes, stat fields, flags and TREE cache updates |
| Config / ignore | `config --get`, set/`--add`/`--unset`/`--unset-all`/`--replace-all` with local/global/file destinations; bounded `remote add/remove/rename/-v/get-url/set-url` and `branch --set-upstream-to`; `check-ignore` with provenance, negation, tracked-file bypass and `--no-index` |
| Worktree | `add` paths/directories, `-A`, `-u`, `--ignore-removal`, `-f`, `-N`, `--chmod`; `rm`, `mv` and their implemented safety/force/recursive options |
| Status | Human, short and porcelain v1, branch/unborn/detached headings, NUL output, untracked grouping and ignored paths |
| Commit | Ordered `-m`, `-F`, `-a`, `--amend`, `--reset-author`, `--author`, fixed `--date`, cleanup modes, quiet and allow-empty options; attached/detached HEAD and loose-over-packed branch updates |
| Diff | Worktree/index, `--cached`, two commits/trees or blobs; unified context, final-newline markers, modes, binary patches, stat/name forms, rename/copy detection and common pathspec magic |
| History | `log` default/oneline/short/full/fuller, `-n`, `--skip`, `--reverse`, `--first-parent`, fixed date formats, patch/stat, short/full/no/terminal-auto decorations; `show` commits, trees, blobs, annotated tags and `REV:path`; default-format display of `refs/notes/commits` notes |
| Restore | Index-to-worktree `restore`, `--staged`, `--worktree`, `--source`; `checkout -- <paths>` |
| Refs | Loose and packed refs with peeled tag records; branch list/create/force/delete/rename, lightweight and message-supplied annotated tags, command reflogs |
| Branch worktree | `switch` and branch `checkout`, `-c`/`-b` creation, explicit and implicit detached HEAD, dirty-worktree protection; `reset --soft/--mixed/--hard` |
| Merge | Fast-forward, already-up-to-date, bounded regular-file three-way merges, conflict stages and merge/diff3/zdiff3 markers; `--no-ff`, `--ff-only`, `--squash`, `--no-commit`, `--no-edit`, `-m`, `-F`, `--abort` |
| Revert / resolution | Single ordinary or root commit, `--no-edit`, `--no-commit`; merge-parent refusal; `add` saves REUC when resolving/deleting higher stages, and `commit` completes a resolved merge |
| Cherry-pick | Single commits and explicit commit lists; preserved source author/date, current committer, durable todo/head/options, conflicts, resolved `--continue`, `--skip`, `--abort`, `--allow-empty`, `--keep-redundant-commits` and `--empty=keep/drop/stop` |
| Revisions | Shared bounded parser/evaluator: documented ref precedence, full/prefix OIDs, pseudorefs, parent/ancestor chains, object peels, literal `REV:path`, numeric reflogs and previous checkout; `log` exclusions/ranges and `diff` dotted endpoints |
| Blame | Default columns, numeric/offset `-L` unions, `-w`, ordered merge parents and `--first-parent`, whole-file renames, raw line bytes, `--porcelain` and `--line-porcelain`; conservative alignment limits below |
| Stash | `push`/bare/`save` with `-m`, `-q`, `--keep-index`; `list`; `show` (diffstat default, any diff option); `apply`/`pop` over the shared merge plan against the index tree; `drop` (reflog record rewrite) and `clear`; `stash@{N}` and bare `N` through the shared evaluator |
| Notes | `notes add` (`-m`, `-f`, `--allow-empty`), `show`, `list`, `remove` (`--ignore-missing`) and `get-ref` over `refs/notes/commits`; any permitted fan-out read, the measured fan-out written |
| Rebase | Linear current-branch replay with explicit upstream, `--onto`, `--reapply-cherry-picks`, durable `rebase-merge` state, conflict stops, skip/abort and continuation after an explicit resolution commit; editor-dependent continuation remains refused |

Status, commit summaries and diff share one rename/copy pairer. Exact OIDs are
matched first; edited regular files use measured chunk-hash similarity, with
50 percent as the default threshold. Executable-bit changes do not prevent
regular-file pairing. A 100-percent score can result from fingerprint
collisions and is not an identity test; summaries still count actual edits.
Quiet commit remains independent of display scoring.

Two text alignment witnesses remain byte-different from Git's default, despite
reconstructing the same files. Each input, context width and both outputs are
bound in `tests/review/diff-hunks.json`; they are not counted as parity.
Binary output is independently decoded and applied in both directions with Git.
The expanded binary corpus has 154 exact bodies and 96 capture-bound encoding
differences out of 250; the strict byte report remains visibly red. Ordinary
headers, literal sizes, blob identities and framing remain exact or validated.

## Build and measure

Run `tools/gate` inside the pinned Ubuntu container, holding the assigned
core-block lock and applying `taskset` inside the container. Rootless hosts
without delegated cpusets must not rely on pinning only the outer process.
Keep the CI build mount `/work/den`: the default oracle binary's pinned digest
also depends on its build path, not merely the base image and version.
The gate checks formatting, builds native/release binaries, runs actual checked
programs, constructs the corpus twice, compares against the pinned oracle and
builds the static Linux archive. `tools/mkden OUTDIR` checks ET_EXEC/no PT_INTERP
and prints full/stripped binary digests. No host-specific glibc is substituted.

Inside that container, with `DEN_GIT` set to the pinned built Git:

```sh
tools/env COMMAND ARGS...          # fixed identity, dates, locale, hooks and HOME
tools/corpus target/corpus --prove-twice
tools/check-config
tools/check-index
tools/check-ignore
tools/check-worktree
tools/check-commit
tools/check-blame                  # immutable original/new loose/packed fixtures
tools/check-stash                  # stash/notes complete state, loose/packed, client, checked units
tools/check-revision               # loose/packed grammar and independent clients
tools/check-history
tools/check-refs
tools/check-merge
tools/check-replay
tools/check-pack                   # after corpus and inherited client builds
tools/check-pack-write             # after check-pack/check-stash; interop, sizes, commands and corruption
tools/check-wire                   # file/git peers, received streams and configured porcelain
tools/check-porcelain              # remote/tracking, typed push, leases, pull and checked units
tools/check-ssh --host PEER --peer-root OWNED_PINNED_FIXTURE # live system-SSH leg
tools/check-housekeeping           # closure, verified retirement/recovery, validator and checked parser
tools/check-delta
tools/check-rename
tools/check-diff
tools/check-diffbinary --reviewed-body --with-cli
tools/oracle                      # parity, shape and named not-yet rows
tools/oracle --filter status       # empty selections are errors
tools/oracle --strict              # fails while named not-yet cases remain
```

The gates include external-package clients, real filesystem operations,
index lock contention, ref CAS/lock collisions and injected failures, command-state snapshots,
ignore precedence and diagnostics, fixed dates/messages, object interop and
full repository-byte comparisons. Formatting/date API comparisons are not a
claim of CLI stderr/exit-status parity. A checked result means the JSON verdict
from `wolf conform-run --checked`, not merely a successful process exit.

The expanded main matrix contains 190 cases: 183 parity requirements, 6 named not-yet and
one version-shape check. Generated diff, similarity, pairing and application
matrices are reported separately in `notes/vc04-evidence/`; their explicit
representation/alignment differences are never added to the parity count.
History has a separate exact command/state matrix on native and release,
bounded actual-checked units and an independent package client. The inherited
diff exceptions remain separately counted. Module/prose changes use final-head local gauntlet and plant evidence;
cross-cutting changes retain the labelled CI gate described below.
The gauntlet also publishes a generated-input plan; operational pruning retains
every input named by a remaining leaf, including the strict binary-report client.
Object, pack and protocol algorithms have no Git, Python, zlib or OpenSSL
implementation dependency. The file transport starts the selected remote service
executable: Git's service by default, or native den service probes through
`DEN_UPLOAD_PACK` / `DEN_RECEIVE_PACK`. There is no shell command parser in den.
The self-hosted file tests run with empty `PATH` and `GIT_EXEC_PATH`. Shipped wolf
code uses wolf-std and the provenance-marked SHA-1 code from boreutils.

## Corpus and comparison rules

The corpus now defines 16 repositories: the original nine object/history
fixtures plus ignore, staged rename, modes/symlink, unborn, amend, index-v4 and
edited-rename states. `tests/cases.json` currently defines 190 main cases.
The main classifications are stated above. The generated config,
index, ignore, worktree, commit and diff matrices run separately.

Every compared repository file is included. The `loose-object-raw` comparison
checks uncompressed object bytes, OID, framing and checksum with valid,
size-bounded compression; it does not require identical deflate streams.
Other bytes remain exact, except six inode/time index words may be compared
canonically only after each is independently proved against that tool's own
worktree stat. Mode, uid, gid and size are never normalized. Neither ignoring
the index nor accepting a recomputed checksum is such a proof.

An expected not-yet refusal is not a parity pass or a reviewed difference.
[Review records](tests/review/README.md) bind the complete command result and
repository state to a specific case; there are no wildcard exclusions.

## Repository and command limits

The SHA-1 store reads and writes loose objects and pack-v2/idx-v2 pairs.
Binary object/tree names are preserved, but filesystem path arguments
remain UTF-8 `str`; raw non-UTF-8 OS paths have named upstream limitations.
SHA-256 IDs are representable, but SHA-256 repositories are refused before writes.
GC expiry/reflog/ref-packing policy, on-disk thin packs, multi-pack-index, bitmaps, alternates, linked worktrees,
submodules and unstaged revision forms remain unsupported.
`log` accepts inclusions, `^REV` exclusions and two-/three-dot sets. `diff` treats
a dotted range as endpoints, with one merge base required for three-dot. Other
consumers take single objects (or explicit lists of single objects), not sets.
The history walk is timestamp-ordered with stable parent-order ties, duplicate
suppression and a first-parent option. See the explicit grammar in MAP.

Revision inputs are limited to 4,096 bytes, 256 suffixes and 10,000 ancestry
steps; a peel visits at most 64 objects. Tree paths preserve raw bytes in the
public API; OS argv remains UTF-8-limited. Numeric reflogs and `@{-N}` are read
without mutation, including branch-aware previous checkout for switch/checkout.
Date/message/index selectors, parent-set shorthands and upstream/push tracking
revision suffixes are refused by name; branch tracking configuration is supported
through the bounded remote/push/pull commands. Ref ambiguity warns and follows the documented search
order. Prefix disambiguation honors a consumer's object-kind requirement: a
unique commit-ish candidate can satisfy `log` even when a blob shares its prefix.
Untyped consumers retain the ambiguity and its candidate diagnostics.
The grammar gate compares 366 command results and 98 independent-client results
across loose and packed fixtures per native/release tier, with sixteen separate
named scope captures and an actual-checked parser program. Reads preserve every
repository/worktree file, including a foreign index lock and dirty worktree.

TREE and REUC index extensions are validated and preserved. UNTR, FSMN, IEOT,
EOIE, split-index `link`, sparse-index `sdir` and unknown extensions are refused
by name. Higher merge-stage entries can be read and written. Resolving or deleting
them through `add` records the original stages in REUC; unrelated higher-stage
`rm`/`mv`/restore operations remain refused.

Config parsing handles quoting, escapes, continuation and precedence, but
`include`/`includeIf` are named refusals. Config supports `--get` and legacy
set, `--add`, `--unset`, `--unset-all` and `--replace-all`, with `--local`
(the default), `--global` through HOME and `--file`. It preserves unrelated
comments/lines and modes, writes an exclusive lock, rechecks the original bytes,
syncs and atomically renames. Existing file symlinks keep the link and update
their referent; dangling links and nonregular destinations are refused by name.
System writes, worktree scope and value-pattern/
regexp edits remain named unsupported options. Remote/tracking editing retains
its separate continued/CRLF/BOM, inline-assignment and multiple-URL limits.
Diff implements literal, top, icase, glob and exclude
pathspecs; other commands retain their earlier literal-path limits. Attribute
pathspecs, filters/attributes, non-false `core.autocrlf`, nonempty templates/hooks,
signing and user editor execution remain unsupported. A requested editor is never launched; the measured
`GIT_EDITOR=false` failure is handled explicitly. Relative dates such as `now`
are refused; deterministic raw, RFC 2822 and ISO/calendar inputs are supported
within the formatting API's stated bounds.

Diff's pure `collect`/`render` API does not publish state. The CLI follows
`diff.autoRefreshIndex`: a selected stat-only match triggers refresh of all
unchanged index entries, unless disabled or a foreign index lock prevents it.
Cached/two-object comparisons do not refresh. The gate proves the six permitted
inode/time fields against each tool's own files; modes and sizes remain exact.

Diff bodies are limited to 16 MiB per file, aggregate endpoints to 128 MiB,
text sequences to 200,000 lines and general edit searches to 2,000 changed
lines. Rename pools are limited to 2,000 candidates per side. Exceeding a bound
returns a named failure, never an approximate result presented as exact.

History readers never write the index, objects, refs or reflogs. Root patches
compare with an in-memory empty endpoint; ordinary patches reuse the shared
diff collector and renderer. Unique abbreviations grow past collisions.
History caps each object at 16 MiB, discovered commit data and rendered output
at 128 MiB, and the CLI walk at 10,000 commits. The public walker accepts an
explicit node budget. It is a bounded whole-history reader, not a streaming walk.

Default `log -p` omits merge patches as Git does. `show` of a merge prints the
dense combined diff (`--cc`, the default) or `-c`, with `-U<n>`; `show -s`
renders its ordered parents and message. Combined `--stat`, other pretty formats,
`--binary`, attributes, `-m`, `--diff-merges`, `--combined-all-paths`,
`--remerge-diff` and `log -c`/`--cc` stay named refusals. Show-specific
revision limiting, show ranges, history path simplification, graph/topological order,
custom formats, relative/human dates, non-UTC local zones, message transcoding,
mailmaps and tabs after non-ASCII text remain named unsupported surfaces.
Fixed dates include default, short, raw, unix, ISO, strict ISO and RFC forms;
UTC-local variants are measured. UTC rendering needs no zone database; missing
zones fall back to UTC without changing stored numeric offsets. `--decorate`,
`--decorate=short|full|no|auto`, `--no-decorate` and `log.decorate` render HEAD,
branches, tags and remote-tracking refs. Auto decorates only at a terminal;
the default terminal colour palette and colour-free output are measured.
Custom decoration filters/palettes remain outside this bounded surface.
None of the remaining limitations is a parity pass.

The refs gate separately compares 632 command/state rows per native tier,
with seventeen named unsupported cases kept outside that count, fourteen independent
client checks, and two bounded actual-checked programs. It compares command
output, exit status, objects, HEAD, loose/packed refs, reflogs, index and worktree
state on native and release.
Branch/tag listing patterns, tracking-aware branch display, overlapping rename paths,
merge-mode checkout and orphan branches stay outside
this bounded surface. Explicit unsupported cases are counted separately.

Ref commands share the revision evaluator, including ancestry, peels, numeric
reflogs and previous-checkout inputs where appropriate. Set operands refuse by
name rather than selecting an arbitrary tip. Packed-ref files are bounded at 16 MiB and
100,000 records; a listing is bounded at 4,096 entries. Tree transitions refuse
higher-stage or flagged index entries and submodules rather than losing their
metadata. `switch` protects in-progress operations; `reset --soft` refuses an
in-progress merge. Reflog management/expiry commands remain future work.

The merge gate separately measures **132 exact command/state cases**, **12
named not-yet captures**, **1,521 exact three-way file merges** and **84 complete
merge-base sets** on each native/release tier. Independent packages import the
file and graph boundaries; three bounded actual-checked programs cover graph,
markers and resolve undo. The state comparisons include merge files, objects,
reflogs, packed refs, locks, index stages and the inherited per-file stat proof.

The file API follows `git merge-file`'s Myers default. The tree merger does not
silently substitute Myers for `ort`'s histogram policy: when both sides change a
file, repeated base-line hashes and multiple edit hunks on either side are named
refusals. Recursive virtual bases for criss-cross histories, rename topology,
modify/delete and binary conflicts, nonregular tree entries, unborn merges,
annotated-tag messages and dirty/staged true-merge recovery are also refused.
Fast-forward dirty/untracked safety remains measured. `revert -m`, sequences,
`--continue`/`--skip` and revert abort are not implemented. Merge editor execution
and the previously named history limits remain open.

The replay gate compares **96 exact complete-state scenarios** and **20 named
scope captures** on each native/release tier, including multi-process resolution
and recovery sequences. An independent importing client checks 136 records per
tier; a bounded actual-checked program covers records, empty policy and the
conservative equivalence checksum. All repository files remain in comparisons.

Replay reuses the same tree/file engine and rename scorer; it does not remove
any merge limits above. Default rebase refuses possible upstream patch equivalence
rather than silently replaying a commit Git would omit. Its conservative
whitespace-normalized net-line checksum is only a refusal filter, never a reason
to drop a commit. `--reapply-cherry-picks` bypasses that preliminary check, not the
merge engine's alignment limits. Empty results are then dropped as measured.

Interactive and apply-backend rebase, merge replay, upstream/branch inference,
a separate branch operand, and editor-dependent continuation remain unsupported.
To continue after resolving a rebase conflict, explicitly commit the staged
resolution with the desired message/author/date before `rebase --continue`.
Cherry-pick dirty skip/abort and foreign `AUTO_MERGE.lock` cases retain named
transient-stat boundaries; no index field is excluded to call them parity.
Recovery refuses a changed original rebase branch or cherry-pick abort tip,
unfamiliar state files and unsupported replay configuration before writing. Replay state files are data, never scripts
to execute. Selected commit data is bounded at 128 MiB, todo records at 16 MiB
and 100,000 entries; each applied step has reclaimable scratch storage.

Commit writes support attached and detached HEAD. Loose refs override packed
records; an unchanged packed tip is not needlessly unpacked. Amend retains
the existing parents and normally its author; it does not change ORIG_HEAD.
Index/ref/reflog publication is not a multi-file atomic transaction. An ordinary
commit can refresh the index before a message/editor abort, whereas `commit -a`
keeps its prepared index unpublished until ref publication succeeds. FORMATS
records these lifecycle differences and the possible earlier object/message
side effects. Unsupported-command refusals must not be confused with rollback
of every ordinary commit failure.

## Blame boundaries

Blame uses the shared revision evaluator and raw loose/packed object readers;
it never writes the index, objects, refs or reflogs. A whole-file-identical
parent wins before partial matching; otherwise parents transfer lines in their
stored order. Whole-file renames reuse the existing 50-percent rename pairer.
The original bytes are rendered even when `-w` changes comparison semantics.
Without an explicit revision, only worktree contents identical to HEAD are
supported; uncommitted contents are a named refusal.

Changed repeated/hash-colliding lines, reordered common lines and multiple
origin paths for the same commit refuse rather than guess an alignment.
Unchanged repeated content is supported. Function/regex `-L`, moved/copied-line
`-M`/`-C` (all levels), ignored revisions, reverse history, alternate contents,
nonregular paths, mailmaps, attributes, message transcoding, non-ASCII author
display widths and unsupported blame/diff configuration remain named limits.
Porcelain retains raw identity/content bytes; the public path API accepts raw
non-UTF-8 tree names, while argv remains UTF-8-limited.

Bodies cap at 16 MiB/200,000 lines, inherited edit searches at 2,000 changes,
and attribution at 10,000 work items with 128 MiB of charged commit/blob,
rename-input and line-position payload. Numeric ranges cap at 256 operands of
4,096 bytes. Rendering caps at 128 MiB and reclaims per-line scratch; the shared
comparison boundary reclaims each edit search's scratch. These are payload/work
bounds, not streaming or peak-RSS guarantees. `tools/check-blame` compares 241 new
and 50 inherited-corpus command/state rows **per storage mode and native/release
tier**, with six independent client rows and ten separately named refusals per
mode. A small actual-checked program covers line correspondence and numeric
ranges. This does not complete M3: all inherited merge/replay and editor
limitations remain open.

## Stash and notes boundaries

A stash entry is constructed before it is published: I records the index over
HEAD, W the worktree of every path the index or HEAD tracks, over [HEAD, I]
(git-stash Discussion). Objects are written first; `refs/stash` and its
always-written reflog follow, then the measured reset (ORIG_HEAD and HEAD's
`reset: moving to HEAD` record). The index is refreshed and written before the
unborn, no-change and lock checks, as the oracle does. Recovery is separate:
`apply`/`pop` merge W into the current index tree through the existing merge
plan (base W^1, labels `Updated upstream`/`Stash base`/`Stashed changes`), then
return changed paths to their previous index entries as zero-stat tree entries
while new paths stay staged; `AUTO_MERGE` names the merged tree. `drop` takes the
reflog lock first, rewrites the following record's old id and writes a loose
`refs/stash` even when its value is kept.

Notes are blobs in a tree under `refs/notes/commits`. Any permitted fan-out is
read; writes use the oracle's measured shape: flat until each of the sixteen
first-hex-digit groups holds two notes, then two-hex directories (R-vc12-2).
`log`/`show` display the default ref's notes in the default format only.

Named refusals: untracked/ignored snapshots (`-u`/`-a`) and their entries,
`-p`, `--staged`, path-limited push, `--index`, conflicting apply, `branch`,
`create`, `store`, `export`, `import`, `list` log options, `show -u`, `stash.*`
configuration; notes `append`, `copy`, `edit`, `merge`, `prune`, `-F`/`-C`/`-c`/`-e`,
the editor, `--ref`, `GIT_NOTES_REF`, `core.notesRef`, `notes.displayRef`,
`--stdin`, and notes in non-default formats or with patch and stat.
`tools/check-stash` compares 104 complete-state cases (395 intermediate
processes) and 39 named refusals **per storage mode and native/release tier**,
19 independent client rows per mode and a bounded actual-checked unit.

## Packed object reads

Packed lookup sits beneath the existing object API. Loose objects take precedence;
only absence falls back to packs. Prefix lookup merges and deduplicates both
namespaces, and writes do not duplicate objects already packed. Multiple packs
and `.keep` files need no special caller behavior. OFS_DELTA and in-pack REF_DELTA
chains reconstruct owned bodies, including forward REF bases.

Both file SHA-1 trailers and their binding are verified before lookup results
are used. The index validates fan-out, sorted unique names, CRC entries and
32/64-bit offsets. Each reconstructed entry checks CRC, zlib consumption, sizes,
delta instructions and its independent object identity. Corruption is a named
error, not a missing-object fallback.

Pack hashing and file reads use reclaimed 64-KiB offset windows without mmap.
Compressed entries and reconstructed bodies are bounded whole-object buffers:
512 MiB per inflated entry/body (Git's `core.bigFileThreshold` default; it was
16 MiB before vc23), that plus a sixteenth and 64 KiB compressed, 64 delta
links and three objects' worth of charged reconstruction input/output per read.
Inflated entries are reserved to their declared size. Indexes are bounded at
16 MiB/400,000 objects, directories at 8,192 entries and 256 packs. No persistent
verification cache or pack-size-independent CPU cost is claimed: checksums scan
candidate packs again on each lookup.

`tools/check-pack` checks 2,442 raw objects across 34 oracle-packed fixtures per
native/release tier, plus independent corruption/limit inputs, an importing client,
a bounded actual-checked delta/CRC program, and the existing history, refs, merge
and replay matrices over packed copies. The fixture builder checks that packing
preserves the entire object namespace, including unreachable objects. Existing
M2/M3 refusals and diff representation exceptions remain unchanged.

## Packed object writes

Pack construction writes v2 packs and v2 indexes, with undeltified, OFS or REF
entries. It shares the binary patch encoder, considers ten prior candidates and
caps delta chains at fifty. Bounds are 10,000 objects, 16 MiB per body and
128 MiB of aggregate input/output. There is no streaming or peak-RSS guarantee.
`pack-objects` accepts a stdin object list and the repository's
`.git/objects/pack/pack` base; that command's stdout transport, thin output and
nondefault window/depth settings remain named refusals. Wire services call the
shared encoder directly; received thin streams are reconstructed as canonical
loose objects rather than installed as thin on-disk packs.

Publication writes and syncs an exclusive temporary pair, validates every object
through the existing reader, then renames pack before idx and syncs the directory.
Ordinary failures clean owned temporaries. A repeated publication can restore a
missing index after independently verifying the orphan pack against the new index.
This is not a two-file transaction; the writer itself never prunes loose objects.
GC, cruft packs, .keep policy, bitmaps and multi-pack-index remain unimplemented.

The writer gate checks 61 source fixtures in three modes, 15,207 object reads
per native/release tier, and all-object Git verification after isolating the new
pack from loose and older packed copies. Pack bytes need not equal Git's:
compressed OFS packs measure at most 1.025967 times Git's size and REF packs
1.399425 times, against a 1.5 ceiling. REF has limited headroom. No-delta mode
is gated against Git explicitly given `--window=0 --no-reuse-object` (maximum
1.054644); its similarity/default-Git ratio of 12.254789 is retained separately.
Publication failure/corruption tests and a real fifty-link chain are separate
from the bounded actual-checked delta program.

`verify-pack -v` renders the validated physical object listing and chain-length
histogram. `count-objects -v` reports actual allocated loose blocks and pack/index
sizes; unavailable allocation metadata is a named refusal. `fsck --full` checks
objects, typed links and HEAD/ref/index/reflog roots without writes. It supports
`--no-dangling`, `--no-reflogs` and `--no-progress`. Single-file commit graphs
validate chunk framing, fanout, object names, parent edges, checksums and object
database metadata, including corrected generations. Missing objects, corrupt
loose headers/hash paths, wrong tree types and invalid roots have measured
bounded diagnostics. Multiple dangling/missing output ordering, multiple broken
links, malformed refs and unmeasured diagnostic combinations remain named;
split/Bloom graphs and strict/configured checks are also refused. The main packed
fsck fixture now requires exact parity. No M4 completion is claimed.

Housekeeping separates reachable selection, pair construction, verified publication
and removal. Roots include refs, HEAD, both reflog endpoints and the index, including
valid cache-tree records. `repack -a -n -q -d` retires only redundant packs;
if an old pack has unreachable objects outside the replacement, it refuses before
publication. Add `-k` to retain every old packed and loose object. Incremental
repacking, `-A`, server-info updates and nonquiet output remain named refusals.
`gc` remains separate and unsupported: repack never expires reflogs, packs refs,
prunes unique unreachable objects or writes a commit graph.

Every replacement is read back before retirement. A synced retirement record
allows a repeated repack to finish interrupted pack/index removal after verifying
the replacement again. An incomplete or foreign record is preserved and refused;
foreign temporary files are never swept. Interrupted retirement can leave an old
index without its pack, so ordinary den reads may refuse until repack recovery.
The new pair remains independently readable; this is not a multi-file transaction.
`prune-packed` verifies packed copies before removing loose duplicates and removes
empty fanout directories. Its dry run preserves raw directory order within each
hex prefix; both tools are compared on one immutable physical fixture.

The housekeeping differential has 56 exact command/state rows and four separate
unreachable-retirement refusals per tier. Validator tests add 41 exact immutable
commands and three independent metadata clients. Five interruption phases,
foreign files, repeated cleanup, orphan publication and bounded actual-checked
parser tests have separate witnesses. The larger repetitive/binary/mixed writer
fixtures retain the original REF 1.399425 headroom warning and every 1.5 size gate.

## Wire protocols and transport bounds

The wire layer uses binary-clean pkt-lines, protocol-v2 capability advertisement,
`ls-refs`, and `fetch` with want/have/done and multiplexed pack data. Text writers
emit LF; readers accept the optional missing LF required by the protocol. Push
uses Git's documented receive-pack framing, capability negotiation and per-ref
status, not an invented v2 push command.

Supported command forms are explicit:

```sh
den clone -q --bare file:///absolute/source.git destination.git
den clone -q git://127.0.0.1:9418/source.git destination
den fetch -q URL refs/heads/main:refs/remotes/origin/main
den push -q --force URL refs/heads/main:refs/heads/main
den push -q --atomic URL HEAD:refs/heads/a HEAD:refs/heads/b
den remote add origin file:///absolute/source.git
den fetch --prune
den push -u origin main
den push --force-with-lease=refs/heads/main:EXPECTED_OID
den pull --no-rebase
den pull --rebase
den clone -q --upload-pack=/owned/fixture/upload ssh://kasumi/owned/repo.git destination
den daemon --enable-receive-pack /dedicated/export/base 9418
```

Clone requires a new destination. Normal checkout uses the existing verified
worktree/index transaction; bare clone preserves the selected HEAD and branch/tag
refs. Fetch accepts one fully qualified source/destination refspec, with `+` or
`--force` for deliberate rewrites. Push accepts explicit refspecs, deletion and
force; local fast-forward/tag checks precede transmission, and receive-side policy
and expected-old-id checks precede reference publication. Outside `refs/heads` and `refs/tags`, unforced updates require both values to
peel to commits and fast-forward; distinct tags of the same commit are allowed.
Changed tree/blob values require force. Branches always require commits, even
when forced; tags reject replacement without force. The measured receiver
refuses remote updates to `refs/stash` as `funny refname`, including forced
creation; local stash storage is unchanged. Failure diagnostic text
and the remaining porcelain spellings are not general Git CLI parity claims.

The daemon serves one connection on IPv4 loopback, requires
`git-daemon-export-ok`, checks canonical repository and administrative paths
against its export root, and enables writes only with the explicit flag. The
transport supports plain `file:///absolute/path`, `git://host[:port]/path`,
`ssh://[user@]host[:port]/path` and scp-like `[user@]host:path` forms up to
4,096 bytes. SSH uses the system executable and an argv vector. The remote
command is the program word and the single-quoted path, as Git sends it: a plain
program word (letters, digits and `._/+-`) goes bare, because a service that
parses the command itself, as GitHub's does, refuses a quoted one; any other
`--upload-pack=`/`--receive-pack=` value is a literal executable and stays quoted.
Percent-escaped paths and IPv6 SSH forms remain named limits. TCP operations have 30-second deadlines; local and
SSH services use mapped byte pipes. An sshd that does not accept GIT_PROTOCOL
serves protocol v0, which den refuses rather than falling back. The live fixture
uses explicitly selected owned wrappers exporting protocol v2, not sshd changes.

Receive-pack currently requires a bare repository. Atomic receive is advertised
only without the unimplemented reflog policy. It locks every target and
`packed-refs`, preserves old values in a packed snapshot while removing equivalent
loose shadows, then publishes all new values with one `packed-refs` rename.
Precommit failure preserves every logical old value. This is not a reflog
transaction, crash-lock recovery or concurrent reader snapshot-isolation promise;
a postcommit directory-sync failure is reported separately from the committed
logical result. Non-atomic requests retain per-ref outcomes.

Clone and fetch stream the response's packfile section to a temporary under
`objects/pack` as it arrives, as `git index-pack` does (vc23, den#61): no
response, HTTP body or pack is held in memory, and there is no whole-pack cap.
A failed write refuses by name and removes the temporary. The pack is then read
back by offset. Each entry is inflated into a buffer reserved to its declared
size, and its CRC-32 and the pack's SHA-1 are checked over the same bytes.
Deltas resolve depth-first from the whole objects, with the bodies on the
walk's path bounded at 96 MiB (Git's `core.deltaBaseCacheLimit` default); a
deeper subtree is revisited from its own reconstruction. Objects cap at
512 MiB (`pack object size limit`), counts at 400,000 and delta depth at 64.
The fetch asks for no thin pack, so the received pack is self-contained. Its
idx v2 is written and both are installed: a clone keeps the pack, as Git does,
and so does a fetch of 100 objects or more (`fetch.unpackLimit`'s default); a
smaller fetch is rebuilt into loose objects one at a time. Peak memory follows
the largest object, not the pack: at most about 64 MiB + 96 MiB + 5 times the
largest object, measured by `tools/large-pack-test.py` under a hard
address-space cap. The selected closures are checked before refs change,
typing blobs from the received pack's own table without reading them.

`pack.decode`, the whole-stream decoder, remains for its own callers with its
bounds: 10,000 objects, 16 MiB per body, 128 MiB of charged payload and 64
delta links. Thin streams are never stored as thin on-disk packs.

`tools/check-wire` exercises native/release peers in both directions against the
pinned Git services and daemon, native self-hosted services without external tools
on PATH, normal checkout, force/policy/atomic outcomes, explicit atomic failure
phases and actual-checked pure parsers. A separate received-stream family has four
real Git pack modes and thirteen malformed/strict-input cases; it retains complete
process bytes, canonical object comparisons, refs, fsck results and raw streams
under `target/runs/wire-*` and `target/runs/wire-pack-*`. The original 16-repository
main corpus and its 190-case classification remain separately counted.
Shallow/filter/URI fetches, arbitrary unadvertised wants, hooks, non-bare receive,
atomic reflog policy, linked worktrees, SHA-256 repositories, broader configuration
and remaining porcelain/error-output parity are not complete. No M5-complete
claim is made.

### Smart HTTP and HTTPS

```sh
DEN_TLS_ROOTS=/path/roots.der den clone -q https://github.com/OWNER/REPO.git destination
den clone -q --tls-roots=/path/roots.der https://host/repo.git destination
DEN_HTTP_TOKEN=... den push -q https://host/repo.git refs/heads/main:refs/heads/main
den clone -q http://127.0.0.1:8080/repo.git destination
```

Clone, fetch and push speak Git's smart HTTP protocol (`gitprotocol-http(5)`):
discovery is `GET …/info/refs?service=git-upload-pack` or `git-receive-pack`,
followed by stateless POSTs. Fetch uses protocol v2 (`Git-Protocol: version=2`,
`ls-refs`, then `fetch` with want/have). Discovery may start with `version 2` or
with exactly the matching `# service=` banner and a flush before it, as GitHub
sends it. Push uses receive-pack with the status report, leases and atomic
pushes where the server advertises them, and side-band-64k demultiplexing.
The dumb protocol, protocol v0/v1 advertisements, mismatched service banners
and unexpected RPC content types are refused by name.

HTTPS runs over the wolf standard library's TLS 1.3 client. The trusted roots
are a file of concatenated DER certificates, named by `--tls-roots=PATH` or by
`DEN_TLS_ROOTS` (the option wins). Nothing else is read: no system store,
`GIT_SSL_CAINFO`, `GIT_SSL_NO_VERIFY` or `http.sslVerify`. A PEM bundle converts
to this form with `openssl x509 -outform DER` per certificate, concatenated.
Certificates are checked against the host clock in UTC, the URL's host name
(SNI and subject alternative names), key usage and the issuer path. A bad
certificate or an unknown root fails with the client's own name for it
(`issuer_mismatch`, `name_mismatch`, `expired`, `not_yet_valid`, `not_ca`,
`bad_usage`, `bad_signature`, …). There is no insecure mode. Plain `http://` is
accepted only for literal loopback addresses, for tests.

Authentication is HTTP Basic. The user is `DEN_HTTP_USER` (default
`x-access-token`), and the token is `DEN_HTTP_TOKEN`, or is read without echo from
the terminal when stdin is one. Credentials are bound to the original origin and
never follow a redirect to another. They are never written to a file, a reflog,
a diagnostic or the recorded rows. A configured `credential.helper` and every
`http.*` setting except `http.followRedirects=initial` are refused, and no
helper is executed. Discovery follows at most five same-scheme redirects; a
scheme change, a changed discovery suffix and any redirect of an RPC are
refused.

Responses are HTTP/1.0 or 1.1 with Content-Length or chunked framing.
Header blocks are capped at 64 KiB, header lines at 8 KiB and fields at 256.
Discovery, `ls-refs` and push responses keep their caps (140,000,000 bytes at
most), and each read's buffers and TLS records are freed when the read ends.
A fetch response streams a pkt-line at a time through the connection's one
reused 64 KiB buffer, with no whole-body cap. A close-delimited HTTPS body is refused until the
standard library can tell a clean close from truncation (wolf-std#133).
A failed clone removes the directory it created, as Git does.

`tools/check-http` runs the HTTP units natively, in release and on the
checked machine. It also runs raw-peer and hostile-input rows, TLS rows against
the pinned OpenSSL, memory, redirect, authentication and refusal rows, and
clone, fetch and push against the pinned `git-http-backend` over plain HTTP
and authenticated TLS. Two live rows read from github.com:
a small public repository and den's own repository (a pack over 300 MB), each
cloned by den and compared with Git's clone, den's own within its predicted
time and peak memory. Both are named SKIPs without network. A third fetches,
pushes and deletes a disposable branch on the repository that
`DEN_LIVE_HTTPS_URL` names, with `DEN_LIVE_HTTPS_TOKEN`, and is a named SKIP
without them. It names that repository only in the environment, as a remote
den reads from `GIT_CONFIG_*`, and checks every child's `/proc/<pid>/cmdline`
for the URL and the token while it runs.

Configured fetch/push cover ordinary scalar URLs and wildcard branch fetch maps,
branch defaults, tracking updates/prune, `push -u` and plain/explicit leases.
Pull selects CLI/config merge or rebase policy and reuses the existing M3 engines,
including conflict state and their existing conservative refusals. Divergence
without a reconciliation policy and ff-only divergence fail before ORIG_HEAD.
Rewritten-upstream/fork-point rebase, octopus selection, broader refspec/config
forms, multiple-URL editing and existing unconfigured local paths remain named
limits. CLI service selectors and remote uploadpack/receivepack values select
literal executables; they are not shell commands.

The portable porcelain gate defines **892 fixture groups per native/release
tier**: 48 remote/tracking, 770 typed update-policy, 48 configured/lease/failure
and 26 pull groups. The typed matrix compares acceptance and resulting refs,
not exact failure text/status; complete raw outputs are retained. Other groups
compare full process results and repository state, with one exact-input-bound
receive-service stderr REVIEW rather than a parity pass. Pure units, review
binding mutations and 12 live Mac-to-peer SSH groups are counted separately.
See MAP for the auto-identity and service-sideband diagnostic limits. These
measurements do not complete M5 or remove any M3 limit.

Owned SSH fixtures accept an explicit `ssh-peer.py --lane` owner; the default
retains the earlier fixture contract. Mismatched owners and paths escaping their
lane directory are refused before fixture writes. The live client takes its
host and fixture root from the plan (`DEN_SSH_HOST`, `DEN_SSH_PEER_ROOT`) and
refuses any other before network access. This changes only the test endpoint,
not SSH configuration, keys or the supported wire protocols.

## Loose objects and historical measurements

Objects own their binary data and algorithm-tagged IDs. Reads validate zlib,
canonical header/size, full consumption and the independent OID. Tree sorting
uses Git's directory-aware byte order. Generic headers/messages retain unknown
fields and continuations. Commit creation alone applies the measured UTF-8
repair/warning when no non-UTF-8 encoding is selected; explicit ISO-8859-1
preserves the input bytes.

Loose writes use an exclusive temporary, complete write and sync, atomic
no-replace hard-link installation, owned temporary cleanup and directory sync.
Concurrent writers validate the installed winner. Abrupt termination may leave
an orphan temporary, never a partially installed final object. The temporary
name-reuse cleanup race has a dedicated concurrent-writer regression.
`tools/check-objects` covers malformed input, API/checked witnesses, Git interop,
write failures, permissions, races and interruption.

Historical M1 measurements on hasu, three whole-object release runs per input
with the first excluded, gave peak RSS at 100,000,000 bytes: random write/read
**787,892/655,276 KiB**; zero write/read **461,368/426,968 KiB**. Doubling 50 MB to
100 MB stayed below 2.7x for each path. `tools/objects-bench.py` and
`notes/vc02-evidence/` retain those measurements; they are not a new benchmark
for the current changes or a streaming/large-object checked claim.

## Zlib codec

`src/zlib` is an original RFC 1950/1951 implementation, with no external codec
in the executable. Inflate supports stored, fixed and dynamic Huffman blocks,
32-KiB cross-block history and overlapping matches. It checks framing, trees,
backreferences and Adler-32, reports consumed bytes through the checksum, and
leaves the following stream untouched. Preset dictionaries are refused.

The public API is `inflate`, `inflate_raw`, `deflate`, `deflate_raw`, `adler32`,
`Inflated`, `InflateErrors` and `DeflateErrors`. `List[byte]` carries binary data.
Limits are inclusive: exact-cap output succeeds, another byte returns `limit`;
negative limits return `invalid`. Returned bytes own their storage. Errors are
rows, never intended traps on malformed input.

Encoding supports **0** (stored) and **1** (bounded lazy LZ77, stored/fixed/dynamic
block selection); **-1** selects 1. Every other level returns `unsupported_level`.
The object store accepts `core.compression` and `core.looseCompression` only
at 1 or -1. Levels 0/6/9 have exact named not-yet matrix rows; pack settings
remain outside this loose-only implementation.
The whole-object API is not a streaming pack reader.

The historical M1 codec gate covered 52 independent small vectors, all lengths 3–258 and
every distance range through 32768, native/release cross-tests, four actual
checked programs, 1,067 loose objects and 31 packed entries, and 1,098 den-written
objects read by Git. Nine rebuilt repositories pass Git fsck. Corpus encoded-size
ratios against Git level 1 range from 0.9959 to 1.0068; the 1.25 ceiling is gated.
Each native tier runs 250 deterministic fuzz rounds (1,250 calls); every
malformed result must be a named row. The Adler CI plant failed as intended
in run 40133795581 (closed-unmerged PR #3).

Historical M1 measurements on hasu, three 100,000,000-byte file-driver runs with the first excluded:

| Release operation | Random bytes | Repeated zeroes |
|---|---:|---:|
| Encode throughput | 29.25 MB/s | 157.47 MB/s |
| Decode throughput | 67.04 MB/s | 77.57 MB/s |
| Encoded bytes | 100,015,266 | 138,484 |
| Ratio to zlib level 1 | 0.99985 | 0.31735 |
| Peak encoder RSS | 427,792 KiB | 197,476 KiB |
| Peak decoder RSS | 426,292 KiB | 328,852 KiB |

These are whole-object file read/codec/write measurements, not isolated CPU or
disk benchmarks. `tools/codec-bench.py` reproduces them; raw runs, hashes and
predictions are under `notes/vc01-evidence/`. Those small checked programs passed;
100-MB file measurements were native-only. These are retained measurements,
not a new performance result for the current changes.

## Measured platform gaps

The full stat record supplies every index word. TCP and subprocess pipes were
observed on native and the actual checked machine. Since the standard library's
public-PKI client (RSA, RSA-PSS, ECDSA P-256/P-384 and path validation to a
root set), HTTPS completes against github.com with a distribution's roots; the
checked machine runs den's HTTP parsers, not a handshake. Non-UTF-8 OS paths, non-creating writable opens,
regex and mmap have the specific limitations listed in MAP; argv[0] is
available since wolf 0.2.36 and den does not read it yet.

The combined index checked unit also exceeds the pinned mem-phase budget.
Five smaller checked probes cover format, flags, trees, malformed input and
stat mapping; all five returned actual-checked `exit(0)` in the full gate. This does
not turn the combined program's `unsupported` verdict into a pass. A retained
compiler reproducer tracks the returned lent-byte-view copy issue separately.

## CI and packaging

Unlabelled pull requests run one cheap job that reports the local-evidence
gate. The `ci` or `full-matrix` label runs the full set: Linux and the
nonblocking macOS field observation. Trunk pushes run that set only when
workflows, CI, shared tools, pins or other cross-cutting paths change;
module-only pushes run no CI. The nightly and default dispatch still run
the full set. `ci/tiers-test.py` checks planning and final verdicts, and a
failed nightly opens or updates a `nightly-red` issue. Portable implementation
measurements use Linux containers. The separate live SSH leg builds on macOS
arm64 and interoperates with pinned Git on kasumi.

`packaging/den.rb` and `packaging/PKGBUILD` remain **drafts, not published**.
They name a future v0.1.0 tag and have an unfilled source-archive digest. Do not
install or upload them as a release. Neither replaces the system Git or installs
a `git` alias.

## Clean room

Implementation work uses Git's documentation, published specifications and
black-box oracle runs, never Git source, sample hooks/templates, libgit2 or
another VCS implementation's code. [SOURCES](docs/SOURCES.md) lists references.
A documented behavior that disagrees with the binary is recorded with its
reproducer; an unimplemented feature is not silently approximated.

## Licence

GPL-3.0-only (`LICENSE`) with the wolf Training Data Permission
(`LICENSE-TRAINING-DATA`). Vendored organisation-owned files retain provenance.
