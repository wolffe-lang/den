# Sources

Clean-room record for den. Git implementation files were never opened. The
oracle builder invokes `make` on the verified tarball; only documentation is
extracted for reading. No other Git implementation was consulted. The prose
below is original, not copied from the references. Raw AsciiDoc is from the
same signed Git 2.56.0 tarball pinned in `den-oracle.toml`.

## Git documentation consulted

| Page | Sections read and used |
|---|---|
| gitrepository-layout(5) | Description; objects, refs, HEAD, config, hooks, index, info, logs, worktrees; included technical/repository-version.adoc, Versions 0 and 1 |
| gitformat-index(5) | File header; Index entry; Extensions (all named subsections, including sparse directory entries) |
| gitformat-pack(5) | Checksums and object IDs; pack files, Object types/encoding, Size encoding, Deltified representation and instructions; idx v1/v2; rev and mtimes introductions |
| gitformat-commit-graph(5) | Description; header, chunk lookup/data, trailer and historical notes |
| gitformat-bundle(5) | Format, Semantics, Capabilities |
| gitformat-loose(5) | Loose objects; loose-object mapping (deferred) |
| gitformat-signature(5) | Description; Tag signatures; Commit signatures; Mergetag signatures introduction |
| gitprotocol-common(5) | ABNF notation, reference-name restrictions, pkt-line format |
| gitprotocol-v2(5) | Packet-line framing; Initial Client Request and transports; Capability Advertisement; Command Request; agent; ls-refs; fetch request and response; server-option; object-format; session-id |
| gitprotocol-pack(5) | Description; pkt-line; Transports; Extra Parameters; Git/SSH transports; Packfile Negotiation (want/have, shallow, ACK); Packfile transfer; push command grammar, Report Status |
| gitprotocol-capabilities(5) | Description (v0/v1); multi_ack, multi_ack_detailed, no-done, thin-pack, side-band/64k, ofs-delta, agent, object-format, symref, shallow/deepen, no-progress, include-tag, report-status and report-status-v2 |
| git-config(1) | Configuration file via config.adoc: Syntax, Includes, Conditional includes |
| gitignore(5) | Description/precedence, Pattern Format, Configuration, Notes, Examples |
| gitrevisions(7) | Included revisions.adoc: Specifying Revisions, Specifying Ranges, exclusions, two/three-dot ranges and parent shorthands |
| githooks(5) | Description; applypatch hooks; pre-commit, pre-merge-commit, prepare-commit-msg; all hooks deferred |
| Git user manual | The Object Database: Commit Object, Tree Object, Blob Object, Tag Object; Object storage format. The following source-code overview was NOT read. |
| git-mktree(1) | Description, Options (ordering is normalized by the oracle) |
| git-commit-tree(1) | Description, Options, Commit Information; included date-formats.adoc and i18n.adoc |
| git-mktag(1) | Description, Options, Tag Format |

Nineteen Git pages/manuals plus their named includes. These are the consulted
sections, not a claim to have read every line of every manual page. Porcelain
examples are black-box measurements, not prose-derived goldens.

## Specifications

- RFC 1950, https://www.rfc-editor.org/rfc/rfc1950 : sections 2.1–2.3,
  especially CMF/FLG, dictionary flag, Adler-32 and rejection requirements.
  Section 5's checksum security note. No implementation linked there read.
- RFC 1951, https://www.rfc-editor.org/rfc/rfc1951 : sections 3.1/3.1.1,
  3.2.1 introduction, 3.2.3–3.2.7: bit packing, block types, stored lengths,
  literal/length and distance codes, fixed and dynamic trees.
- FIPS 180-4 sections 4–6 are the normative provenance of the org-own SHA
  implementation. This lane inherited its standard-answer vectors from
  boreutils' checksum tests; it did not independently read the FIPS PDF.
  A later algorithm change must consult the primary specification directly.

## Organisation-owned references

- `wolf/sprints/vcs/{index.md,vc00-the-map.md}`, `sprints/RULES.md` §§1–10,
  `AN_AGENTS_GUIDE_TO_WRITING_GOOD_WOLF.md` in full: contract, clean room,
  milestones, report and checked-machine commands.
- aspen `476edee3`, `tools/{lib-toolchain.sh,fetch-toolchain,build,check-fmt}`,
  `ci/{tiers.py,tiers-test.py,nightly-red.sh}` and workflow: scaffold shape.
  The local aspen checkout was initially `5f99a37`, whose scaffold had been
  reduced; scent's preserved tools supplied the build scripts.
- scent `b6f63a4`, toolchain/oracle TOML, `tools/{fetch-toolchain,lib-toolchain.sh,
  lib-toml.sh,build,check-fmt,check-test,in-container,mkscent,oracle-review.py}`,
  `ci/oracle.Containerfile`, CLI and manifest, packaging formula and PKGBUILD.
  Adapted files name the own-code origin in their headers.
- lope `bc388673`, `packaging/{lope.rb,PKGBUILD}`: draft packaging shape.
- boreutils `f87dc76`, `src/checksum/{sha.lu,digest.lu}`: SHA-1 round function
  vendored and streaming adapter narrowed to SHA-1. The requested `575dc7b`
  predates these files (proposed correction `R-vc00-1`).
- wolf-std `2386522e`, `std/{fs/fs,net/net,process/process,time/time,time/local,
  term/term,x/tls/client/client,x/tls/cert/cert,x/crypto/sha2/sha2}.lu`:
  public signatures, relevant bodies and contracts, not third-party source.
- wolf-lang `cf0c13d3`, `spec/11-os.md`, clauses os.proc.fds, os.fs.open,
  os.fs.lock, os.fs.fstat.record and the builtin synopsis.
