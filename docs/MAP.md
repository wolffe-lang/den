# Map

The codec, owned OIDs, bounded loose/packed store and binary parsers underpin the
index/worktree/commit interface and diff. The dispatcher routes the implemented
porcelain, plumbing, diff, bounded log/show, ref commands, merge/revert and replay.
Combined merge show, recursive/complex merges, full replay semantics, pack writing and transports
remain separate work; M2 and M3 are not complete. Diff's known hunk
alignment differences and binary representation exceptions are explicit below,
not a blanket byte-parity claim.

## Modules and lanes

| Milestone | Modules and scope |
|---|---|
| M0 | CLI refusal scaffold, `hash`, probes, oracle/corpus/review harness (vc00) |
| M1 | `zlib`: inflate then deflate, Adler-32 (vc01); `oid`, `object`, `repository`, init/hash-object/cat-file/tree/commit/tag plumbing (vc02) |
| M2 (partial) | `index`, `worktree`, `ignore`, `commit_format`, `commit`: implemented subset (vc03); `delta`, `rename`, `difftext`, `diffbinary`, `diff` (vc04); `walk`, `pretty`, log/show (vc05) |
| M3 (partial) | `refs`, `refcmd`, `worktree.transition`: refs/reflogs, branch/tag/switch/checkout/reset (vc06); three-way merge/revert (vc07); rebase/cherry-pick/sequencer (vc08); blame (later); stash/notes/revision grammar (vc10) |
| M4 (partial) | `pack`: pack-v2/idx-v2 reads and delta decoding (vc09); pack writing, gc/repack/fsck/count-objects (later) |
| M5 | `pktline`, protocol v2 fetch (vc13); receive-pack push/remotes (vc14); clone/pull porcelain (vc15) |
| M6 | static build and PAX handoff (vc16, then px lane); optional `git` alias |
| Later | HTTPS beyond measured TLS profile, hooks, worktrees, sparse index, submodules, SHA-256 repositories, interactive rebase, bundles and protocol v0/v1 fetch |

The MVP is M0–M3, file/git transports from M5, and M6. Pack reading is available
beneath object lookup; pack writing and transports remain separately staged.
OID design keeps an algorithm and a byte list from the start, never a fixed
20-byte public type. SHA-256 is available in the hash adapter already.

## Surfaces

The original surface census was measured on wolf 0.2.35 (`cf0c13d3`), bundled
std `2386522e`, Ubuntu 24.04 on kasumi CPUs 12–15. M1/M2 implementation
measurements use hasu CPUs 0–5; diff uses CPUs 6–11 with the same pinned toolchain/container. “Checked” below means the observation's
`verdict` from `wolf conform-run --checked --json`, never its process status
(which is 0 even for a static rejection). Full logs are tracked under
`notes/vc00-evidence/probes/`.

| Need | Exact surface; measured verdict | Witness / disposition |
|---|---|---|
| SHA-1 / SHA-256 | `hash.new1/update1/final1/sum1`, SHA-1 rounds from boreutils; `std.x.crypto.sha2.sum256`, exposed as `hash.sum256` | `hash`, `src/hash_test.lu`: empty, abc and 56-byte standard answers plus five streaming splits on native + checked; provenance correction R-vc00-1 |
| zlib inflate/deflate | `src/zlib`: original RFC 1950/1951 codec, levels 0/1/-1 | Four checked programs pass; native/release independent zlib and Git interop. No `std.compress` dependency or FFI |
| Files / metadata | `fs_fstat_record` returns all 20 words, with `have=1048575` here. ctime_s/ns [16/17], mtime_s/ns [14/15], dev [9], ino [10], mode [4], uid [6], gid [7], size [1] | `stat`: native + checked. mtime exactly 1700000001.987654321; size 6. Mode is permission bits only: construct Git's type bits from kind. Index words truncate to 32 bits, without a trapping signed cast |
| File operations | `std.fs.create_new_with_mode`, `move_file`, `sync`, `sync_dir`, `symlink`, `read_link`, `lstat`, `realpath`, `entries`; builtin `fs_lock/unlock` | `files`: native + checked, exclusive creation, sync/rename, lock/unlock and symlink round trip. Unix advisory locks are not Git's `.lock`-file protocol; use exclusive create for that |
| Write-only non-truncating open | Absent: modes 0/5 read only, 1 truncates, 2 appends, 3 reads+writes, 4 exclusive-create; 6/7 invalid | `open`: native + checked. Existing wolf-lang#908 covers the missing non-creating writable modes; #684 is st_blksize and #706 is rename-no-replace, not this API. Do not describe mode 3 as write-only. No new duplicate issue proposed |
| Non-UTF-8 paths | `std.fs.entries`/read_link preserve bytes, but path arguments are `str`; `str_from_utf8([255])` raises utf8 | `paths`: native + checked. wolf-lang#687/#912. Partial surface, not a byte-path API; unsupported input remains named, never silently transcoded |
| Processes / pipes | `os_pipe`, `os_spawn_fds`, `os_wait`; std.process's pipe, set_stdin/set_stdout/start/wait wrappers | `process`: native + checked, bytes “both ways”, wait 7; no host process targeted. Spawn helper is lane-owned shell text |
| TCP | `std.net.connect/listen_with/port/accept/read_bytes/write_bytes/set_deadline/close` (`listen` is the simple wrapper) | `tcp`: native + checked, loopback ephemeral port, binary 00 ff 0a round trip in both directions |
| TLS | `std.x.tls.client.begin/complete/read/write/close`, explicit concatenated DER roots and caller entropy; TLS 1.3 ChaCha20/X25519 profile | `tls`: native local OpenSSL handshake + 3,853 application bytes; GitHub:443 returns unsupported_alg with system roots. Actual checked verdict is unsupported (step budget exhausted during mem), not a handshake. No blanket “TLS absent” claim |
| Dates | `std.time.local`, `std.time.format` (both files are one module), format `%a %b %e %H:%M:%S %Y %z` | `time`: native + checked: Tue Nov 14 22:13:20 2023 +0000. Offset is explicit; zone names not inferred |
| Terminal / pager | `os_isatty`, `std.term.group`; term mode/size APIs exist | `term`: native + checked under redirected streams; pinned pager is cat, colour off. No interactive TTY session claimed |
| Regex | No `std.regex` | `regex`: E0301 native + checked; existing wolf-std#99. Vendor scent only when log --grep/-G needs it |
| Globs | No `std.glob` | `glob`: E0301 native + checked; implement Git ignore/pathspec grammar in den, not a new generic dependency |
| Big integers | No `std.bigint`; not needed by den | `bigint`: E0301 native + checked, existing wolf-std#100 |
| Large packs / memory | `fs_read_at`, `fs_seek`, per-window region reclamation; no `fs_mmap` builtin | `read-at`: native + checked scan 100,000,000-byte sparse file in 64-KiB windows. Native repeated reads after warm-up: 8,339,710 and 8,495,314 ns, median 8,417,512 ns; RSS 2,588–2,652 KiB (`gauntlet-8.log`). Sparse, warm-page-cache read, not a disk benchmark. `mmap`: E0301 on both. Use a bounded window cache, not whole-pack reads |
| argv[0] | No `env_arg0` in 0.2.35 | `argv0`: E0301 native + checked. wolf-lang#904 is merged but unreleased; revisit the git alias when the pin moves |
| C ABI / muzzle | No dependency: den is a hosted/static wolf executable over wolf-std | `muzzle` probe; README and LEDGER read. A future C-facing libden needs the C ABI membrane and an explicit allocator/ownership convention (malloc/free for caller-owned results), not muzzle as a VCS dependency |

