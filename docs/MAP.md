# Map

The codec, owned OIDs, bounded loose store and binary object parsers underpin
a writable index and the implemented worktree/commit subset. The dispatcher
now routes add/rm/mv/status/commit/restore, path-only checkout, check-ignore and
read-only config --get as well as the object plumbing. M2 is not complete:
edited rename similarity, diff/history commands, general refs, packs and
transports remain separate work. The local full gate passed against 177 frozen
source/input hashes, checked again after completion; final-head CI remains the
merge gate. This is a measured subset, not full Git compatibility.

## Modules and lanes

| Milestone | Modules and scope |
|---|---|
| M0 | CLI refusal scaffold, `hash`, probes, oracle/corpus/review harness (vc00) |
| M1 | `zlib`: inflate then deflate, Adler-32 (vc01); `oid`, `object`, `repository`, init/hash-object/cat-file/tree/commit/tag plumbing (vc02) |
| M2 (partial) | `index`, `worktree`, `ignore`, `commit_format`, `commit`: implemented subset (vc03); edited rename similarity and `diff` (vc04); `walk`, `pretty`, log/show (vc05) |
| M3 | `refs`, `reflog`, branch/tag/checkout/reset (vc06); three-way merge/revert (vc07); rebase/cherry-pick/sequencer (vc08); blame (vc09); stash/notes/revision grammar (vc10) |
| M4 | `pack`, `pack_index`, delta decoding (vc11); pack writing, gc/repack/fsck/count-objects (vc12) |
| M5 | `pktline`, protocol v2 fetch (vc13); receive-pack push/remotes (vc14); clone/pull porcelain (vc15) |
| M6 | static build and PAX handoff (vc16, then px lane); optional `git` alias |
| Later | HTTPS beyond measured TLS profile, hooks, worktrees, sparse index, submodules, SHA-256 repositories, interactive rebase, bundles and protocol v0/v1 fetch |

The MVP is M0–M3, file/git transports from M5, and M6. Pack support is
separately staged; transports must not pretend a pack reader already exists.
OID design keeps an algorithm and a byte list from the start, never a fixed
20-byte public type. SHA-256 is available in the hash adapter already.

## Surfaces

The original surface census was measured on wolf 0.2.35 (`cf0c13d3`), bundled
std `2386522e`, Ubuntu 24.04 on kasumi CPUs 12–15. M1/M2 implementation
measurements use hasu CPUs 0–5 with the same pinned toolchain/container. “Checked” below means the observation's
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
`tests/cases.json` defines 163 main cases, with generated component matrices
counted separately. The full gate reports 136 parity / 26 named not-yet /
1 version-shape / 0 reviewed / 0 failures. It validates 636 canonicalized
tool-side entry rows: 60 in the main matrix, 84 per worktree tier, 168 per
commit tier and 36 per index-client tier. There are 54 distinct captured status
stdout texts across the main/worktree matrices. `final-counts.json` records
these counts directly from the observations.

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
extensions refuse by name. Resolving/removing higher-stage entries is refused
until their REUC generation is implemented, rather than losing undo data.

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
loose branch with exclusive HEAD/branch locks and an expected-old-OID recheck.
It never writes ORIG_HEAD. Reflog appends and ref/index publication are not one
multi-file atomic transaction: later IO failure can leave earlier log bytes.
`commit.subject` formats the human first paragraph; `reflog_subject` uses only
the first physical line, before command-edge UTF-8 repair. FORMATS describes
same-OID amend logging and the normal-versus-`-a` index lifecycle.

### Rename scope and follow-on consumers

R-vc03-5 keeps staged rename/copy matching exact-OID only, including regular
100644/100755 mode changes when the file type agrees. Rename-enabled status
refuses unresolved same-type staged A+D candidates by name rather than guessing
an edited-content score. Non-quiet commit checks its corresponding human
summary policy before writes; quiet commit skips that unavailable summary and
can use the otherwise exact staged tree/ref/reflog path. This is not M2
completion or an accepted approximate rename metric. Disabling status rename
detection returns independent rows without invoking that metric.

vc04 should consume full Index.Entry paths/modes/OIDs and the owned snapshots,
not legacy flat `parse_v2`; compare content and configured modes, never stat
words alone. Replace the explicit edited-similarity refusal only after a
clean-room general rule passes the discriminating black-box cases. The six
archived `notes/vc03-evidence/rename-measure-{initial,random,hash,structural,equivalence,wrap}.json`
reports contain 1,510 pairs from `tools/rename-measure.py`, with matching logs.
They are research captures, not scorer parity or a fixture-specific exception
table. Exact byte span matching and first-byte-offset normalization both
misclassify witnesses.

vc05 should reuse lossless object headers, `head`, `flatten_tree`, owned rows and
quoting/subject helpers as appropriate, but must implement revision walking and
pretty-history policy separately. Amend retains its complete parent list;
merge-amend human summaries cannot be guessed as first-parent shortstat.
Neither consumer may assume all extensions, arbitrary revision grammar or
higher-stage mutation are supported. There is still no production Git/shell
dependency.

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


## Similarity primitive and unfinished diff experiment (vc04)

`src/delta/similarity.lu` adds a pure, bounded content-similarity API. It is not
wired into `status`, commit summaries or a `diff` command yet; their existing
refusals and M2's incomplete state are unchanged.

```wolf
pub error DeltaErrors = {invalid, limit}
pub struct Similarity { common: int, maximum: int, units: int, percent: int }
pub fn delta.binary(data: List[byte]) -> bool
pub fn delta.span_counts(data: List[byte]) -> Map[int, int] ! DeltaErrors
pub fn delta.similarity(before: List[byte], after: List[byte]) -> Similarity ! DeltaErrors
```

Each input is limited to 16 MiB. The map owns its storage. LF/64-byte spans
contribute byte weights to fingerprint buckets; text CRLF handling and the
8,000-byte binary sample are measured independently on each side. Similarity
uses the original maximum body size as denominator, preserves copied-byte
weight, and exposes a 60,000-unit score and floored percent. Identical byte
bodies, including two empty bodies, score 100. File-type eligibility, exact-OID
priority, candidate assignment and rename thresholds belong to a future pairer,
not this function. Fingerprint collisions deliberately affect similarity;
100 percent is not an identity test.

`tools/check-delta` is a standalone gate, not yet part of `tools/gate` or CI.
The native and release public clients each agree on all 1,510 inherited score
and 50-percent-threshold observations, plus 24 independently isolated collision
pairs. `src/delta_test.lu` also returns actual-checked `exit(0)`. The six report
counts are 123/300/522/90/301/174; raw results and derivation are retained under
`notes/vc04-evidence/`. This is not CLI rename/copy-pairing parity.

The unfinished Myers/unified-hunk experiment is isolated in
`probes/hunk-prototype/`, outside production modules. Its strict differential
witness `tools/diff-hunks-test.py` is intentionally RED, not a passing gate:
620/684 comparisons match Git's default, 676/684 match with its indent heuristic
disabled, and the oracle's two modes differ in 56/684. The remaining no-indent
counterexamples are seeded-21 and seeded-116 at all four context widths.
`hunks-checkpoint.json` retains complete inputs and both oracle outputs.
Do not import this renderer into log/show or expose it as a compatible diff.
