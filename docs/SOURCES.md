# Sources

Clean-room record for den. Git implementation files were never opened. The
oracle builder invokes `make` on the verified tarball; only documentation is
extracted for reading. No other Git implementation was consulted. The prose
below is original, not copied from the references. Raw AsciiDoc is from the
same signed Git 2.56.0 tarball pinned in `den-oracle.toml`.

## Blame attribution (vc11)

Read only versioned Git v2.56.0 documentation before implementation:

- `Documentation/git-blame.adoc`: Synopsis, Description, Options, Specifying
  Ranges, Porcelain Format, Incremental Output, Mapping Authors and Configuration.
- `Documentation/blame-options.adoc`: line ranges, boundaries, root, dates,
  first-parent/reverse traversal, porcelain/line-porcelain, moved/copied lines,
  ignored revisions, alternate contents and display options.
- `Documentation/line-range-format.adoc`: absolute endpoints, signed end
  offsets, regex search anchoring and function-name range semantics.
- `Documentation/config/blame.adoc`: boundary/root, dates, email, coloring,
  ignore-revision files and ignored/unblamable markers. Unsupported controls are
  refused, not silently ignored.
- URLs use `https://raw.githubusercontent.com/git/git/v2.56.0/` followed by
  those documentation paths. No implementation link was followed. No new
  gitformat-* or gitprotocol-* parser was introduced.

Only den's own revision, raw commit/object/path, packed-store, line/Myers/diff,
rename-pairing, date and quoting APIs supplied implementation boundaries. The
oracle was built afresh through `tools/fetch-oracle` at `/work/den` and its full
c4848492… executable digest asserted before every observation. Git source was
built, never opened. No Git/libgit2/VCS/matcher source was read and no production
subprocess or new dependency was added.

`tools/blame-test.py` independently creates raw commits, ordered merges, exact
and edited renames, raw-byte paths/content, generated unique-line histories and
reuses ten original corpus fixtures used by vc09. Complete stdout/stderr/status
and immutable file/symlink/directory-mode state are compared on loose and packed
copies. Retained reds corrected ordinary final-LF identity and whole-file-equal
second-parent priority; oracle expectations were not altered. Repetition and
reordering heuristics remain explicit non-parity refusals.

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


## Similarity derivation and diff experiment (vc04)

- Git v2.56.0 documentation only: git-diff(1), synopsis and endpoint forms;
  diff-format.adoc, raw and other formats; diff-generate-patch.adoc, extended
  headers and unified patches; diff-options.adoc, context, indent heuristic,
  stat widths, binary/full-index and rename/copy options; gitdiffcore(7), chain
  of operation and rename/copy candidate stages. These pages do not specify
  the fingerprint recurrence or projection constants; those were measured.
- Myers, *An O(ND) Difference Algorithm and Its Variations*, sections 1–3,
  especially the edit graph, Figure 2 and trace recovery; original paper at
  https://neil.fraser.name/writing/diff/myers.pdf. No diff library source or
  Git implementation was consulted. The experiment uses the paper's greedy
  method and original boundary-compaction hypotheses, not Git heuristics.
- The six vc03 black-box reports supply 1,510 pairs. An explicit search of
  348 rolling-fingerprint models fits 1,157 small witnesses, then tests the
  complete corpus. Only 64-bit left rotation by seven with addition restricted
  to the low 32-bit word agrees on every inherited pair.
- Fresh pinned-Git threshold probes isolate 24 unequal 64-byte pairs that
  collide after projection despite distinct full fingerprints. Each query is
  retained. Searching both word orders, three arithmetic widths and all
  coefficients 0–65,535 against 16 pairs leaves one model: low + 97 * high,
  truncated to 32 bits, modulo 107,927. The other eight pairs validate it.
  Scripts, source/input hashes, observations and rejected candidates are in
  tools/rename-{fingerprint,collision,projection}-measure.py and the evidence.
- A documentation discrepancy remains for review: diff-generate-patch.adoc
  says 100-percent similarity is reserved for equal files, but the retained
  unequal repeated-byte and isolated-collision witnesses report R100. The
  implementation follows the measured content score, not that identity claim.
  This is a proposed documentation correction, not an upstream submission.


## Diff integration references (vc04 continuation)

- Git v2.56.0 glossary-content.adoc, pathspec: literal, top, icase, glob,
  exclude and the attribute boundary; original byte-DP adapter, not another
  matcher's source. Git config/diff.adoc, diff.autoRefreshIndex and diff stat
  controls. The refresh side effect was measured on copied/stale indices,
  including disabled refresh, foreign locks, paths, quiet and cached forms.