No stat nanosecond gap was found; the prediction was wrong. std.fs.fstat is
only the older three-field wrapper; using its name instead of the full
builtin would throw away available information. The table deliberately
separates standard-library wrappers from language builtins.

### Gaps to send upstream (not filed by this lane)

- wolf-std: the TLS client cannot complete the observed GitHub chain;
  `tls-github-native.log` returns `complete=unsupported_alg`, with explicit
  system roots. The deterministic local RSA-signed certificate reproduces
  `complete=unsupported_alg` (`tls-local-rsa-native.log`); an Ed25519 local
  certificate succeeds against the same native client. Existing tests cover the
  narrower supported profile; HTTPS remains deferred, not absent forever.
- wolf-lang: compiling the TLS probe for the actual checked machine exhausts
  the mem-phase step budget before any handshake; both local and GitHub
  checked logs witness this. Consider a way to set the budget for this
  library-sized program; do not substitute `wolf run --checked` (native).
- Existing gaps remain #908 (open), #706 (rename-no-replace), #684 (st_blksize; not needed by index v2), #687/#912 (paths), #904 (argv[0]),
  wolf-std#99 (regex), #100 (big integers). zlib and Git globs are den work,
  not requests for unrelated standard-library features.

## Zlib component boundary

Implemented in `src/zlib/{inflate,deflate,huffman}.lu`. Public API:

```wolf
pub error InflateErrors = {truncated, bad_header, dictionary, checksum, invalid, limit}
pub error DeflateErrors = {invalid, unsupported_level, limit}
pub struct Inflated { data: List[byte], consumed: int }
pub fn inflate(src: List[byte], max_output: int) -> Inflated ! InflateErrors
pub fn inflate_raw(src: List[byte], max_output: int) -> Inflated ! InflateErrors
pub fn deflate(src: List[byte], level: int, max_output: int) -> List[byte] ! DeflateErrors
pub fn deflate_raw(src: List[byte], level: int, max_output: int) -> List[byte] ! DeflateErrors
pub fn adler32(src: List[byte]) -> int
```

The encoder's three-tag row has a public name to satisfy W0602 at the pinned
compiler; its set is unchanged from the adopted API. Limits are inclusive
(adopted R-vc01-1 A): output exactly at the cap succeeds; another byte
is `limit`; a negative cap is `invalid`. Input is read-only, output owns its
storage, and no source list is retained. `consumed` counts bytes, including
partial final-byte padding and, for `inflate`, the framing/checksum. Raw
inflate excludes framing. A caller advances by consumed, never by output size.

Inflate validates CM=8, CINFO<=7, FCHECK, FDICT and Adler; distance is bounded
by the advertised window. Stored/fixed/dynamic blocks share prior history.
Tree space accounting rejects oversubscription and incomplete trees except
the RFC's one-bit single data symbol and empty distance alphabet. Empty
distance codes cannot be used for matches. All source bounds are checked.

Level 0 uses stored blocks. -1/1 uses a 32-KiB window, hash chains capped at
32 candidates, one-byte lazy lookahead, and exact bit-cost selection among
stored/fixed/dynamic output per 32-KiB block. Prefix lengths come from repeated
lightest-node joins; positive weights are rounded up and halved if a depth
exceeds the format bound, so construction terminates without recursion.
Measured release lazy/greedy output is identical on the 10.2-MB repeated-text
and 6.0-MB phrase datasets; lazy takes 0.1215 s versus 0.1017 s on phrases.
On the 8,000-byte lookahead witness, lazy emits 6,207 bytes versus greedy's
6,610. The matching unit test exercises that decision explicitly; these
measurements justify the policy, not a claim that lazy always improves output.
Block/matcher scratch uses bounded regions; input/output are whole-object
allocations. No pack-streaming claim. Other levels return `unsupported_level`.

52 independent vectors and native/release range tests cover malformed input,
checksums, levels, cap boundaries and consumed offsets. Four actual checked
programs pass with zero unsupported rows. Every corpus loose object (1,067)
and packed entry (31) is inflated, its reconstructed SHA-1 compared with Git,
and all 1,098 objects are rewritten with den and read/fsck'd by Git. The nine
corpus ratios are <=1.0068, below the 1.25 stop. Fixed-only output exceeded the
bar on repeated-zero/text fixtures; preserved evidence drove dynamic selection.
README has measured 100-MB throughput/memory; evidence holds every raw run.

vc02 uses `deflate(raw, 1, cap)`, validates its own object header, and refuses
other compression levels by name until implemented. It must check the raw
object oid independently of the codec's Adler check. No API signature change
is needed beyond referring to the equivalent `DeflateErrors` alias.

### Settled M0 decisions

- R-vc00-1: SHA-1 provenance is boreutils b603bb8 as formatted at f87dc76.
- R-vc00-2: loose streams compare by raw bytes/oid and valid interoperable
  compression, with measured sizes. Other on-disk artifacts stay exact.
- R-vc00-3: fetch/ls-refs use protocol v2; push uses receive-pack framing.

## Harness, evidence and CI

`tools/corpus` defines 16 repositories: the original nine object/history
fixtures plus ignore, staged rename, modes/symlink, unborn, amend, index-v4 and
edited-rename states. The original nine builders remain unchanged. The two
independent corpus builds compare OID manifests, not inode-dependent stat data.
`tests/cases.json` defines 190 main cases; its latest measured main comparison
is 176 parity / 13 named not-yet / 1 version-shape / 0 reviewed / 0 failures.
Implemented diff and edited-rename cases require parity and cannot regress to
a named refusal unnoticed. Generated component matrices remain separately
counted. Historical vc03 counts and 636 stat-proof rows are retained in
`notes/vc03-evidence/final-counts.json`; current gate evidence is under
`notes/vc04-evidence/` and the CI artifact's `target/runs/vc04-evidence/`.

`tools/oracle --filter TEXT` rejects an empty selection; `--strict` rejects
named not-yet results. The normal gate distinguishes those from parity and
shape checks. A reviewed difference binds its case hash, complete stdout,
stderr, status and repository-byte map to a specific reason/issue; no wildcard
or excluded repository path is permitted. The loose-object comparison checks
raw bytes/OIDs and valid bounded compression, retaining compressed captures.
Other bytes and modes remain exact except the six proven index-stat words
described below. Optional read-only index refresh is disabled by the pinned
environment. Empty hook/template fixtures contain no sample scripts.

Recorded earlier witnesses are not the final expanded verification:

| Component | Earlier recorded coverage | Current gate |
|---|---|---|
| Worktree | 186 command cases per native/release tier and an actual checked unit exit | `tools/check-worktree`: units, external client and full repository snapshots |
| Ignore | 840 pattern rows per native/release tier and actual checked unit exit; 479 filesystem rows on native | `tools/check-ignore` plus `tools/ignore-filesystem-oracle.py`: precedence, tracked/prefix bypass, relative sources, warnings and no-write checks |
| Commit | 51 native full-repository comparisons after the initial fixes | `tools/check-commit`: CLI state, failure/ref tests and actual checked units |
| Commit formatting | 150 API comparisons | Date/identity/message outputs; **not** 150 CLI stdout/stderr/status parity cases |

