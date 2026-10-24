# Map

M0 is a scaffold. `den --version` works; all other commands refuse with
exit 2 and the destination milestone/lane. No repository-writing feature is
implemented. A successful M0 gate means the harness classified refusals
honestly, not that den matches Git.

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
| zlib inflate/deflate | Absent; no `std.compress` module | `deflate`: E0301 native + checked; own-source grep finds cryptographic/DNS compression and configuration names, no zlib codec. vc01 is the component, not an FFI dependency |
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

## zlib component boundary

vc01 is a den module initially. RFC 1950 framing: validate CMF/FLG and FCHECK,
reject preset dictionaries by name, validate big-endian Adler-32, report the
number of input bytes consumed. RFC 1951 inflate first: stored/fixed/dynamic
blocks, overlapping backreferences, bounded output and explicit malformed /
truncated rows. A pack contains concatenated compressed streams, so callers
must know exactly where each stream ends. Then a stored/fixed encoder and a
bounded match finder; no C zlib linkage in the shipped tool.

The oracle's default loose compression matches zlib level 1 on the measured
95,232-byte payload (953 bytes compressed); core.compression=9 produces 627
bytes (this corpus cannot distinguish levels 7–9), and an explicit loose
level 0 produces 95,259 bytes. See FORMATS and raw summary. This measures the
default rather than inferring the numeric setting from an FLEVEL bit.

## Decisions proposed, not ruled

- **R-vc00-1 — SHA provenance.** 575dc7b lacks the requested file. Options:
  stop vendoring, or use the SHA implementation at b603bb8 as formatted at
  f87dc76. Recommend the latter; provisionally adopted in headers/tests.
- **R-vc00-2 — loose compressed bytes.** R4a asks for identical loose-file
  bytes, while R9 permits a new fixed-Huffman deflater whose bytes differ.
  Options: reproduce zlib 1.3's encoder exactly, or require identical raw
  object bytes/oid plus valid interoperable zlib and record sizes. Recommend
  the latter (pack-like representation distinction); vc01 draft is conditional
  on that ruling. The current harness still compares every .git byte and
  waives nothing. No standing parity bar has been silently weakened.
- **R-vc00-3 — push wire protocol.** The v2 document defines fetch/ls-refs,
  not a receive-pack push command. Options: defer push with all v0/v1, or
  allow receive-pack's traditional advertisement/capabilities/status framing
  for push while retaining v2-only fetch. Recommend the latter. vc14 must
  settle this before claiming push; no wire implementation exists today.

## Harness and CI

Nine corpus repositories: two files; ten-commit linear history; branch/merge;
rename; binary; symlink; empty tree; 1,000 files; packed after gc. Every one
passes oracle fsck. Two independent builds produce the same object manifests.
That proof concerns oids, not inode-dependent index stat bytes.

`tests/cases.json` names 32 cases. `tools/oracle --filter TEXT` selects a
subset; an empty selection fails. `--strict` fails on not-yet rows. Normal M0
mode counts those separately: 1 version-shape pass, 31 not-yet, 0 parity or
reviewed rows. Every unexpected mismatch fails. The gate also proves --strict refuses not-yet and an empty filter is an error; local native TLS is gated, with one actual checked budget refusal printed and counted. Review JSON binds the case
hash and the complete Git/den stdout, stderr, status and .git file maps, with
reason and issue/ruling; there is no wildcard, normalization or excluded file.
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