- Git revisions.adoc, first-parent tilde and selected-parent caret notation;
  the endpoint adapter is bounded and does not implement ranges or a walk.
- Binary delta instructions use gitformat-pack(5); the envelope and base85
  alphabet/framing were measured against pinned Git. Existing own zlib code
  supplies level-1 deflate. Python stdlib zlib/base64 are independent test
  decoders/oracles, not implementation references or runtime dependencies.
- Pairing measurements include exact/type/basename precedence, four-candidate
  destination shortlists, slot-order ties and unused-source-before-copy
  assignment. Preserved disagreement logs drove general corrections; no
  fixture-specific pairing exceptions were introduced.
- No Git, libgit2, other VCS, diff library or external codec source was read.
  `notes/vc04-evidence/pins/` contains two fresh release-metadata reads; no
  compiler, std, archive or oracle pin changed.
- The pinned wolf-std `term/term.lu` size contract and its `os_term_size`
  wrapper were read for stat-width defaults. The command queries the builtin
  directly, without importing foreground-process operations or adding an exec
  capability. Private-PTY and COLUMNS tests use only terminals they create.


## History walking and presentation (vc05)

Read from the pinned Git 2.56.0 tarball's Documentation directory only:

- git-log(1), Synopsis, Description, Options, revision/path arguments and Diff
  Formatting (default merge-patch suppression).
- git-show(1), Synopsis, Description, Options, Diff Formatting and Examples:
  object-kind display and dense-combined merge semantics.
- pretty-formats.adoc, introduction, merge-parent line, oneline, short, medium,
  full and fuller formats. Custom format placeholders were not implemented.
- rev-list-options.adoc, Commit Limiting (max-count and skip), Commit Ordering
  (default, date/author-date/topological ordering, reverse), and --date formats.
- Existing own object/header, commit human/reflog subjects, worktree HEAD and
  diff consumer APIs. No new gitformat-* or gitprotocol-* format was introduced;
  the inherited parsers and their cited format documentation remain the source
  of raw object validation.

`tools/history-measure.py` retains black-box whitespace, timezone, empty-message,
NUL, ordered-parent and tag/tree observations. `tools/history-test.py` constructs
raw commits independently through the pinned executable, including tied/skewed
DAG clocks, without loading any Git implementation source. Native/release
results bind complete stdout/stderr/status and immutable repository/worktree
state. Non-ASCII tab widths and combined merge diffs are refused, not guessed.

## Refs and branch transitions (vc06)

Git v2.56.0 documentation pages read from the versioned Documentation URLs;
only documentation was opened, never implementation files:

- gitrepository-layout(5), Description: refs, packed-refs, HEAD and logs.
- git-check-ref-format(1), Description and Options: full refname restrictions
  and the stricter branch-name edge.
- git-pack-refs(1), Description: packed fallback and loose writes after packing.
- git-update-ref(1), Description, transaction commands and Logging Updates:
  expected old OIDs, exclusive preparation and reflog fields.
- git-symbolic-ref(1), Description, Options and Notes: textual symbolic refs,
  dereferencing and detached HEAD.
- git-branch(1), Description and Options: create/force/delete/rename, listing,
  safety and reflog behavior. Tracking remains outside this lane's surface.
- git-tag(1), Description, Options and Files: lightweight versus annotated
  objects, message cleanup, force/delete, optional reflogs and editor boundary.
- git-switch(1), Description and Options: transactional creation, detached HEAD,
  dirty-worktree protection and force behavior.
- git-checkout(1), Description, branch-related Options, Detached HEAD and
  Argument Disambiguation. Existing explicit path checkout remains vc03's.
- git-reset(1), Description and Options: soft/mixed/hard, ORIG_HEAD and refresh.
- git-reflog(1), Description and Options: HEAD records branch switching; reflog
  management/expiry and revision selectors are not implemented here.

No new gitformat-* or gitprotocol-* parser was introduced. Packed-refs header
traits and peeled lines were measured with the pinned executable alongside the
layout/pack-refs documentation. The inherited object and index format sources
remain authoritative for those parsers.

`tools/refs-measure.py`, `refs-tag-log-measure.py`, `refs-tag-date-measure.py` and
`refs-cleanup-measure.py` retain original black-box experiments. They distinguish
current-branch rename's two HEAD log records, same-OID attached/detached reset,
tag subjects/UTC committer dates, and repeated AUTO_MERGE cleanup attempts.
The first detached matrix accidentally prepared two different index timestamps;
the corrected harness copies one prepared fixture to both tools, without
changing or normalizing expected bytes. The original red captures are retained.