The current gates have expanded since those measurements. The combined index
checked-budget refusal and the new bounded stat probe are tracked separately
below. Native/release failures and explicit unsupported rows are never counted
as checked passes.

CI selects PR/full/noop/partial tiers, tests its own planner, and adds the
nonblocking macOS Homebrew-Git field leg at the full tier. Local heavy work
runs under the assigned core-block flock with taskset inside a 12-GiB container.
The complete gate also retains codec/object interop, race/interruption tests,
format checking, corpus reproducibility and the static archive checks.

### Toolchain input identity

`wolf-toolchain.toml` and `den-oracle.toml` retain archive, source and container
pins. The two metadata reads in
`notes/vc03-evidence/{wolf,lupin}-release-read-{1,2}.json` agree on asset IDs,
names and digests. These are input identities, not test verdicts.

| Linux x86-64 archive | Release asset ID | SHA-256 |
|---|---:|---|
| wolf 0.2.35 | 668511628 | `4cc4045bbbb605c07835bc4f32685953c784eeef4cd3139a48b457dfc90dad1a` |
| lupin 0.1.56 | 667986244 | `ad703550ac4787e8e4bb26989d591a731410274d7332f2b4e8b9a64c878822cc` |

The oracle executable is Git 2.56.0, SHA-256
`c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60`.
The wolf archive includes its runtime archive and std tree; do not replace it
with an unstamped plain build. Lupin's tag revision and embedded revision differ
as recorded in the pin file.

## Object API for index/porcelain consumers

`probes/object-client` is an independent package importing the public modules;
its native and release runs exercise real reads, writes, limits and errors.
All byte lists returned by these APIs own their storage. `read` inputs are
not retained. Public Oid fields must still pass validation at every boundary.

```wolf
pub struct Oid { algorithm: str, bytes: List[byte] }
pub fn oid.parse(algorithm: str, text: str) -> Oid ! OidErrors
pub fn oid.from_bytes(algorithm: str, bytes: List[byte]) -> Oid ! OidErrors
pub fn oid.hex(id: Oid) -> str ! OidErrors
pub fn oid.prefix(algorithm: str, text: str) -> str ! OidErrors
pub fn oid.digest(algorithm: str, data: List[byte]) -> Oid ! {unsupported_format}
pub struct Repo { gitdir: str, config: Map[str, str] }
pub fn repository.open(gitdir: str) -> Repo ! RepoErrors
pub fn repository.discover(start: str) -> Repo ! RepoErrors
pub fn repository.init(path: str, bare: bool, branch: str) -> (Repo, bool) ! RepoErrors
pub struct Object { kind: str, data: List[byte] }
pub fn object.identify(kind: str, data: List[byte]) -> Oid ! {bad_header}
pub fn object.read_object(repo: Repo, id: Oid, max_output: int) -> Object ! StoreErrors
pub fn object.write_object(repo: Repo, kind: str, data: List[byte]) -> Oid ! StoreErrors
pub fn object.lookup(repo: Repo, name: str) -> Oid ! StoreErrors
pub fn object.resolve(repo: Repo, name: str) -> Oid ! StoreErrors
pub struct TreeEntry { mode: int, name: List[byte], id: Oid }
pub fn object.parse_tree(data: List[byte], algorithm: str) -> List[TreeEntry] ! TreeErrors
pub fn object.build_tree(entries: List[TreeEntry], algorithm: str) -> List[byte] ! TreeErrors
pub struct Header { key: str, value: List[byte] }
pub struct Headers { fields: List[Header], message: List[byte] }
pub fn object.parse_headers(data: List[byte]) -> Headers ! {invalid_header}
pub fn object.build_headers(headers: Headers) -> List[byte] ! {invalid_header}
pub fn object.parse_commit(data: List[byte], algorithm: str) -> Headers ! HeaderErrors
pub fn object.parse_tag(data: List[byte], algorithm: str) -> Headers ! HeaderErrors
pub fn object.build_commit(tree: Oid, parents: List[Oid], author: str,
    committer: str, encoding: str, message: List[byte]) -> List[byte] ! HeaderErrors
pub fn object.build_tag(id: Oid, kind: str, name: str, tagger: str,
    message: List[byte]) -> List[byte] ! HeaderErrors
pub fn index.parse_v2(data: List[byte]) -> List[TreeEntry] ! IndexErrors
pub fn index.write_tree(repo: Repo, cap: int) -> Oid ! IndexErrors
```

Names above are qualified for the reader; actual declarations use the unqualified
function names in their modules. OidErrors is invalid_oid/unsupported_format.
StoreErrors enumerates framing, checksum, oid, cap, missing/ambiguous and IO rows;
`Unsupported(str)` names unsupported repository/configuration features. Exact
aliases live beside the declarations. `max_output` is inclusive body bytes;
read_object currently caps it at 1,000,000,000, plus bounded compressed overhead.
The pure decoder independently checks consumption, raw header, size and oid.

Installation uses std.fs.link's no-replace guarantee, not replace-capable rename
or an advisory lock. Concurrent writers validate the winner; ordinary errors
remove the exclusive temporary. Abrupt termination leaves a possible orphan
`tmp_den_*`, never a partial object installed under its oid. Directory fsync is
required; unsupported platforms return a row instead of claiming durability.
`write_injected` is an explicit test seam (write/sync/install/directory-sync),
never selected by a production environment variable.

These object APIs remain available to the index and porcelain modules.
`parse_v2` is a legacy flat-v2 compatibility reader, not the interface for new
nested consumers. `index.write_tree` now writes nested trees and refreshes TREE
under index.lock. Generic headers/messages remain byte-lossless; UTF-8 repair
belongs only at commit creation command edges. Configuration and deterministic
date/message parsing have their own APIs below; no general revision grammar or
production Git/shell dependency has been introduced.

## Packed storage boundary (vc09)

`pack.Body {kind, data}` is owned. `read_object(gitdir, full_name, cap)` and
`prefix(gitdir, prefix)` are the adapter's pack-side operations; callers should
normally use `object.read_object` and `object.lookup`. `prefix` returns at most
two distinct matching names, sufficient to determine ambiguity. No zero or
negative offset is an absence sentinel in the file format. Internal map misses
are checked before addressing entries.

The idx-v2 parser validates SHA-1, exact length, fan-out counts against sorted
unique names, 32-bit offsets and referenced 64-bit slots. Packs require version
2, matching counts, distinct in-range offsets and first entry at byte 12. A
streaming SHA-1 validates the complete pack and its binding to the index. Entry
reads validate CRC-32 over header/reference/zlib bytes, exact inflated size and
consumption, then the reconstructed canonical object OID. OFS references must
land on an indexed earlier boundary; REF references stay inside the same pack,
including forward bases. Thin references and cycles fail by name.