- muzzle README and `docs/LEDGER.md`: read only; no dependency taken.
- Deflate-name census in wolf-std, lobo, pax and boreutils: exact revisions,
  search expression and matches in `notes/vc00-evidence/compression-census.txt`.

## Verification services and black boxes

- GitHub release API for wolf v0.2.35 and lupin v0.1.56: two independent reads
  per release, raw responses in the evidence directory.
- kernel.org Git tarball/signature; Ubuntu keyserver public maintainer key.
  The exact key bytes are vendored because keyserver responses can reorder
  signatures. Fingerprints and every digest are pinned; a cryptographically
  valid signature is not a claim of a Web-of-Trust certification.
- Git 2.56.0 CLI; Python stdlib zlib (container zlib 1.3) as a compression
  black box; OpenSSL CLI as a TLS server; system trust roots as data only.

## Codec derivation (vc01)

- RFC 1950 §§2.1–2.3 read fully: byte order, CMF/FLG/FCHECK,
  FDICT refusal, Adler-32 recurrence and compliance. Adler is derived from
  the two modular sums in §2.2, not the appendix's sample C (not read).
- RFC 1951 §§3.1–3.2.7 read fully, including §3.2.2 canonical-code
  ordering and §3.2.7's single-symbol/empty distance cases. Tables and
  algorithms are original implementations of the stated format, not copies
  of the RFC's sample routines or of any codec implementation.
- FIPS 180-4 §§4.1.1, 5.1.1, 5.2.1, 5.3.1 and 6.1.1–6.1.2 read from
  https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf for the inherited
  SHA-1 object's framing and known-answer tests; no hash algorithm change.
- Git gitformat-pack(5), pack header, entries, object/size encoding and
  deltified representation; Pro Git 2nd edition §10.2, Object Storage:
  https://git-scm.com/docs/gitformat-pack and
  https://git-scm.com/book/en/v2/Git-Internals-Git-Objects.
- Python zlib and the pinned Git are independent black-box test oracles only.
  No zlib, miniz, libdeflate, zlib-ng, Git or other codec/VCS implementation
  source was consulted; no external codec is linked or invoked by den.

## Object store derivation (vc02)

Primary documentation read before implementation, Git v2.56.0 documentation
only (raw.githubusercontent.com/git/git/v2.56.0/Documentation):

- gitrepository-layout(5), Description and named entries, including gitfiles;
  technical/repository-version.adoc, Versions 0 and 1.
- gitformat-loose(5), Loose objects and Loose object mapping (mapping deferred).
- git-init(1), Description, Options, Template Directory; empty-template policy.
- git-hash-object(1), Description and Options; git-cat-file(1), Description,
  Options, Output and Batch Output (batch deferred).
- git-mktree(1), Description and Options; git-write-tree(1), Description and
  Options; gitformat-index(5), File header, Index entry and Cache tree extension.
- git-commit-tree(1), Description, Options, Commit Information; date-formats.adoc
  and i18n.adoc in full. git-mktag(1), Description, Options and Tag Format.
- gitformat-signature(5), Description, Tag signatures, Commit signatures and
  Mergetag signatures: SP-prefixed continuation lines, not signature checking.
- Git user manual, The Object Database (commit/tree/blob/tag) and Object storage
  format only; no source-code overview consulted.
- Pro Git 2nd edition §10.2, Git Objects, Tree Objects, Commit Objects, Object
  Storage, https://git-scm.com/book/en/v2/Git-Internals-Git-Objects; read the
  documentation, did not copy its illustrative Ruby.
- FIPS 180-4 §§4.1.1, 5.1.1, 5.2.1, 5.3.1, 6.1.1–6.1.2, printed pages
  10, 13–14, 18–20; https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf.
  SHA-1 implementation remains den's merged, provenance-marked hash module.

## Index and worktree derivation (vc03)

Primary references are Git v2.56.0 Documentation, read as documentation only:

- git-config(1), get, Files, Scopes and Environment; config.adoc, Syntax,
  Includes and Values. Sections/subsections, implicit booleans, quoting,
  escapes, continuations and precedence are checked against the binary.
- gitformat-index(5), File header, Index entry, Cache tree, Resolve undo,
  Split index, Untracked cache, File System Monitor cache, End of Index Entry,
  Index Entry Offset Table and Sparse Directory Entries.
- gitignore(5), Description, Pattern Format, Configuration, Notes, Examples;
  git-check-ignore(1), Options, Output and Exit Status. The two documented
  contradictions and their exact binary witnesses are retained in FORMATS.
- git-add(1), Description and Options; git-rm(1), Description, Options and
  Examples; git-mv(1), Description and Options; git-status(1), Description,
  Options, Output (short/porcelain v1), Configuration and Background Refresh.
- git-commit(1), Description, Options, Commit Information, Files and Hooks;
  date-formats.adoc in full; config/core.adoc, core.commentChar/commentString.
- git-restore(1), Description, Options and Examples.
- The inherited oid/repository/object/hash/zlib modules and their API clients
  are the only implementation references; no external VCS implementation,
  sample hook or template source was read. The full-stat and nofollow contracts
  were checked in wolf-lang cf0c13d spec/11-os.md and bundled wolf-std 2386522e.
  Current std wrappers are not assumed present in that pinned bundle.
- githooks(5), Description only: executable hooks, default hooks directory,
  core.hooksPath and working directory; no sample hooks/templates consulted.
- gitrevisions(7), included revisions.adoc, HEAD definition and @ shorthand only.
- Pro Git 2nd edition, section 2.2, Recording Changes to the Repository:
  Checking the Status of Your Files, Short Status, Staging Modified Files,
  Ignoring Files, Committing Your Changes, Skipping the Staging Area,
  Removing Files and Moving Files; https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository.