Implementation references are only den's own object/header, commit identity,
index transaction, worktree installation, history abbreviation and walk APIs.
There is no subprocess, Git, external VCS or codec implementation in production.
The signed oracle source was built without opening implementation files.
Building the identical pinned image at `/work/den`, rather than `/work`, was
necessary to reproduce the unchanged oracle binary SHA-256.

## Merge and revert (vc07)

Read only the versioned Git v2.56.0 Documentation pages before implementation:

- git-merge(1), Description, Options, Pre-merge Checks, Fast-forward Merge,
  True Merge, Merging Tag, How Conflicts Are Presented and How to Resolve
  Conflicts. True Merge specifies stages and AUTO_MERGE; Options describes abort.
- merge-options.adoc, commit/no-commit, edit/no-edit, fast-forward controls,
  messages, squash, statistics, strategies and unrelated histories.
- merge-strategies.adoc, ort, recursive virtual ancestor trees, rename handling
  and the histogram default; other strategies remain outside this surface.
- git-merge-base(1), Description, Operation Modes, Options and Discussion:
  all best common ancestors, dominance and criss-cross ambiguity.
- git-revert(1), Description and Options: inverse changes, root/single commits,
  no-edit/no-commit and the mainline requirement for merge commits.
- git-merge-file(1), Description, Options and Examples: marker labels,
  conflict counts, merge/diff3/zdiff3 and its distinct Myers default.
- git-read-tree(1), Merging: 3-way stages, trivial collapse and index safety.
- gitformat-index(5), Index Entry and Resolve Undo: stage flags, sorted paths,
  REUC pathname, three octal modes and optional object IDs.
- gitrepository-layout(5), Description: objects, refs, packed-refs, HEAD and
  configuration. Merge-state file semantics come from git-merge above.

No new gitprotocol-* page or parser was used. The only implementation references
were den's own object/walk, index, worktree, commit, diff and rename boundaries.
The signed oracle source was built without opening implementation files.

Independent black-box fixtures measure commands and all resulting files; the
file client tests generated edit triples, and the base client constructs DAGs
through commit-tree. Early captures exposed nearby-conflict coalescing, literal
full-ref message labels, revert's direct commit path and its retained AUTO_MERGE.
Dirty true merges also create internal recovery objects and transient index
metadata. Those inputs now refuse without mutation and remain named non-parity
captures; no files were excluded or oracle expectations changed to excuse them.
The default tree consumer refuses repeated-base-line and multi-hunk ambiguity
rather than claiming the file API's Myers result is generally ort-compatible.

## Cherry-pick, rebase and sequencer (vc08)

Read the versioned Git v2.56.0 Documentation pages, not implementation files:

- git-cherry-pick(1), Description, Options (authoring, empty commits, redundant
  commits and no-commit), Sequencer Subcommands and Examples.
- git-rebase(1), Description, Transplanting a Topic Branch with --onto, Mode
  Options, Options, Behavioral Differences, Interactive Mode and Rebasing Merges.
  Interactive, apply and real-merge replay remain named refusals.
- git-revert(1), Description, Options and Sequencer Subcommands; sequencer.adoc
  in full for continue, skip, quit and abort semantics.
- gitrepository-layout(5), Description, especially HEAD, refs and logs. This
  page does not specify the sequencer/rebase metadata schema; those bytes were
  measured, not attributed to an absent documentation section.
- git-commit(1), Commit Information, Environment and Configuration Variables,
  and Files: source author versus current committer, editor selection and
  COMMIT_EDITMSG lifetime. Existing identity/date parsers remain shared.
- git-reflog(1), Description and Options, especially HEAD's branch-switch records.

No new gitformat-* or gitprotocol-* parser was introduced. Existing object,
index/REUC, ref and worktree documentation remains authoritative. Implementation
references are den's own walk, mergetree/file, index, refs, commit and diff APIs;
there is no Git, shell, Python or external codec dependency in production.

The independent replay matrix captures every intermediate process's output,
status and complete repository/worktree state. Measurements distinguish direct
and continued cherry-pick messages/reflogs, initially empty versus redundant
commits, progress files, rebase's inert author-script, hard versus merge-style
recovery, and ref failures after index/worktree publication. Rebase backup-help
text is measured command output, not copied implementation source.

The initial generic commit guard still rejected CHERRY_PICK_HEAD; retained reds
led to its measured removal. Further retained discrepancies corrected object
publication before dirty/untracked errors, empty direct-path COMMIT_EDITMSG,
index refresh on early exits, recovery diagnostics and failure cleanup order.
Foreign AUTO_MERGE locks and dirty cherry-pick recovery expose stat values from
an earlier observation than the inherited stat proof permits. They now refuse
before writes rather than excluding the index or inventing a proof.