`pack.apply_delta(base, instructions, cap)` is a pure owned-output API with
`DeltaErrors = {invalid, limit}`. It validates both variable-length sizes,
optional little-endian copy fields, zero copy-size meaning 65,536, nonzero insert
opcodes, base ranges and exact target size. `pack.crc32(bytes)` implements the
reflected IEEE/zlib polynomial. These small boundaries have an actual-checked
program; full filesystem pack scans are native/release witnesses, not checked
memory measurements.

File reads and pack hashing use reclaimed 64-KiB offset windows. Index bytes are
bounded at 16 MiB/400,000 entries; compressed entries at 17,000,000 bytes;
inflated entries and bodies at 16 MiB. Reconstruction charges cumulative encoded,
inflated and target sizes against 128 MiB and allows 64 delta links. These are
payload accounting bounds, not peak-RSS guarantees: owned copies and codec
scratch add memory. Directory scanning caps 8,192 entries and 256 pack indexes.
There is no persistent verification cache: candidate pack checksums are scanned
again on each lookup. A missing companion, unsupported format, corrupt data or
limit is a named `Unsupported` error; only a genuine object miss is `not_found`.

Loose objects retain precedence. Prefixes merge loose and packed identities,
including duplicates across packs. Writers verify and reuse an already-packed
object instead of adding a duplicate loose file. `.keep` files do not hide packs;
`.rev` and `.mtimes` sidecars are unnecessary for these reads. Multi-pack-index
and bitmaps refuse by name. No pack writer, protocol/thin-pack support or new
revision grammar is exposed.

The mandatory `tools/check-pack` independently writes valid/corrupt structures,
reads every oracle-listed object from 34 fixtures (2,442 object comparisons per
native tier), requires all six packed entry types, and checks Git fsck/verify-pack.
The history/refs/merge/replay matrices also run against packed clones, retaining
every file and each inherited refusal. Packing checks the object namespace in
both directions, including unreachable objects. Large-offset table decoding is
exercised with small synthetic packs; no multi-gigabyte IO benchmark is claimed.

## Index and ignore consumer API

The index module now owns full v2/v3/v4 records. `Index` contains version,
entries and extensions; `Entry` contains the ten ordered u32 stat words,
algorithm-tagged OID, flags, extended flags and an owned raw byte path.
`parse` checks framing, bounds, checksum, names/stages/order, padding and
extensions. `serialize` preserves selected v3, while `serialize_for_write`
implements Git's v2/v3 downgrade/upgrade policy. Version 4 remains version 4.
The legacy `parse_v2` API keeps its flat stage-zero contract.

`begin(repo, cap, version)` acquires index.lock before reading. An existing
index retains its version regardless of this argument: 0 means default v2 for
a missing index, and 2/3/4 choose only a missing index's initial version. To
convert an existing index, set `tx.value.version` explicitly; the transactional
v2/v3 write policy still applies. This matches `index.version`, not an implicit
conversion on every command. Immediately `defer abort(mut tx)` and never copy a
live transaction.

`prepare(mut tx)` serializes, writes, syncs and closes index.lock without
publishing it. `install(mut tx)` atomically renames that prepared lock to index
and syncs the directory. `commit(mut tx)` combines both; ordinary failures
clean only this transaction's lock. An install directory-sync error means the
complete new index is already visible. Preparation leaves an active owned
transaction with a closed fd; abort can still discard it. The split boundary
lets `commit -a` prepare its index before ref CAS and install only afterward.
No API promises a multi-file atomic commit.

```wolf
pub fn index.begin(repo: repository.Repo, cap: int, version: int) -> Transaction ! IndexErrors
pub fn index.abort(mut tx: Transaction)
pub fn index.prepare(mut tx: Transaction) -> () ! IndexErrors
pub fn index.install(mut tx: Transaction) -> () ! IndexErrors
pub fn index.commit(mut tx: Transaction) -> () ! IndexErrors
```

TREE and REUC
are validated and preserved; UNTR, FSMN, EOIE, IEOT, sdir, link and unknown
extensions refuse by name. `record_undo` saves higher stages in sorted REUC;
`replace_entry` with stage zero and `remove_path` invoke it before dropping
unmerged entries. `conflict_entry` creates validated zero-stat stages 1/2/3.
The `add` consumer resolves conflicts; other mutation consumers retain their
own higher-stage guards until their operation-specific semantics are measured.

`replace_entry`, `remove_path` and `invalidate_tree` maintain sorted entries
and invalidate affected TREE ancestors. `build_trees` returns owned child-first
tree bodies, root OID and TREE bytes. `write_tree` validates referenced objects,
publishes the trees and refreshes TREE under the transaction; it is no longer
a read-only index operation. Intent-to-add entries are omitted from trees,
with invalid ancestor cache records retained. `entry_from_stat`/`fresh_entry`
map a full regular-file record and explicit canonical mode; `entry_from_lstat`
requires actual symlink metadata. Callers own core.fileMode/core.symlinks policy.

The stat comparison canonicalizes **exactly six words**: ctime seconds and
nanoseconds, mtime seconds and nanoseconds, dev and ino. Each word must first
match the corresponding tool's own worktree lstat. Mode, uid, gid and size are
always compared byte for byte between the tools. All ten words remain recorded.
This adopted R-vc03-3 policy handles --chmod without a wildcard or invented
physical-mode proof. `tools/index-proof.py` binds proof rows to entry path,
stage and original stat words; a recomputed checksum cannot excuse corruption.
Original checksums are verified first. Only the canonical comparison copy's
checksum is recomputed after the six proven words are changed.

`ignore.parse` owns rules from binary content. `matches` checks one node;
`evaluate` checks parent exclusions and precedence. `query` takes Repo,
worktree root, canonical relative path and lstat directory status; it is
explicitly untracked, with `query_tracked` providing an explicit tracked bypass.
The result carries matched/source/1-based line/effective pattern/physical
original line/negated/ignored. `format` renders verbose/plain/NUL records;
pattern bytes are raw, while source/operand quoting is controlled separately.
NUL ends the effective pattern on its physical line, not the file. The original
retains BOM/NUL-tail provenance; the effective first-line pattern omits a BOM.

`query_with_warnings(..., mut warnings: List[str])` and
`query_tracked_with_warnings(..., tracked, mut warnings)` append complete
nonfatal diagnostic lines without LF, once per source across a caller's
operation list. They never print, clear existing diagnostics, or follow a
symlink .gitignore. A warning remains available if a later query fails. Silent
compatibility wrappers discard their local warning lists. Tracked bypass and
excluded-parent early stop load no deeper ignore sources and add no such
warnings. Other symlink ancestors are refused. Configured relative global
sources retain their spelling for output but are opened relative to the
explicit worktree root; tilde/default absolute sources are unchanged.

The matcher uses iterative O(pattern-atoms × path-bytes) DP, not recursive
backtracking. Sources are bounded at 16 MiB each; ~user expansion is refused.
Filesystem path inputs remain str-limited, even though matching is binary.

```wolf
pub fn ignore.query_with_warnings(repo: repository.Repo, worktree: str, path: str,
    is_dir: bool, mut warnings: List[str]) -> Match ! IgnoreErrors
pub fn ignore.query_tracked_with_warnings(repo: repository.Repo, worktree: str,
    path: str, is_dir: bool, tracked: bool, mut warnings: List[str]) -> Match ! IgnoreErrors
```

