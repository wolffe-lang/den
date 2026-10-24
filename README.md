# den

A version control system in [wolf](https://github.com/wolffe-lang/wolf-lang),
working toward Git-compatible repositories and wire protocols. Where a wolf
keeps what it has.

**State: M0, the map. No VCS command works yet.** `den --version` prints
`den 0.0.0 (built with wolf 0.2.35)`. Every other command refuses by name,
with its destination milestone/lane, on stderr and exits 2. This is not a
replacement for Git. The module/lane map and measured surfaces are in
[MAP](docs/MAP.md); documented formats and generated oracle bytes are in
[FORMATS](docs/FORMATS.md).

## Machines and pins

| Role | Machine / identity |
|---|---|
| Behavioral oracle | Git 2.56.0, signed kernel.org tarball; default build (Rust, gettext, HTTPS enabled), Ubuntu 24.04 image by digest |
| Development witnesses | kasumi, Linux x86-64, rootless pinned container, lane-assigned CPUs under flock |
| CI PR gate | ubuntu-24.04, same container and oracle, planner's own tests |
| CI full field leg | macOS arm64, Homebrew Git; nonblocking observation, not the oracle |
| Toolchain | wolf 0.2.35 cf0c13d3, lupin 0.1.56 tag 28547b4 (binary embeds 294d626), bundled std 2386522e |

Archive and oracle pins are in `wolf-toolchain.toml` and `den-oracle.toml`.
Downloads are refused on a digest mismatch. Both release API reads, detached
signature verification and two identical oracle builds are retained in
`notes/vc00-evidence/`.

## Build and measure

On Linux with rootless Podman, run in the assigned CPU block. This example is
vc00's allocation; other lanes need their own host/block assignment.

```sh
flock ~/lanes/kasumi-cores-12-15.lock \
  taskset -c 12-15 tools/in-container tools/gate
```

The gate fetches the complete toolchain archives, builds/verifies the signed
oracle, checks formatting, builds native/release, runs SHA tests on native and
the actual checked machine, constructs the corpus twice, runs harness selftests
and the matrix, then builds the static Linux binary twice. `tools/mkden OUTDIR`
checks ET_EXEC/no PT_INTERP and prints both full and stripped binary digests.
Baseline Ubuntu libraries are used, never the host's architecture-tuned glibc.

Inside that container, after setting `DEN_GIT` to the pinned built Git:

```sh
tools/env COMMAND ARGS...          # fixed identity, dates, locale, hooks and HOME
tools/corpus target/corpus --prove-twice
tools/oracle                      # every case, explicit M0 classifications
tools/oracle --filter status       # only matching names; empty selection is an error
tools/oracle --strict              # refuses every not-yet result as well
tools/probe                       # native + conform-run --checked JSON verdicts
tools/probe-tls                    # local OpenSSL and GitHub TLS observations
tools/formats                     # regenerate byte examples in target/formats/
```

There is no production dependency on Git, Python, zlib or OpenSSL; they are
black-box oracle/harness tools. Shipped wolf code depends only on wolf-std and
the provenance-marked SHA-1 code the organisation wrote in boreutils.

## Corpus and review rows

The nine reproducible fixtures cover two files, a ten-commit history, a branch
and merge, rename, binary bytes, symlink, empty tree, 1,000 files, and a packed
repository after gc. Two independent builds have identical oid manifests.
Index inode/ctime fields are not claimed reproducible across fresh copies.

| Matrix class | Cases | Meaning |
|---|---:|---|
| version shape | 1 | own version line and status, not equality with `git --version` |
| parity | 0 | stdout, stderr, status and all .git file bytes agree |
| reviewed | 0 | exact accepted differences, listed individually below |
| not yet | 31 | exact named scaffold refusal; no repository writes |
| unexpected failures | 0 | any new mismatch makes the gate red |

**Accepted review rows: none.** [Review mechanism](tests/review/README.md).
A review names the case, both complete byte results, reason and issue/ruling.
Neither an expectation change nor a blanket ignored index counts as a review.
Every .git file is compared; no repository paths are excluded. The one-byte
version plant was rejected by the CI differential gate (run 40130445507,
closed-unmerged PR #2). The selftest also rejects repository-only corruption.

The case list is `tests/cases.json`; `--strict` intentionally fails at M0.
A green normal gate proves the scaffold/harness, not Git parity. Unimplemented
commands and raw-byte path limitations must not be presented as supported.

## Measured gaps

The full stat record includes nanosecond times, identity, permissions, owner
and size. TCP and subprocess pipes work in both directions on native and the
actual checked machine. Git-style dates work. TLS completes a native local
Ed25519/OpenSSL handshake, but RSA-signed certificates and the observed GitHub
chain return `unsupported_alg`; the checked TLS program exhausts its mem-phase
budget before a handshake. HTTPS is deferred, not generically claimed absent.

No zlib codec exists in the scanned org code; vc01 is its implementation lane.
Non-UTF-8 path arguments, non-creating writable opens, argv[0] at this pin,
regex and mmap have named upstream limitations in MAP. muzzle is not a
dependency; a future C-facing libden would need a C ABI/allocator boundary.

## CI and packaging

`plan` selects PR/full/noop/partial tiers; `ci/tiers-test.py` tests both planning
and the final verdict. Normal PRs run Linux; trunk/nightly/dispatch and a
`full-matrix` label add the nonblocking macOS field observation. The label is
added at the final head by the orchestrator, never by a lane. A failed nightly
opens or updates a `nightly-red` issue. No local Mac builds were used for M0.

`packaging/den.rb` and `packaging/PKGBUILD` are **drafts, not published**. They
refer to a future v0.1.0 tag that does not exist and deliberately contain an
unfilled source-archive digest. They must not be installed or uploaded as a
release. Neither draft replaces the system Git or installs a git alias.

## Clean room

Authors read Git's documentation, published specifications and run the oracle.
They never read Git implementation source, libgit2 or another Git implementation's
code. No blog code is translated. [SOURCES](docs/SOURCES.md) records the exact
pages, sections and organisation-owned references. Every difference needs an
exact reviewed row. A format ambiguity or divergence is a proposed ruling,
never a silent lane decision.

## Licence

GPL-3.0-only (`LICENSE`) with the wolf Training Data Permission
(`LICENSE-TRAINING-DATA`). Vendored organisation-owned files carry provenance.