Default rebase uses an original conservative net-line checksum only to refuse
possible upstream patch equivalence. It is deliberately not a patch-id
implementation: path/order omissions and collisions can refuse extra inputs,
never discard commits. Explicit reapplication is measured separately. Actual
editor-dependent continuation remains named; the resolution-commit-then-continue
workflow is compared exactly. No oracle expectation was rewritten to fit a
byte discrepancy.

## Packed object reading (vc09)

Read the Git v2.56.0 documentation URLs, never implementation sources:

- `Documentation/gitformat-pack.adoc`: Checksums and object IDs; pack header,
  entries and trailer; Object types, Object encoding, Size encoding; Deltified
  representation, copy/insert/reserved instructions and OFS offset encoding;
  version-1 trailer definition and complete version-2 index layout. The rev,
  mtimes, multi-pack-index and cruft descriptions were also read; those formats
  are not implemented by this reader.
- `Documentation/gitformat-index.adoc`: File header, Index entry and Extensions;
  especially the v4 reference to OFS_DELTA offset encoding. This is the worktree
  index document, not the source of the pack `.idx` layout.
- Existing den hash/zlib/object and history/refs/merge/replay APIs, vc04 and vc08
  notes, MAP/SOURCES and the tracked Wolf language guide. No Git, libgit2 or
  other VCS/codec implementation source was opened.

The pack reader and test encoder are original implementations of the format.
Python zlib/CRC32 and the pinned Git executable are independent test oracles,
not runtime dependencies. Git `gc`, `repack`, `pack-objects`, `index-pack`,
`cat-file`, `verify-pack` and `fsck` generate and inspect the fixtures. Synthetic
small packs exercise large-offset slots without claiming a multi-gigabyte test.
A probe of `index-pack --index-version=2,1` produced a tiny index the same Git
binary rejected as `wrong index v2 file size`; normal interoperability uses
`--index-version=2`, with the nondefault threshold behavior kept separate.

The first packed matrix exposed a harness error: repacking an already-packed
fixture without `--keep-unreachable` dropped its unreferenced commit. The fixture
builder now preserves and compares the entire before/after OID sets; command
expectations were not weakened. A structural offset witness was corrected to
mutate the first physical offset, not the first lexicographic name's offset,
so it isolates the intended first-entry invariant.

## Shared revision grammar (vc10)

Read only Git v2.56.0 documentation, never implementation sources:

- `Documentation/revisions.adoc`, included by gitrevisions(7): Specifying
  Revisions, full/prefix object IDs, documented refname search order and
  pseudorefs; numeric/date/previous-checkout/upstream/push selectors; ordered
  parent/ancestor chains, empty and typed peels, message searches, literal
  tree paths and index expressions. Specifying Ranges: exclusions, two-dot,
  symmetric three-dot, parent-set shorthands and the complete range summary.
- `Documentation/git-rev-parse.adoc`: Description, Options for Output
  (verify, quiet, symbolic and short forms), Options for Objects and Examples.
  The remaining parseopt/quoting documentation was read but not implemented.
- Versioned documentation URLs:
  https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/revisions.adoc
  and https://raw.githubusercontent.com/git/git/v2.56.0/Documentation/git-rev-parse.adoc.
- Den's own object/ref/HEAD/reflog, ordered raw commit parents, walk and diff
  APIs, plus vc09/vc08/vc06/vc04 notes. The existing lossless first-paragraph
  subject function moved unchanged from commit/support.lu into object/subject.lu;
  commit.subject remains a compatibility wrapper. Date formatting uses the
  pinned std.time UTC formatting surface, not an external implementation.

`tools/revision-test.py` constructs commits, tags, ref collisions, real short-OID
collisions, literal raw tree names and deterministic reflogs independently.
The pinned binary supplies expected successful and malformed/ambiguous process
results on loose and packed copies; every repository/worktree file remains in
read-only comparisons. Inherited refs/merge/replay harnesses independently
exercise mutation consumers and retain their original state/stat proof.
`hint-measure.py` retains commit/blob and tag/blob measurements: log selects a
unique commit-ish without a warning, while untyped rev-parse/cat-file remain
ambiguous. Hint dates, first-paragraph subjects, tag names and type ordering
are measured output, not rules attributed to prose that does not specify them.

An initial exploratory runner mistakenly selected the image's system Git 2.43
instead of the built oracle. Those provisional captures and identity files are
retained but not counted as Git 2.56 parity. The correct oracle was then built
at the pinned `/work/den` path, its c4848492… binary digest read twice, and the
revision harness now asserts its full pinned SHA256 before measuring anything.
No expectation was changed to fit that mistake. The later type/path diagnostic
and `heads/topic` merge-message counterexamples remain retained reds; correct
production behavior follows the independent pinned observations.