Independent packages exercise these boundaries in probes/index-client,
probes/ignore-client, probes/worktree-client, probes/commit-format-client and
probes/commit-client. Follow-on consumer requirements are listed below; these
APIs do not implement revision walking or every index extension.

## Worktree and commit consumer APIs

`Context {repo, root, cwd, prefix}` distinguishes the worktree root from gitdir
and command cwd. `discover` handles gitfiles, explicit GIT_DIR/GIT_WORK_TREE and
core.worktree, but refuses bare-worktree commands and GIT_INDEX_FILE. Paths
are owned root-relative bytes after normalization; ordinary porcelain pathspec
magic/globs remain named refusals. `check-ignore` uses literal normalization,
so metacharacters in an operand do not become wildcard selections.

`FlatEntry {path, mode, id}`, `FileState {path, mode, id, data, stat, kind}`,
`StatusRow {path, original_path, x, y, ignored, untracked}` and
`Snapshot {context, head, index, head_entries, files, directories, rows}` own
their data. File content and symlink target bytes are distinct; no followed
referent is used as link metadata. `Head` represents unborn/attached/detached
state and optional checkout-origin data without writing HEAD.

Key operations, with error aliases defined alongside their declarations:

```wolf
pub fn worktree.read_index(ctx: Context) -> index.Index ! WorkErrors
pub fn worktree.flatten_tree(repo: repository.Repo, id: oid.Oid) -> List[FlatEntry] ! WorkErrors
pub fn worktree.scan(ctx: Context) -> Snapshot ! WorkErrors
pub fn worktree.scan_index(ctx: Context, value: index.Index) -> Snapshot ! WorkErrors
pub fn worktree.scan_with_warnings(ctx: Context, include_untracked: bool,
    mut warnings: List[str]) -> Snapshot ! WorkErrors
pub fn worktree.scan_index_with_warnings(ctx: Context, value: index.Index,
    include_untracked: bool, mut warnings: List[str]) -> Snapshot ! WorkErrors
pub fn worktree.stage_paths_with_warnings(ctx: Context, mut value: index.Index,
    paths: List[List[byte]], options: AddOptions, mut warnings: List[str]) -> List[List[byte]] ! WorkErrors
pub fn worktree.query_ignore_with_warnings(ctx: Context, operand: str,
    no_index: bool, mut warnings: List[str]) -> ignore.Match ! WorkErrors
pub fn worktree.tracked_for_ignore(value: index.Index, path: List[byte]) -> bool
pub fn worktree.render_status(snapshot: Snapshot, options: StatusOptions) -> List[byte] ! WorkErrors
```

Scan/read operations do not refresh the index or acquire its write lock.
`include_untracked=false` skips ignore queries and untracked file-body reads,
not just their displayed rows. `compare_status_with_warnings` offers the same
control when comparing caller-supplied snapshots. Silent compatibility wrappers
remain for scan/index-scan, comparison, staging and ignore queries. Command
callers share one warnings list and flush once, including before fatal returns.
Tracked ignore bypass includes indexed descendants under a literal directory
prefix; `no_index=true` does not read the index at all.

For edits, callers own begin/abort/commit around `stage_paths`, `remove_paths`,
`plan_moves`/`move_paths` or `restore_paths`. `AddOptions`, `RemoveOptions`,
`RestoreOptions` and `MovePlan` make the selection explicit. The index lock
is not a promise of atomic rollback for a series of worktree file operations.

`commit_format` is pure: `Date {seconds, offset}`, `Identity {name, email,
date}`, `parse_date`, `date_text`, `make_identity`, `parse_author`,
`parse_identity`, `identity_text`, `cleanup_mode`, `comment_marker`, `cleanup`,
`paragraphs`, `file_message` and `message_empty`. Callers supply environment,
configuration and default offset; cleanup preserves binary message bytes.
Clock-relative dates, unsupported identity search and input/size limits have
explicit rows. Command-edge UTF-8 repair is not part of these pure APIs.

`commit.reflog_line` builds owned bytes; `publish_ref` publishes an attached
branch or detached HEAD, with exclusive locks and an expected-old-OID recheck.
An unchanged packed branch is not unpacked. It never writes ORIG_HEAD. Reflog appends and ref/index publication are not one
multi-file atomic transaction: later IO failure can leave earlier log bytes.
`commit.subject` formats the human first paragraph; `reflog_subject` uses only
the first physical line, before command-edge UTF-8 repair. FORMATS describes
same-OID amend logging and the normal-versus-`-a` index lifecycle.

### Rename scope and follow-on consumers

`rename.pair` now supplies staged status, commit summaries and diff. Exact OID
matching precedes approximate regular-file scoring. Nonregular files pair only
by exact OID/type; executable-bit changes remain regular-file compatible.
Candidate pools contain deletions and additions, plus modified retained
sources when copies are requested. Unique-basename preselection, four best
candidates per destination, stable slot ties and rename-before-copy assignment
are independently measured. No source/destination index is an absence sentinel.

Commit's metadata-only preview does not require unpublished `-a` blobs. Quiet
commit skips display work. Nonquiet summaries count actual OID differences,
even when a hash collision yields a 100-percent content score. The pairer is
bounded at 2,000 candidates per side and body scoring at 16 MiB per file.

vc05 should reuse lossless object headers, `head`, `flatten_tree`, owned rows and
the new pure diff consumer API below. `diff.collect`/`render` never refresh the
index; the CLI's separately measured optional refresh must not be imported into
log/show. Revision walking and pretty-history policy remain independent.
Amend retains all parents; merge-amend summaries are not a guessed first-parent
shortstat. General revision grammar and higher-stage mutation remain outside
these APIs. There is no production Git/shell dependency.

### Configuration boundary and key census

`ConfigEntry {key, value, implicit}` preserves raw assignments. `parse_config`
handles section/subsection case, quoting, escapes, continuations and implicit
booleans. `configuration` loads system/global/repository/runtime scopes in that
order; GIT_CONFIG_NOSYSTEM suppresses system reading. GIT_CONFIG_SYSTEM and
GIT_CONFIG_GLOBAL select their files; explicit GLOBAL replaces XDG/HOME defaults.
GIT_CONFIG_COUNT/KEY_n/VALUE_n override file values. Includes/includeIf refuse
by distinct names. Repo.config remains a last-value scalar map (implicit=true);
`config --get` preserves raw implicit output as an empty line. The
`configuration_diagnostics`/`check_config` boundary carries contextual CLI
errors without changing object APIs' RepoErrors. Files are capped at 1 MiB and
runtime pairs at 65,536. This is a reader, not a general config editor.

Keys currently consulted (canonical matching is case-insensitive except quoted
subsections); entries marked refusal controls do not imply feature support:

