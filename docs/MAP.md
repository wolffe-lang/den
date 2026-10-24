# Map

M1 includes the codec, owned OIDs, bounded loose store, binary object parsers,
repository discovery/init and the measured plumbing subset described in README.
Packs, index writing, porcelain and transports remain unimplemented; unsupported
options/features refuse by name. A green gate is not full Git compatibility.

## Modules and lanes

| Milestone | Planned modules and owners |
|---|---|
| M0 | CLI refusal scaffold, `hash`, probes, oracle/corpus/review harness (vc00) |
| M1 | `zlib`: inflate then deflate, Adler-32 (vc01); `oid`, `object`, `repository`, init/hash-object/cat-file/tree/commit/tag plumbing (vc02) |
| M2 | `index`, `worktree`, `ignore`, add/rm/mv/status/commit/restore (vc03); `diff` Myers, unified output and rename detection (vc04); `walk`, `pretty`, log/show (vc05) |
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

Measured on wolf 0.2.35 (`cf0c13d3`), bundled std `2386522e`, Ubuntu 24.04
container on kasumi CPUs 12–15. “Checked” below means the observation's
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

## Harness and CI

Nine corpus repositories: two files; ten-commit linear history; branch/merge;
rename; binary; symlink; empty tree; 1,000 files; packed after gc. Every one
passes oracle fsck. Two independent builds produce the same object manifests.
That proof concerns oids, not inode-dependent index stat bytes.

`tests/cases.json` names 86 cases. `tools/oracle --filter TEXT` selects a
subset; an empty selection fails. `--strict` fails on not-yet rows. Normal M0
mode counts those separately: 1 version-shape pass, 28 not-yet, 57 parity and 0
reviewed rows. Every unexpected mismatch fails. The gate also proves --strict refuses not-yet and an empty filter is an error; local native TLS is gated, with one actual checked budget refusal printed and counted. Review JSON binds the case
hash and the complete Git/den stdout, stderr, status and .git file maps, with
reason and issue/ruling; there is no wildcard or excluded file. Named `loose-object-raw` comparison
validates checksum/header/oid and compares raw bytes; compressed evidence
remains in the captures. All non-object file bytes and modes remain exact.
A review stops matching when either side changes. The seed template is empty
so the harness never reads Git's sample hook scripts.

Repository copies have different inode/ctime metadata; before index-writing
parity is asserted vc03 must supply shared stat fixtures or a specifically
reviewed index-stat difference. It must not globally exclude the index.
Optional index refresh is disabled in the pinned environment for read-only
commands. Index data itself is never normalized by this harness.

CI plan: PR runs ubuntu-24.04 and the planner's own tests; full-matrix at the
final head (or trunk/nightly) adds a nonblocking macOS Homebrew-git field leg.
Only the orchestrator may add that label. The nightly opens/updates a
nightly-red issue on failure. Build/probe jobs locally run inside the pinned
Ubuntu container under the core-block flock. The .txt evidence/PR-body route
is used instead of a Markdown lane report, as the lane tool rules require.

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

vc03 should retain this API, implement index writing/refresh and nested tree
assembly, and replace the minimal flat-v2 reader only with strict checksum,
padding, mode, stage and extension tests. The existing TREE cache is ignored
for building but preserved byte-for-byte; unknown extensions refuse by name.
Do not normalize inode/ctime fields or ignore the index in parity snapshots.
Keep generic stored headers/messages lossless; commit-tree's observed repair
belongs only at the command edge. General config/date/revision parsing is not
provided by this milestone. Add no production Git or shell dependency.
