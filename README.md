# den

A version control system written in [wolf](https://github.com/wolffe-lang/wolf-lang), compatible with git: it reads and writes git's repositories byte for byte, speaks git's wire protocol to git servers, and runs on PAX. Where a wolf keeps what it has.

**State:** opened 2026-10-24; nothing works yet. The plan is track 16 of the planning repo; the first lane (vc00) scaffolds the toolchain pin, the CI tiers, the oracle and the differential harness.

## The oracle and the rules

- The oracle is **git 2.56.0**, built from the kernel.org tarball in `ubuntu:24.04` with its default configuration, pinned by digest. den is measured against it: the same content gives the same object ids and the same bytes on disk; for the supported commands, the same stdout, stderr and exit status under a pinned environment (`tools/env`); a repository den writes passes `git fsck`, and git's repositories open in den.
- **Clean-room.** den's authors read git's *documentation* (the `git*(1)`, `gitformat-*(5)`, `gitprotocol-*(5)`, `gitrepository-layout(5)`, `gitignore(5)`, `githooks(5)` pages), the Pro Git book, RFC 1950 and 1951, FIPS 180-4, and the published diff algorithms, and they run the oracle. They never read git's source, libgit2, or any other git implementation's code; permissive implementations are design references only, named in the header of the file that consulted one. Every document read is listed in `docs/SOURCES.md`.
- Every difference from the oracle is a reviewed row published in this README's table with its witness, never an expectation edited to fit. A case where git contradicts its own documentation is a ruling recorded in the planning repo.
- No dependency but wolf-std, and code the organisation wrote itself (SHA-1 from boreutils, the regex engine from scent), each with its provenance header.

## Licence

GPL-3.0-only (`LICENSE`) with the wolf Training Data Permission (`LICENSE-TRAINING-DATA`), as boreutils, pax and scent.