| Consumer | Keys |
|---|---|
| Repository / init | `core.repositoryFormatVersion`, `extensions.objectFormat`, `core.bare`, `core.worktree`, `init.defaultBranch`, `init.templateDir`; unknown `extensions.*` refuse |
| Loose storage | `core.compression`, `core.looseCompression` |
| Worktree / ignore / index | `core.fileMode`, `core.symlinks`, `core.excludesFile`, `core.quotePath`, `index.version` |
| Status | `status.short`, `status.branch`, `status.showUntrackedFiles`, `status.relativePaths`, `status.renames`, `advice.statusHints`; `branch.<current>.merge` triggers the unsupported upstream-tracking path |
| Diff | `diff.context`, `diff.indentHeuristic`, `diff.renames`, `diff.autoRefreshIndex`, `diff.statNameWidth`, `diff.statGraphWidth`, `core.abbrev`, `core.quotePath`, `core.fileMode`, `core.symlinks` |
| Add diagnostics | `advice.addEmptyPathspec`, `advice.addIgnoredFile`, `advice.updateSparsePath` |
| Commit identity / message / logging | `user.name`, `user.email`, `author.name`, `author.email`, `committer.name`, `committer.email`, `i18n.commitEncoding`, `commit.cleanup`, `core.commentChar`, `core.commentString`, `core.logAllRefUpdates` |
| Refusal / editor controls | `core.autocrlf`, `core.attributesFile`, `core.hooksPath`, `commit.gpgSign`, `core.editor`; attributes, nonempty hooks, signing and actual editor execution remain unsupported |

The generic --get command can retrieve any well-formed key; this is not a claim
that every Git option affects den. Environment identity/date overrides and
EMAIL/EDITOR/VISUAL/TZ are resolved by the commit command, not the pure format
module. User hooks/editors are never executed.

### Checked-machine and compiler limits

The combined `src/index_test.lu` checked program exhausts the pinned mem-phase
step budget; `index-combined-checked-budget.json` retains its unsupported
verdict. Five bounded actual-checked programs are wired into `tools/check-index`:
format, flags, trees, malformed input and stat mapping. All five recorded
exit(0) in the full gate. Native and
release still run the complete unit and independent filesystem/oracle suite.
The ignore, worktree, commit-format and commit unit programs also recorded
actual-checked exit(0). `final-gate.log` and `final-inputs.json` bind these
results to the source files; no runtime source was changed after that gate.

wolf-lang#927 tracks a native compiler gap when copying a lent str.bytes()
read parameter into a returned value. `probes/index-view-direct` refuses with
build exit 4, while `probes/index-view-bound` builds; both actual-checked probes
exit(0). Explicit byte materialization at owned-return boundaries is the narrow
workaround. `notes/vc03-evidence/index-view.log` retains the diagnostics; this is
not evidence that every native copy is broken or a substitute for checked
verification.


## Diff consumer boundaries (vc04)

The pure similarity API remains independent of filesystem and presentation:

```wolf
pub error DeltaErrors = {invalid, limit}
pub struct Similarity { common: int, maximum: int, units: int, percent: int }
pub fn delta.binary(data: List[byte]) -> bool
pub fn delta.span_counts(data: List[byte]) -> Map[int, int] ! DeltaErrors
pub fn delta.similarity(before: List[byte], after: List[byte]) -> Similarity ! DeltaErrors
```

It owns returned storage, limits inputs to 16 MiB, uses original size as the
denominator and returns a 60,000-unit score plus floored percentage. Exact byte
identity, including two empty inputs, scores 100; unequal chunks may collide.
The native and release external clients each match all 1,510 inherited records
(123/300/522/90/301/174) and 24 newly isolated projection collisions. The checked
unit verdict is independently `exit(0)`.

```wolf
pub struct Candidate { path: List[byte], mode: int, id: oid.Oid,
    data: List[byte], retained: bool }
pub struct Options { enabled: bool, copies: bool, threshold: int }
pub struct Pair { source: int, destination: int, units: int,
    percent: int, is_copy: bool }
pub fn rename.defaults() -> Options
pub fn rename.exact(before: List[Candidate], after: List[Candidate],
    options: Options) -> List[Pair] ! RenameErrors
pub fn rename.pair(before: List[Candidate], after: List[Candidate],
    options: Options) -> List[Pair] ! RenameErrors
```

`RenameErrors` is invalid/limit/invalid_oid/unsupported_format. Inputs may be in
arbitrary order; returned indices address the supplied lists. `exact` ignores
body data, supporting lazy reads. `pair` repeats the exact stage internally:
do not concatenate its results with `exact`. Retained sources are modified
paths, not arbitrary unchanged files. Threshold 100 requests exact OIDs,
not a colliding inexact score of 100. Default matching is enabled at 50 percent.
The mandatory pairer gate covers 267 candidate matrices and 1,044 full-state
status/commit comparisons per native tier; native/release/checked tests are
separate evidence rows.

```wolf
pub struct Line { start: int, end: int, hash: int }
pub struct Edit { old_start: int, old_count: int,
    new_start: int, new_count: int }
pub fn difftext.lines(data: List[byte]) -> List[Line] ! DeltaErrors
pub fn difftext.edits(before: List[byte], after: List[byte]) -> List[Edit] ! DeltaErrors
pub fn difftext.hunks(before: List[byte], after: List[byte],
    context: int, indent: bool) -> List[byte] ! DeltaErrors
pub fn diffbinary.patch(before: List[byte], after: List[byte]) -> List[byte] ! BinaryPatchErrors
```

`difftext` uses byte lines, including LF, and verifies line equality after a
hash prefilter. It keeps a bounded Myers trace; direct empty-side edits avoid
that search. General searches cap at 2,000 changed lines, inputs at 200,000
lines/16 MiB, context at 200,000. Invalid arguments and limits are explicit rows.
Its default boundary ranking matches 676/684 measured hunk outputs; the oracle
changes output in 56/684 when its indent heuristic is disabled. The remaining
seeded-21/seeded-116 cases at four context widths are fixed full-input/output
records in `tests/review/diff-hunks.json` (proposed R-vc04-3). Every generated
patch, including those eight records, is independently applied forward and
reverse to reconstruct exact bytes. These eight are not parity passes.

`diffbinary.patch` returns the complete `GIT binary patch` body, not ordinary
headers, with errors invalid/limit and 16-MiB input bounds. R-vc04-4 was refined
by the coordinator by analogy to R4c: literal/delta selection and delta payload
lengths belong to the representation; literal target lengths, blob sizes/OIDs,
framing and forward/reverse application are checked independently. The original
corpus is 55/150 byte-identical; the expanded corpus is 154/250, with 96 fixed
capture-bound representation differences, not parity. The strict byte gate
remains report-only red. A new/changed capture fails the accepted gate.

```wolf
pub struct File { path: List[byte], mode: int, id: oid.Oid, data: List[byte] }
pub struct Change { before: List[File], after: List[File], status: str, percent: int }
pub fn diff.defaults() -> Options
pub fn diff.configured(ctx: worktree.Context) -> Options ! worktree.WorkErrors
pub fn diff.changes(before: List[File], after: List[File], options: Options)
    -> List[Change] ! worktree.WorkErrors
pub fn diff.collect(ctx: worktree.Context, options: Options)
    -> List[Change] ! worktree.WorkErrors
pub fn diff.render(ctx: worktree.Context, changes: List[Change], options: Options)
    -> List[byte] ! worktree.WorkErrors
pub fn diff.run(args: List[str]) -> int
```

These qualified signatures distinguish modules; `diff.Options` is the display
record in `src/diff/model.lu`, not `rename.Options`. `configured` reads config,
COLUMNS and terminal size without publishing state; plain `defaults` is pure.
Endpoints must be sorted by
unsigned path for `changes`; each Change side is an owned zero/one file list.
`collect` handles worktree/index, cached HEAD or a named endpoint, two loose/packed
commits/trees and two blobs. Aggregate body input is limited to 128 MiB per
endpoint. Simple bounded `^n`/`~n` ancestry is not a general revision parser.

