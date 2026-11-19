# Changes

## Unreleased — blobs past 16 MiB

- `pull`, `merge`, `diff` (with `--stat`, `--cached` and between commits), a
  rename's score and `commit`'s summary read and count a file as large as an
  object read allows (1,000,000,000 bytes), as checkout and add already did.
  They stopped at 16 MiB (den#145): a pull of a repository whose 18 MB test
  oracle had grown past it fetched, then failed with `limit: an object larger
  than 16777216 bytes` and left HEAD where it was. Under 16 MiB, a diff, a
  commit or a true merge of a file past 200,000 lines stopped too.
- A commit's summary counts lines as a stat does, in space linear in the two
  bodies, where a table of every line pair stopped past 4,000,000 pairs.
- Memory: each object read keeps only the body it returns, a copy or a file
  read takes one buffer of its size, a commit's scans keep no bodies, a true
  merge builds each file's line tables once, and a commit's checks, a
  summary's pairs and a true merge's files are each reclaimed before the
  next. Over a 16 MB
  blob every row of `tools/large-blob-test.py` peaks within four times Git's
  peak plus 64 MiB, but `pull --rebase`, within six: a rebase scans the work
  tree several times, and each scan keeps the bodies of the files it reads.
- `pull --rebase`, a cherry-pick and each replayed commit read only the bodies
  that differ between the trees they compare, as a merge does, where every
  blob of three trees was read for each commit; `show` of a blob and a root
  commit's patch take one past 16 MiB.
- Rename scores of a body past 1 MiB sum their weights in slots, not a Map:
  one renamed 16 MB file took 100 s of CPU. A true merge finds a repeated
  line by its bytes, where two distinct lines whose hashes collided refused.
- The 2,000-line budget of a patch and of a three-way file merge is named
  when reached (Git has none), as is the 128 MiB of file bodies one diff
  holds. `tools/limit-test.py` holds the budget's two.
- The bounds kept as protections name their files: a commit or merge message
  past 16 MiB (`limit: the message file 'NAME' is larger than 16777216
  bytes`, and MERGE_MSG's path) and a configuration file past 1 MiB (`limit:
  the configuration file PATH is larger than 1048576 bytes`). Git takes both;
  `tools/limit-test.py` holds the two messages.
- A line count's totals are a minimal script's, Git's `--minimal`; where
  Git's default diff departs from minimal (a 486,000-line JSON file rewritten
  by a third), den's stat differs from Git's in that file's counts.

## Unreleased — symbolic links in pulls

- `pull` and `merge` carry symbolic links (mode 120000) as Git does: a link's
  blob is its target, so it is compared, counted in the change summary and
  checked out as a link like any other entry. Before, any tree holding a link,
  changed or not, stopped a pull after it had fetched with `merge nonregular
  tree entry` (den#137). A link changed on one side of a true merge is taken
  from that side; a link changed on both sides, or against a file, stays a
  named refusal (`merge of a symbolic link changed on both sides`).
- `tools/pull-test.py` holds to the pinned Git a fast-forward that leaves a
  link alone, retargets one, adds one and removes one, and a true merge that
  retargets a link on one side.

## Unreleased — change summaries of any size

- A stat, numstat or shortstat, and the change summary a pull or merge prints
  after it moves HEAD, count a file's lines with no bound on differing lines
  (den#105). They stopped past 2,000 with a named bound, after the pull had
  moved HEAD, so a caller saw a failed pull: a week of a public repository
  whose generated parser changed by 15,273 lines did. The counts are a
  minimal script's, found in space linear in the two bodies; that week's
  stat now matches Git's byte for byte in 0.3 s. `tools/summary-scale-test.py`
  holds pulls, merges and diffs past 2,000 differing lines to Git's output,
  and a generated table's to a multiple of Git's peak memory.
- A binary file's `Bin` in a stat stands right-aligned in the count column,
  as Git puts it; with a count of four or more digits beside it, den's row
  differed from Git's.

## Unreleased — pulls of a week's work

- A pull, merge, checkout or reset puts the index entries it writes in path
  order without copying them, and a diff puts its changes in path order the
  same way. Each was ordered by an insertion sort that copied every element
  it shifted, and every copy stayed until the command ended: a fast-forward
  pull of a week of a 10,000-file public repository (889 commits, 440 paths
  added beside 133 changed) peaked at 4.0 GB, 2.6 GB of it entry copies and
  1.2 GB copies of the summary's changes with their bodies, where Git peaks
  at 26 MB (den#138). It now peaks at 450 MB, and takes 7.5 s of CPU where it
  took 9.6 s (release; Git 0.9 s). `tools/pull-memory-test.py` holds such a
  pull, with and without its summary, to a multiple of Git's peak.

## Unreleased — clones Git made

- `pull`, `merge`, `commit`, `branch`, `tag`, `switch`, `checkout`, `reset`,
  `revert`, `cherry-pick` and `rebase` work in a clone Git made with its
  default template. Its `.git/hooks` holds only
  Git's disabled samples (`pre-commit.sample` and the rest), which Git never
  runs: githooks(5) enables one only by removing its `.sample` suffix. den
  counted any entry there as a hook it could not run and refused with
  `nonempty hooks directory`, after a pull had already fetched. Entries named
  `*.sample` no longer count; anything else in the hooks directory is still
  refused by name.
- `tools/pull-test.py` (`pull-ff-sample-hooks`) and `tools/commit-oracle.py`
  (`samples-message`) hold a fast-forward pull and a commit in such a clone to
  the pinned Git, with the pinned Git's own samples.

## Unreleased — status of large trees

- Reading an index checks its cache tree against the entries in near-linear
  time. Each directory's record was tested against every entry, and the
  records against one another, so an index of 100,000 entries in 10,000
  directories took den about a minute to read where Git takes 17 ms, and
  plain `status` of 10,000 files in 1,000 directories spent two fifths of its
  time there. `tools/index-scale-test.py` holds `ls-files` of that index to
  Git's CPU time and peak memory.
- The status walk finds a directory's gitlink entry by binary search. It
  scanned every index entry for each directory it met, so status of 20,000
  files, one in each of 20,000 directories, took 6.7 s where Git takes
  0.15 s. `tools/status-scale-test.py` holds that shape to Git's CPU time and
  peak memory.
- Opening a repository's packs no longer hashes each pack index whole or
  spells every object name in it in hex. An index keeps its name table as
  stored, and a name is spelled only when one is printed. Git's reads skip
  that checksum too; verify-pack and fsck still check it. Status beside
  390,000 packed objects took 0.71 s where Git takes a millisecond, and now
  takes 0.20 s. `tools/status-scale-test.py`'s objects shape holds it to Git's
  CPU time and peak memory.
- `status` keeps about what it needs. Nothing is freed before a region ends,
  so every outgrown list buffer, every lstat record, listing and absolute path
  of its walk, and its copies of the index stayed until it exited. Status of
  10,000 files in 1,000 directories peaked at 68 MB, nearly ten times Git's
  7 MB; it now peaks at 36 MB. Status of 20,000 files, one in each of 20,000
  directories, went from 230 MB to 137 MB. A pack file's byte range is read
  into one buffer of its size, where it grew a byte at a time.
  `tools/status-scale-test.py` holds both shapes to Git's peak memory.
- SHA-1 runs about two and a half times as fast in a native build. Each block
  is unrolled over 32-bit words; the rounds read and wrote a list for each
  schedule word and masked a 64-bit value after each operation. A whole-file
  read makes one buffer of the file's size, where it kept about twice the
  file in outgrown buffers. `hash-object` of a 64 MiB file took 1.14 s and
  134 MB where Git takes 0.24 s and 70 MB; it now takes 0.44 s and 69 MB.
  A status that must hash its files gains the same. `tools/hash-scale-test.py`
  holds `hash-object` to Git's CPU time and peak memory.

## Unreleased — adding thousands of files

- Repositories whose `.gitattributes` say `* text=auto eol=lf`, mark files
  `binary` or `-diff`, or name diff and merge drivers no longer make status,
  add, commit, checkout, restore, reset, pull, diff or log refuse (den#102,
  first step). Attributes resolve per path and per field in Git's order, the
  `binary` macro in place. LF bodies under `text`, `text=auto` and `eol=lf`
  are stored and compared as they are; a CR-LF body that Git would clean
  still refuses by name, since this step does not normalize. Binary
  attributes and a configured `diff.<name>.binary` shape patches, stats and
  commit summaries as in Git. Unconfigured diff, merge and filter drivers
  behave as Git's defaults; merges honor `-merge`, `binary` and
  `conflict-marker-size`. Configured drivers, the built-in `union` merge,
  the built-in diff hunk-header drivers in patches, `eol=crlf`, `ident` and
  working-tree encodings refuse by name.
- Status, diff and diff's index refresh take a tracked file whose stat data
  still matches its index entry as that entry's blob, unread, whatever its
  attributes say, as Git does (den#102, second step). A clean checkout under
  `eol=crlf` or `ident` is clean instead of refused, and `* text=auto eol=lf`
  no longer makes status and `diff --quiet` read every tracked body. A changed
  or racily clean file under those attributes still refuses by name.
- `diff --binary` prints full object ids only for a file it renders as a
  binary patch; text hunks keep abbreviated ids, as Git prints them.
- `add` of several thousand new files no longer runs out of memory (den#91).
  Everything an add allocated was held until it exited: 512 KiB of
  compression tables for each object it wrote, and about five copies of the
  whole index for each path it staged, so 5000 new files needed about 25 GiB
  where Git takes 5 MiB. Each file's object is now written in its own region,
  the walk's scratch dies in a region of its own, and the index is staged
  once, in one pass, with the same bytes as before.
- `add .`, `add -A`, `add -u` and `commit -a` leave alone an entry whose
  file's stat data still matches it and is not racily clean, as Git does: its
  cache-tree records stay valid, so the index `add .` writes over an unchanged
  tree is Git's. A stat-dirty entry is staged again, as before and as in Git,
  and so is one whose mtime falls in the index file's own second or later.
  `add .` over 2000 unchanged files, and `commit -a` of one change among them,
  ran out of memory before.
- `commit` writes the cache tree's subtrees in Git's order, shorter names
  first and names of one length by their bytes (den#123). Past ten sibling
  directories (`d9`, `d10`) den's index differed from Git's.
- Each SHA-1 state reserves its lists, so hashing a file leaves no list growth
  behind; `commit -a` of 2000 files peaks about 19 MiB lower.
- `tools/add-scale-test.py` holds `add .` of 500, 2000 and 5000 new files, and
  `add .` over 2000 tracked ones, to the pinned Git: the same index, cache
  tree included, under a 64 MiB peak measured from `tools/minimal-parent.c`.
  Its `commit -a` rows, over 1000 and 2000 tracked files, must equal Git's
  index and grow linearly; commit's own per-file memory is a later change.

## Unreleased — a remote that stops sending (den#118)

- A fetch from a remote that stops sending now ends with a named line
  instead of waiting until something outside kills it. Every read of an
  HTTP connection, plain or TLS, already waited at most 30 seconds; a remote
  that kept the connection busy with keepalive or progress packets but sent
  no pack data was never bounded, and den waited as Git does.
- A fetch's pack stream now needs pack data: 30 seconds with none once the
  pack has begun, 120 seconds before its first byte. The lines are `fatal:
  the remote sent no pack data for 30 seconds` (or `for 120 seconds`) and,
  for a read that receives nothing at all, `fatal: the remote sent nothing for
  30 seconds` (it was `den: wire: Unsupported(TLS timeout)` or `HTTP read
  timeout`). Clone and fetch exit 128, pull 1; a submodule update reports a
  failed clone. `DEN_STALL_SECONDS` sets the bound.
- `tools/http-stall-test.py` holds clone and submodule update to the bound
  against a local remote, plain and TLS, that stops mid-pack: silent, sending
  keepalives, sending progress, or before any pack data.

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

## Unreleased — directories the walk cannot open

- `status`, `add -A`, `add .`, `add -u` and `commit -a` no longer stop with a
  bare `fatal: denied` at a directory they may not open (den#80). As Git
  does, the walk warns `could not open directory 'DIR/': Permission denied`
  when it looks for untracked files and goes on as if the directory were
  empty; tracked paths below it are looked up by name, and status reports
  one it may not look up as `PATH: Permission denied`, unchanged.
- `add` no longer opens an ignored directory (unless `-f`), as Git does not.
- A work-tree `.gitignore` that cannot be read is a warning, as in Git; an
  entry that cannot be looked up is untracked for status and Git's
  `fatal: unable to stat 'PATH': Permission denied` for add.
- A tracked path below such a directory whose lookup is denied stays a named
  refusal for `add` and `commit -a`.
- `tools/denied-test.py` holds 100 unprivileged rows to the pinned Git.

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
