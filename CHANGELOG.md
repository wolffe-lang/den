# Changes

## Unreleased — local time zones

- `commit` no longer refuses a `TZ` other than UTC (den#84). A date den is
  not given takes the offset in force at that instant in the local zone, as
  Git does: `TZ`, or `/etc/localtime` when `TZ` is unset, read as Git's C
  library reads it: POSIX rules with daylight saving on both sides of a
  change, fixed offsets, zone names with and without a zone database, `:name`
  and paths.
- `tag -a`, `merge`, `stash`, `revert`, `cherry-pick`, `rebase`, `notes`,
  `branch`, `switch`, `reset` and every reflog line now write the local
  offset; before, they wrote `+0000` whatever `TZ` said.
- A `TZ` value the standard library refuses is read as the C library reads
  it, measured: an unreadable value is UTC, out-of-range offsets are held,
  a rule-less daylight zone takes the US rules, and the C library's
  readings of a missing daylight name, a missing or unreadable rule and
  bytes after a rule are reproduced. The few malformed rules den does not
  reproduce are refused by name, only when a date needs the local zone.
- Dates given without a zone (`--date`, `GIT_AUTHOR_DATE`,
  `GIT_COMMITTER_DATE`, amend's re-read author) are read in the local zone
  as Git reads them, including the skipped and repeated hours of a change;
  `@N` and bare epoch seconds below 100000000 are `invalid date format`, as
  in Git.
- `tools/zone-test.py` holds stamped, dated, wall-clock, amended,
  every-verb, shell-startup and seeded-corpus rows to the pinned Git.

## Unreleased — identities as Git reads them

- Clone, fetch, push, `upload-pack` and `receive-pack` validate no author,
  committer or tagger line, as Git's defaults do: a history holding
  `walker0643 <>` (i3's commit 5f453914) clones, as it does with Git.
  `fetch.fsckObjects`, `receive.fsckObjects` and `transfer.fsckObjects` set
  true are refused by name: den does not run Git's full object checks.
- `fsck` reports identity lines as `git fsck` does: the ten author/committer
  message ids and their text, the first one of each object, in Git's order,
  exit 1.
- `log`, `show`, tags and `blame` read identities from their stored bytes,
  split as Git splits them, with Git's dates for every stored form (zones
  outside the clock, years past 9999, dates it cannot read) and Git's fatal
  lines; a line Git cannot split prints as Git prints it.
- User formats: `--format=`, `format:` and `tformat:` with `%H %h %T %t %P %p
  %s %b %B %n %%` and the author and committer placeholders; any other
  placeholder is refused by name.
- Writing: an explicitly empty email is written as `<>`; an empty name is
  refused with Git's message, after its identity advice when it came from
  configuration; names and emails are cleaned as Git cleans them.
  cherry-pick and rebase keep a picked author's stored bytes; amend re-reads
  the author as Git does.
- `log -n` with no exclusion stops its walk after the count plus the skip:
  `log -1` reads one commit, and a history past the walk's 10,000 commits is
  no longer refused for a count.
- `tools/identity-test.py` holds every identity shape to the pinned Git, and
  `tools/identity-census.py` runs the checker, a clone and the readers over
  real histories; the live row clones i3's public repository.

## Unreleased — submodules

- Every reader knows a gitlink: `ls-tree` and `ls-files -s` (new, bounded),
  diff's `Subproject commit <id>` pseudo-blob with `-dirty`,
  `--submodule=short|log|diff`, `diff.submodule`, `--ignore-submodules` and
  `submodule.<name>.ignore`; status's long, short and porcelain v1 forms with
  Git's `(new commits, modified content, untracked content)` and its hint.
- `clone --recurse-submodules[=<pathspec>]` and `submodule status`, `init`,
  `update`, `sync` and `foreach`, with the layout Git writes:
  `.git/modules/<name>`, the worktree's `.git` file and `core.worktree`.
  Relative URLs resolve as Git resolves them (171 measured resolutions are
  units); a recorded commit no ref reaches is fetched by id.
- `url.<base>.insteadOf` and `pushInsteadOf` on every transport, and
  `protocol.allow`, `protocol.<name>.allow` and `GIT_PROTOCOL_FROM_USER`: a
  `file://` submodule is refused by default exactly as Git refuses it, while
  a `file://` clone the user typed still works.
- `add`, `commit -a`, `reset`, `checkout`, `switch` and `rm` handle gitlinks
  without entering a submodule; `rm` of a submodule removes its worktree and
  its `.gitmodules` section. `checkout` and `switch` print the local changes
  and tracking lines Git prints: a staged change too, by how the worktree
  differs from HEAD, and no list after `switch` or `checkout -b` names no
  start point. A staged change a switch keeps leaves its trees invalid in the
  index, as Git's does.
- `checkout`, `switch` and `reset` work in any clone: they run where
  branches have upstreams, held to Git over every transport by
  `tools/clone-work-test.py`. Making a tracking branch from a remote-tracking
  start point, or by guessing a remote's branch, is refused by name.
  `checkout <tree-ish> -- <paths>` is new. `stash` in a superproject is
  refused by name.
- `fetch` and `pull` fetch submodules on demand, by
  `--recurse-submodules[=yes|on-demand|no]`, `fetch.recurseSubmodules`,
  `submodule.<name>.fetchRecurseSubmodules` and `submodule.recurse`, nested
  submodules included, with Git's error list. `pull` merges a gitlink moved
  on one side through; both sides moved is refused by name.
- `checkout`, `switch`, `reset --hard` and `pull` with `--recurse-submodules`
  or `submodule.recurse` move the active submodules with the superproject,
  refuse first over a submodule's local changes unless forced, and empty a
  submodule the target drops.
- Live rows clone wolf-web with `--recurse-submodules` by both tools and
  compare every repository, and read wolf-interp's, wolf-std's and
  wolf-lsp's release-pinned gitlinks, over https (named SKIPs offline).
- Hostile `.gitmodules` input is refused or warned about as Git does:
  suspicious names, dash URLs and paths, missing URLs or commits, invalid
  values, bad config lines (`bad config line N in file ...`, naming the
  line Git names for a broken section header; a blank between a
  subsection's closing quote and its bracket is refused, as Git refuses it).
- A clone over a URL transport packs its remote-tracking refs, quotes a URL
  in `config` only when needed and leaves no empty `hooks/`, as Git does.
- `submodule add`, `deinit`, `set-url`, `set-branch`, `summary`,
  `absorbgitdirs`, `push --recurse-submodules`, `update --remote`,
  `--merge` and `--rebase`, and clone's `--shallow-submodules` are refusals
  by name.
- `tools/check-submodule` runs the units and every row family natively and
  in release; the gate runs it after the everyday step.

## Unreleased — everyday wire gaps

- Push places a short destination as git-push(1) does (den#71): each source
  resolves first by gitrevisions(7)'s order (`src refspec X does not match
  any`, `matches more than one`), a short destination is the one remote ref it
  names (`dst refspec X matches more than one` for two), else the source's
  `refs/heads/` or `refs/tags/`, else Git's refusal with its type-specific hint.
  A source no longer has to be a branch or tag: object ids, `X~0` and remote
  tracking refs push to a full or remote-matched destination.
- Clone with no directory clones into the URL's humanish name, `NAME.git`
  under `--bare` (den#72); an existing empty directory is filled; an occupied
  destination refuses with Git's diagnostic; an empty repository's clone
  prints Git's warning; operand errors are named refusals. A local clone finds
  `PATH`, `PATH/.git` or `PATH.git`, and honours the source's `lsrefs.unborn`.
- `ls-remote` (den#68) over ls-refs on every transport: `--heads`/`--branches`,
  `--tags`, `--refs`, `--symref`, `--exit-code`, `-q`, `--upload-pack` and
  tail-matched glob patterns, with Git's output and exit codes.
- `rev-parse` (den#69): revisions, `--verify`, `-q`, `--abbrev-ref`,
  `--symbolic-full-name`, `--short`, `--show-toplevel`, `--git-dir`,
  `--absolute-git-dir`, `--is-inside-work-tree`, `--is-inside-git-dir`,
  `--is-bare-repository`, `--show-prefix`, `--show-cdup` and `--`. The revision
  grammar resolves `B@{upstream}` and `@{u}` with Git's refusals. Discovery
  honours `GIT_CEILING_DIRECTORIES`.
- `fetch REMOTE REFSPEC...` for a configured remote (den#70): full and short
  sources, globs, negative refspecs, `tag NAME`, no destination, `+` and `-f`,
  Git's fast-forward and tag-clobber rejections, the opportunistic
  remote-tracking update, followed tags, FETCH_HEAD and Git's report.
- Clone memory (den#63): the issue's quadratic was gone since the streamed
  indexer; what remained was linear but large, from the pack index parsed per
  read outside a reader and kept outside a region, and from the closure walk's
  queue of names. The idx parse keeps one name an object, tree walks reclaim
  their readers, and the closure walk queues ranks.
- Clone CPU (den#63): a checkout, switch, reset, restore or merge abort reads
  its blobs through one reader, so the pack index is parsed once rather than
  twice for every file written; a read through an opened reader re-checks its
  pack's size, header and trailer binding without rescanning every offset. A
  reader whose packs cannot open up front still serves loose objects, and
  fails a packed read with the error a single read gives.
- Checkout syncs (den#63): checked-out files and their directories are no
  longer synced one by one, as the pinned Git syncs none and git-config(1)'s
  core.fsync names no component for them; the received pack, refs, the index
  and the configuration keep their syncs.
- No fixed object count on the wire (den#73): serving a clone or fetch,
  pushing and receiving a push have no 10,000-object bound and no aggregate
  body cap. The closure walk reads through one reader whose cache rebuilds a
  delta chain's bases once, keeps its sets hashed and each object as bytes and
  ints; the served or pushed pack streams to a temporary and goes out in
  windows; a pushed pack goes through the streamed indexer and is kept as a
  pack at 100 objects or more, as Git's receive-pack keeps it. The protocol's
  want, have, ref and command counts are gone; each request stays bounded in
  bytes. Deflate keeps its match tables across a writer's objects and builds
  its codes in linear time, inflate builds its tables in one pass, and the delta
  encoder rolls its fingerprint, each with the same bytes as before.
- `tools/wire-gaps-test.py` holds push, clone, ls-remote, fetch and clone
  memory to the pinned Git on every transport, a pelt clone's CPU to at most
  ten times the pinned Git's, and that clone's sync calls to Git's (Linux);
  its scale rows clone, fetch, push and serve 50,000 objects and i3's public
  history with Git's result under 64 MiB plus 1 KiB an object, and hold
  serving and den's own clone of 50,000 objects to at most 30 times Git's CPU;
  `tools/rev-parse-test.py` holds rev-parse. The oracle's `rev-parse` case is a parity row and
  `rev-parse-parseopt` keeps the strict not-yet witness.

## Unreleased — den clones itself

- Clone and fetch stream the fetch response to a temporary under
  `objects/pack` and index it there, as `git index-pack` does: no response,
  HTTP body or pack is held in memory, so a pack of any size crosses the wire
  (den#61). Deltas resolve depth-first from disk with the bodies on the walk's
  path bounded at 96 MiB; peak memory follows the largest object, not the pack.
- The whole-pack wire cap is gone (R-vc23-1); a failed write refuses by name
  and removes the temporary. Objects cap at 512 MiB (R-vc23-2), refused by name
  as `pack object size limit`, and the pack reader's per-object cap rises from
  16 MiB to the same value, so a clone checks out what it indexed.
- A clone keeps the received pack with its idx and reverse index (`.rev`),
  byte-identical to Git's, and so does a fetch of 100 objects or more; a
  smaller fetch becomes loose objects. The fetch asks for no
  thin pack, so every installed pack is self-contained. A plain local path
  clone loses its 128 MiB copy cap.
- A checkout holds one file's body at a time.
- `tools/large-pack-test.py` clones a pack over 128 MiB on every transport,
  under a hard address-space cap, and refuses an object over the cap; the
  live rows clone den's own repository and compare it with Git's.
- The live push row keeps the fixture's URL off every child's argv, checked
  against `/proc/<pid>/cmdline`: den reads a remote named in the environment,
  and the server's own advertisement replaces `git ls-remote`.
- The oracle runs its Git with `maintenance.autoDetach=false` and refuses an
  invocation whose automatic maintenance detaches: the field leg's
  intermittent commit rows were a snapshot catching the detached child's
  `objects/maintenance.lock` (den#66). The pinned environment is unchanged.

## Unreleased — smart HTTP

- Clone, fetch and push over smart HTTP and HTTPS: `info/refs` discovery,
  protocol v2 `ls-refs` and `fetch` POSTs, receive-pack push with the status
  report, leases, atomic pushes and side-band-64k. Accept discovery as direct
  v2 or as the matching `# service=` banner, flush and v2; refuse the dumb
  protocol, v0/v1 advertisements and mismatched banners by name.
- A bounded HTTP/1.1 client: Content-Length and chunked bodies, trailers,
  informational responses, persistent connections and named caps on header
  lines, blocks, fields and bodies. Each read's buffers and TLS records are
  freed when the read ends, so a body peaks at about three times its size.
- HTTPS over the standard library's public-PKI TLS client, pinned at wolf-std
  `d4a4d4c`: roots from `--tls-roots=PATH` or `DEN_TLS_ROOTS` (concatenated
  DER), host entropy, the UTC clock, SNI and name checks. No insecure mode;
  plain `http://` only for literal loopback addresses.
- Basic authentication from `DEN_HTTP_USER`/`DEN_HTTP_TOKEN` or a no-echo
  prompt, bound to the original origin; `credential.helper` and other `http.*`
  settings refused. Discovery follows up to five same-scheme redirects.
- A failed clone removes the directory it created, as Git does.
- ssh sends a plain program word bare, as Git does (`git-upload-pack '/path'`),
  so services that parse the command, such as GitHub's, accept it; any other
  `--upload-pack=`/`--receive-pack=` value stays quoted as a literal executable.
- `tools/check-http` joins the gate after the wire gate, with live github.com
  rows that SKIP by name without network.
- Keep test PKI out of the uploaded evidence, and check at the end of both gates
  that every uploaded file is readable by another user and holds no private key.

## Unreleased — daily use

- Plan remaining generated inputs before pruning, with a red-first runner
  regression for clients shared by reviewed and strict reports.
- Check the live SSH leg's host and fixture root against the explicit plan
  before any network access, keeping the earlier default when none is planned.
- Render fixed dates without a zone database and fall back to UTC for missing
  zones, preserving explicit stored offsets.
- Add short/full/no/terminal-auto history decorations, `log.decorate`, HEAD
  arrows, tags and remote-tracking refs in measured order, with the default
  terminal colour palette.
- Add local/global/file config set, add, unset, unset-all and replace-all,
  preserving unrelated bytes and modes under an exclusive atomic lock/rename.
  Keep system writes and unimplemented option families named refusals.
- Gate retained config bytes, terminal/pipe output, no-database containers and
  actual-checked config-writer units alongside the inherited regression suite.

## Unreleased — M1 loose objects

- Pin wolf 0.2.36, lupin 0.1.58 and the bundled std `78b9d3cb`;
  `den --version` names the wolf that builds it.
- Add algorithm-tagged OIDs, bounded loose-object read/write with independent
  checksum/framing/oid validation, and atomic no-replace publication.
- Preserve binary tree names, ordered parents, unknown multiline headers and
  message bytes through object parsers/builders.
- Add the measured init/hash-object/cat-file/mktree/commit-tree/mktag subset
  and write-tree over Git-written flat index v2; index writing remains deferred.
- Gate 57 exact parity rows, 28 named not-yet rows, two checked programs,
  external-client interop, corruption, races, failures and memory scaling.
- Reproduce measured invalid-UTF-8 commit repair at the CLI only; generic
  object APIs stay byte-preserving. Document unsupported features explicitly.

## M1 codec

- Add original RFC 1950/1951 inflate, Adler-32 and bounded lazy LZ77 encoding
  with stored/fixed/dynamic block selection. Support levels 0, 1 and default -1;
  refuse other levels and dictionaries by name. Enforce output limits and
  report stream consumption without swallowing following objects.
- Gate independent zlib/Git interop, all block/malformed classes, native,
  release and actual checked programs, deterministic fuzz and corpus size.
- Add named loose-object raw-byte/oid comparison while retaining exact
  comparison for every other repository artifact. No VCS command added.

## M0

- Pin wolf 0.2.35, lupin 0.1.56, bundled std and signed Git 2.56.0 oracle.
- Add explicit command refusals, surface probes, clean-room format map,
  reproducible corpus and byte-exact differential/review harness.
- Add tiered CI, a reproducible static-build tool and unpublished packaging
  drafts. No VCS command is implemented yet.