Only `run` performs documented `diff.autoRefreshIndex` work: a selected stale
but content-equal entry triggers refresh of all unchanged entries. Foreign
index locks suppress it silently; cached/two-object forms do not refresh.
Disabling auto-refresh also preserves Git's stat-only name-list behavior.
The matrix uses R-vc03-3's six-word per-file proof, never a wildcard index
normalization. Pure collect/render is exercised from `probes/diff-client`.

All component checks are mandatory in `tools/gate`. New captures are collected
under the workflow's existing `target/runs` artifact path on success or failure.
The historical `probes/hunk-prototype` is frozen evidence, not a consumer API.
The final full local gate passed with 234 functional input hashes unchanged.
Per native tier: 336 basic display, 575 endpoint/pathspec/width, 66 refresh and
12 external-API comparisons agree exactly (the refresh comparison uses its
proved six-word canonicalization). The 684 hunk and 250 binary comparisons
retain their separately counted differences above. `final-counts.json` derives
all counts from captures; four new unit programs report actual-checked exit(0).
Ninety separate pipe/private-PTY cases per tier measure COLUMNS, window sizes
and explicit width overrides; explicit zero width means 80, not terminal width.
Per-file patch/count scratch is reclaimed by explicit regions; this is a
bounded whole-file implementation, not a streaming-memory benchmark claim.


## History consumers (vc05)

`walk.Commit` owns its OID, tree OID, ordered parent OIDs, lossless
`object.Headers`, committer timestamp and encoded input size. `walk.parse`
validates a bounded SHA-1 commit without changing its raw message or unknown
header continuations. `walk.read` reads one loose or packed commit. `walk.collect(repo,
starts, max_count, skip, max_nodes, first_parent)` visits each reachable commit
once, selecting the greatest committer timestamp from the active frontier and
retaining enqueue order on ties. Its node budget is explicit; commit data is
limited to 128 MiB in aggregate. Author dates never determine default order.
No index, ref or reflog is written.

`pretty.date`, `identity`, `message` and `render` are presentation boundaries.
Raw objects remain unchanged. The renderer receives caller-computed unique
abbreviations (commit, then ordered parents), checks their prefixes, and uses
`commit.subject` for human one-line summaries, not `commit.reflog_subject`.
Default output preserves leading/internal message bytes, trims trailing ASCII
whitespace, expands ASCII tabs, and distinguishes empty messages from a blank
paragraph. NUL terminates presentation only. Non-UTF-8 bytes without tab-width
ambiguity remain bytes; message transcoding is an explicit refusal.

`history.abbreviate` checks the loose/packed object namespace for collisions.
`history.patch` compares a root against an in-memory empty endpoint with
`diff.changes`; nonroots use `diff.collect`. Both paths call `diff.render` with
`diff.configured` defaults. They never invoke `diff.run` or `index.write_tree`.
`diff.resolve` is now public: its bounded caret/tilde adapter is unchanged.
Show handles loose/packed commits, blobs, tree entries, annotated tags and a literal
`REV:path` traversal; these are not a general revision grammar.

`tools/check-history` is mandatory: native/release command stdout, stderr,
status and complete file-byte/mode state; an independent importing package;
bounded pretty and raw-walk actual-checked programs. Captures include negative
scope rows separately from exact comparisons. A foreign index lock and dirty
worktree are present throughout. The two named hunk witnesses and capture-bound
binary representation policy remain unchanged and are not history parity.

Remaining M2 surfaces: combined merge show, show revision limiting, history
path simplification, graph/topological order, custom pretty formats,
relative/human dates and non-UTC local zones. ASCII tab rendering is supported;
non-ASCII prefixes before tabs require a future display-width surface. General
revision grammar stays M3. M2 is not complete merely because the bounded
history matrix passes.

## Refs and branch transitions (vc06)

`refs.Packed {name, id, peeled}` owns a full ref name, the actual target OID and
zero or one peeled OID. Peeling metadata does not replace an annotated tag's
OID. `parse_packed` checks names, IDs, duplicate records and peeling placement;
`packed_bytes(records, traits)` emits only caller-proven peeling traits. Deletion
carries the source file's traits rather than inventing `fully-peeled`.

`read(repo, full_name)` resolves HEAD or full symbolic/loose/packed refs, with
loose precedence and a sixteen-link bound. `optional` returns an empty list only
for absence; malformed and inaccessible refs are not unborn refs. `list(repo,
prefix)` merges the namespaces and sorts by refname, parsing the packed file
once. Parsing/writing caps packed data at 16 MiB and 100,000 records; listing
caps entries and visited loose nodes at 4,096. The independent client exercises
1,002 heads and an explicit over-limit input.

`update(repo, name, expected, after, identity, message, force_log)` is a direct
ref CAS: empty `expected` requires absence, empty `after` deletes. The caller
validates referenced objects. Exclusive ref locks are owned until publication
or abort. Deletion acquires `packed-refs.lock` even when no packed file exists.
`set_head` compares exact prior HEAD text under HEAD.lock. `rename_ref` holds
old/new ref locks and, for the current branch, HEAD.lock; it retains the source
reflog. These operations do not promise an atomic multi-file transaction.

`log_line` constructs owned raw reflog bytes. A same-OID direct update omits its
log; an attached reset still appends HEAD's record. A current-branch rename has
two HEAD records, old-to-zero and zero-to-old, while its branch log has one
old-to-old record. Tag reflogs describe the original target, first physical
commit-message line, and UTC committer date. These distinctions have separate
black-box captures; they are not inferred from human log subjects.

`worktree.transition(ctx, mut index, target, mode)` accepts owned flattened
target leaves and switch/hard/mixed modes. Its caller holds the index transaction
and publishes it explicitly. It validates target blobs, preserves compatible
local changes, refuses destructive ordinary switches, and reuses worktree file
installation and index-entry APIs. Mixed reset invalidates affected TREE paths;
hard reset and clean checkout rebuild TREE in memory. It never calls
`index.write_tree`, writes a history object, or forks the rename/diff scorer.

`refcmd` supplies branch/tag/switch/checkout/reset command edges and shares
commit identity/date and object/tag writers. `commit.environment_identity` is
now public for that reuse. Reset publishes index/worktree changes before ref
updates; a foreign ref lock can therefore leave those earlier changes visible.
ORIG_HEAD is reset's responsibility, never commit's. AUTO_MERGE cleanup has two
measured attempts, and its failures can be diagnostics on a successful command.

Supported revision inputs are HEAD, a full ref, a short branch/tag, a full OID
or an unambiguous loose/packed object prefix. Ambiguous short names are rejected.
General ancestry/ranges/reflog selectors and previous-checkout syntax remain
vc10's work. Tracking configuration, list glob patterns, orphan branches,
overlapping rename paths, merge-mode checkout, tag editors/signing/stdin and
reflog management commands remain outside the bounded surface. Tree transitions
refuse unmerged/flagged indices and submodules; checkout during an in-progress
operation is a named refusal. Switch and soft reset have measured in-progress
safety errors. None of these limits completes M2 or the remaining M3 rows.

