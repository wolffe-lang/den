# den

A version control system in [wolf](https://github.com/wolffe-lang/wolf-lang),
working toward Git-compatible repositories and wire protocols. Where a wolf
keeps what it has.

**State: loose objects, a writable index, worktree/commit commands, bounded diff, history, refs and merges.**
This is not a replacement for Git; M2 and M3 remain incomplete. Log/show support
bounded loose history; branches, tags, branch switching and resets share
loose/packed ref storage. Merge and single-commit revert now cover the measured
regular-file subset below. Combined merge display, rebase, packs
and transports remain unfinished. Text diff has
two recorded equal-cost alignment differences; binary patches reconstruct the
exact blobs but do not always use Git's byte representation. `den --version`
prints `den 0.0.0 (built with wolf 0.2.35)`.
See [MAP](docs/MAP.md) for API contracts and [FORMATS](docs/FORMATS.md) for
measured bytes and documentation discrepancies.

## Machines and pins

| Role | Machine / identity |
|---|---|
| Behavioral oracle | Git 2.56.0, signed kernel.org tarball; default build, Ubuntu 24.04 image pinned by digest |
| Development witnesses | hasu CPUs 0–5 for objects/index/worktree/commit and 6–11 for diff; kasumi CPUs 12–15 for the initial surface census; Linux x86-64, rootless container under a core-block lock |
| CI PR gate | ubuntu-24.04, pinned container and oracle, including planner tests |
| CI full field leg | macOS arm64 with Homebrew Git; nonblocking observation, not the oracle |
| Toolchain | wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4 (binary embeds 294d626), bundled std 2386522e |

Archive and oracle pins are in `wolf-toolchain.toml` and `den-oracle.toml`.
Downloads fail on a digest mismatch. Both release-metadata reads are retained
in `notes/vc07-evidence/pins/` (earlier reads in `notes/vc06-evidence/pins/`); the original signature verification and two matching
oracle builds are in `notes/vc00-evidence/`.

## Commands implemented so far

| Area | Commands and supported surface |
|---|---|
| Objects | `init`, `hash-object`, `cat-file -p/-t/-s`, `mktree`, `commit-tree`, `mktag` |
| Index | `write-tree` over nested index v2/v3/v4 entries; exclusive `index.lock` writes, stat fields, flags and TREE cache updates |
| Config / ignore | Read-only `config --get`; `check-ignore` with provenance, negation, tracked-file bypass and `--no-index` |
| Worktree | `add` paths/directories, `-A`, `-u`, `--ignore-removal`, `-f`, `-N`, `--chmod`; `rm`, `mv` and their implemented safety/force/recursive options |
| Status | Human, short and porcelain v1, branch/unborn/detached headings, NUL output, untracked grouping and ignored paths |
| Commit | Ordered `-m`, `-F`, `-a`, `--amend`, `--reset-author`, `--author`, fixed `--date`, cleanup modes, quiet and allow-empty options; attached/detached HEAD and loose-over-packed branch updates |
| Diff | Worktree/index, `--cached`, two loose commits/trees or blobs; unified context, final-newline markers, modes, binary patches, stat/name forms, rename/copy detection and common pathspec magic |
| History | `log` default/oneline/short/full/fuller, `-n`, `--skip`, `--reverse`, `--first-parent`, fixed date formats, patch/stat; `show` loose commits, trees, blobs, annotated tags and `REV:path` |
| Restore | Index-to-worktree `restore`, `--staged`, `--worktree`, `--source`; `checkout -- <paths>` |
| Refs | Loose and packed refs with peeled tag records; branch list/create/force/delete/rename, lightweight and message-supplied annotated tags, command reflogs |
| Branch worktree | `switch` and branch `checkout`, `-c`/`-b` creation, explicit and implicit detached HEAD, dirty-worktree protection; `reset --soft/--mixed/--hard` |
| Merge | Fast-forward, already-up-to-date, bounded regular-file three-way merges, conflict stages and merge/diff3/zdiff3 markers; `--no-ff`, `--ff-only`, `--squash`, `--no-commit`, `--no-edit`, `-m`, `-F`, `--abort` |
| Revert / resolution | Single ordinary or root commit, `--no-edit`, `--no-commit`; merge-parent refusal; `add` saves REUC when resolving/deleting higher stages, and `commit` completes a resolved merge |

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
tools/check-history
tools/check-refs
tools/check-merge
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

The expanded main matrix contains 188 cases: 174 parity, 13 named not-yet and
one version-shape check. Generated diff, similarity, pairing and application
matrices are reported separately in `notes/vc04-evidence/`; their explicit
representation/alignment differences are never added to the parity count.
History has a separate exact command/state matrix on native and release,
bounded actual-checked units and an independent package client. The inherited
diff exceptions remain separately counted. CI remains the merge gate, not a
consequence of a successful local run.
There is no production dependency on Git, Python, zlib or OpenSSL. Shipped wolf
code uses wolf-std and the provenance-marked SHA-1 code from boreutils.

## Corpus and comparison rules

The corpus now defines 16 repositories: the original nine object/history
fixtures plus ignore, staged rename, modes/symlink, unborn, amend, index-v4 and
edited-rename states. `tests/cases.json` currently defines 188 main cases.
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

The store reads/writes loose SHA-1 repositories only. Binary object/tree names
are preserved, but filesystem path arguments remain UTF-8 `str`; raw non-UTF-8
OS paths have named upstream limitations. SHA-256 IDs are representable, but
SHA-256 repositories are refused before writes. Packs, alternates, linked
worktrees, submodules and general revision expressions remain unsupported.
Diff accepts loose names/IDs and bounded `^n`/`~n` ancestry; this is not a general
revision grammar. Log adds a timestamp-ordered reachable-commit walk, with
stable parent-order ties, duplicate suppression and a first-parent option.

TREE and REUC index extensions are validated and preserved. UNTR, FSMN, IEOT,
EOIE, split-index `link`, sparse-index `sdir` and unknown extensions are refused
by name. Higher merge-stage entries can be read and written. Resolving or deleting
them through `add` records the original stages in REUC; unrelated higher-stage
`rm`/`mv`/restore operations remain refused.

Config parsing handles quoting, escapes, continuation and precedence, but
`include`/`includeIf` are named refusals. There is no config writer; the command is
read-only `config --get`. Diff implements literal, top, icase, glob and exclude
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
explicit node budget. It is a bounded whole-history reader, not a pack walker.

Default `log -p` omits merge patches as Git does. Combined merge `show` is a
named refusal; `show -s` renders its ordered parents and message. Show-specific
revision limiting, history path simplification, ranges, graph/topological order,
custom formats, relative/human dates, non-UTC local zones, message transcoding,
mailmaps and tabs after non-ASCII text remain named unsupported surfaces.
Fixed dates include default, short, raw, unix, ISO, strict ISO and RFC forms;
UTC-local variants are measured. None of these limitations is a parity pass.

The refs gate separately compares 434 command/state rows per native tier,
with eight named unsupported cases kept outside that count, fourteen independent
client checks, and two bounded actual-checked programs. It compares command
output, exit status, objects, HEAD, loose/packed refs, reflogs, index and worktree
state on native and release.
Branch/tag listing patterns, tracking configuration, overlapping rename paths,
merge-mode checkout, orphan branches and general revision grammar stay outside
this bounded surface. Explicit unsupported cases are counted separately.

Ref commands accept HEAD, full ref names, short branch/tag names, full OIDs and
unambiguous loose-object prefixes. They do not add ancestry, ranges, reflog
selectors or previous-checkout syntax. Packed files are bounded at 16 MiB and
100,000 records; a listing is bounded at 4,096 entries. Tree transitions refuse
higher-stage or flagged index entries and submodules rather than losing their
metadata. `switch` protects in-progress operations; `reset --soft` refuses an
in-progress merge. Reflog management/expiry commands remain future work.

The merge gate separately measures **104 exact command/state cases**, **12
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
`--continue`/`--skip` and revert abort are not implemented. Merge editor execution,
combined merge show and the previously named history limits remain open.

Commit writes support attached and detached HEAD. Loose refs override packed
records; an unchanged packed tip is not needlessly unpacked. Amend retains
the existing parents and normally its author; it does not change ORIG_HEAD.
Index/ref/reflog publication is not a multi-file atomic transaction. An ordinary
commit can refresh the index before a message/editor abort, whereas `commit -a`
keeps its prepared index unpublished until ref publication succeeds. FORMATS
records these lifecycle differences and the possible earlier object/message
side effects. Unsupported-command refusals must not be confused with rollback
of every ordinary commit failure.

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
observed on native and the actual checked machine. TLS completed a local
Ed25519 handshake, but the tested RSA/GitHub chain returned `unsupported_alg`;
the checked TLS program exhausted its mem-phase budget before a handshake.
HTTPS remains deferred. Non-UTF-8 OS paths, non-creating writable opens,
argv[0] at this pin, regex and mmap have the specific limitations listed in MAP.

The combined index checked unit also exceeds the pinned mem-phase budget.
Five smaller checked probes cover format, flags, trees, malformed input and
stat mapping; all five returned actual-checked `exit(0)` in the full gate. This does
not turn the combined program's `unsupported` verdict into a pass. A retained
compiler reproducer tracks the returned lent-byte-view copy issue separately.

## CI and packaging

`plan` selects PR/full/noop/partial tiers; `ci/tiers-test.py` checks planning and
final verdicts. PRs run Linux; trunk/nightly/dispatch and `full-matrix` add the
nonblocking macOS field observation. A failed nightly opens/updates a
`nightly-red` issue. Local implementation measurements use Linux containers,
not Mac builds.

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