`tools/check-refs` is mandatory in the full gate, with native/release complete
command/state captures, an independent importing package, and refs/reflog
actual-checked units. Exact comparisons and named unsupported captures are
separate. It uses the inherited six-word stat proof, not an index exclusion.
The original oracle build failed at the non-CI mount `/work`; the identical
image at `/work/den` reproduced the existing binary pin. The default build path
is therefore part of the reproducible input contract.

## Merge boundaries (vc07)

`mergebase.Node {id, parents}` is an owned, caller-validated commit DAG.
`ancestor(nodes, older, newer, cap)` checks reachability; `bases(nodes, left,
right, cap)` returns every best common ancestor in input-node order. Both tips
are traversed without timestamp pruning. Since common ancestry is parent-closed,
a single edge sweep removes dominated common nodes. Missing nodes, duplicate
IDs and the explicit cap are errors. The cap is at most 100,000 nodes.
`mergetree.bases(repo, left, right)` adapts the owned object walker; it
never reads or writes the index. The command refuses multiple criss-cross bases
rather than choosing one: recursive virtual-base merging is still open.

`mergefile.merge(base, ours, theirs, ours_label, base_label, theirs_label,
style)` returns owned `{data, conflicts}`. It reuses `difftext.edits`, preserves
raw bytes and final-newline behavior, and renders merge/diff3/zdiff3 markers.
Labels are single physical lines. Invalid options, binary conflicts and inherited
file/edit bounds are distinct errors. The default-style nearby-conflict joining
rule was measured against `git merge-file`, not copied from an implementation.
The independent file client compares 1,521 input/style combinations per native
tier; the independent graph client compares 84 complete base sets and repository
immutability. Three actual-checked programs cover graph, text and REUC.

`mergetree.files` collects owned regular-file endpoints, capped at 16 MiB per
blob and 128 MiB per endpoint. `mergetree.plan` returns files, higher stages,
ordered diagnostics and conflict paths without publication. It uses the existing
`diff.changes`/rename scorer to detect rename topology, which currently refuses.
Repeated base-line hashes and multiple edits per changed side also refuse:
`ort` defaults to histogram, not the file API's Myers algorithm. Other named
limits are modify/delete and binary conflicts, nonregular entries, annotated-tag
messages, unborn merge and dirty/staged true-merge recovery. Fast-forward safety
and clean regular-file merges remain supported, not approximated fallbacks.

`worktree.merge_check` previews safety without writing objects/index/worktree;
`transition(..., "merge")` installs under the caller's index lock.
`abort_merge` restores unmerged paths from HEAD, preserves unchanged entries and
dirty paths, and checks stage-zero stat identity before replacing such a path.
`commit.refresh_index` exposes the existing content-equal-only refresh policy.
`commit.run_revert` supplies the measured direct no-editor revert publication:
a nonempty revert preserves COMMIT_EDITMSG, and AUTO_MERGE remains after success.
Ordinary `commit` now consumes MERGE_HEAD parents and resolved REVERT_HEAD state.

The command matrix contains 117 exact complete-state rows and 12 separate named
not-yet captures per native tier. It measures ORIG_HEAD before fast-forward
publication, MERGE_HEAD/MERGE_MSG/MERGE_MODE, AUTO_MERGE, SQUASH_MSG, REVERT_HEAD,
ref-lock failure after index publication, packed/detached inputs, root revert,
conflict resolution/REUC and abort. A named refusal is checked for immutable
state; it is never counted as oracle parity. The index comparison retains the
six-word per-file proof. Dirty true merges remain named because the oracle's
internal recovery commits and transient stat writes are additional observable
state, not permission to ignore those files. The full gate runs `check-merge`.

M2's combined merge show/editor/history limits and the two hunk witnesses/eight
contexts plus 96 binary representations are unchanged. Revert sequences and
mainline selection and the recursive/rename/alignment limits above remain
follow-on work; a green bounded merge matrix does not complete M3.

## Replay and durable progress (vc08)

`sequencer.Step {name, subject}` owns a lowercase full/prefix SHA-1 name and a
single physical subject line. `parse(data)` accepts pick records and comments;
other commands, malformed names, NUL/CR, invalid UTF-8, data above 16 MiB and
more than 100,000 records are errors. `render(steps)` validates and returns owned
LF-terminated records. Neither API reads repositories or executes instructions.
`empty_action(originally_empty, allow_empty, policy)` distinguishes initially
empty commits from changes made redundant at the destination.

`line_sum(data)` returns a wrapping-u64 sum of whitespace-normalized line
checksums, bounded at 16 MiB. Equal net changes are only *possible* upstream
patch equivalence. Default rebase refuses such a match; collisions and ignored
path/order information can cause additional refusals, never dropped commits.
This is not Git's patch-id algorithm. Explicit `--reapply-cherry-picks` bypasses
that preselection guard; the tree merge and empty-result policies still apply.

The refcmd replay controller uses owned `walk.Commit`, `mergetree.plan`, index
transactions, `worktree.transition`/`abort_merge`, refs and commit publication.
It never uses `index.write_tree` for history reads, forks the rename scorer or
invokes Git. Selected commit data is bounded at 128 MiB. Applied steps reclaim
scratch between commits; later unsupported trees retain earlier published
commits and progress rather than claiming whole-sequence rollback.

Single cherry-picks use CHERRY_PICK_HEAD/MERGE_MSG/AUTO_MERGE. Explicit lists add
sequencer/head, todo, abort-safety and options. Rebase uses rebase-merge/head-name,
onto, orig-head, todo/backup, done, end/msgnum, author-script, stopped-sha,
message, patch and rewritten-list as measured. The author-script file is inert
data. Unknown state files and unsupported todo commands are refused. State
metadata writes use exclusive locks, sync, rename and directory sync; this is not an
atomic transaction spanning worktree, index, objects, reflogs and refs.

Automatic picks preserve original author/date while resolving the current
committer. Direct versus ordinary commit completion have distinct reflog and
COMMIT_EDITMSG/AUTO_MERGE lifecycles. The ordinary commit edge consumes resolved
CHERRY_PICK_HEAD and preserves author provenance. Rebase skip/abort restores
hard, unlike cherry-pick's merge-style reset. HEAD-lock failures can leave the
new index/worktree visible; initial and recovery failure phases are compared.

`tools/check-replay` is mandatory. Per native/release tier it measures 89 exact
complete-state scenarios, 20 separately named scope captures, and 136 independent
importing-client checks. One bounded actual-checked program covers records,
empty policy and the conservative checksum. Each intermediate process result is
compared in multi-step scenarios; no repository file or index is excluded.

Named limits include editor-dependent staged rebase continuation (explicitly
commit the resolution first, then continue), dirty cherry-pick recovery and
AUTO_MERGE-lock transient stat history, possible upstream equivalence, foreign
or changed operation state, non-default replay configuration, apply/interactive
backends, real merge replay, branch/upstream inference and a separate branch
operand. The inherited repeated-line/multi-hunk, rename, nonregular, binary and
modify/delete boundaries remain; recursive true-merge bases and dirty true-merge
recovery are not closed by this lane. General revision grammar stays vc10.
M2 editor/combined-show/history limits and all diff exceptions remain open.
