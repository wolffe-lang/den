# Changes

## Unreleased — a transition refuses or completes as Git does, never half-applied

- A merge, checkout, switch, cherry-pick or `reset --hard` whose target adds a
  path found its checks blind to what stood where that path needs a directory.
  An untracked file `zz` where the target adds `zz/new.txt` passed the checks,
  and the transition wrote other files before the write of `zz/new.txt` failed
  with `fatal: not_found`: HEAD and the index unchanged, the work tree half
  moved (den#185). Git refuses before writing anything.
- Every check now runs before any write. A file, symlink or staged file in a
  new directory's place is found by name. An untracked one refuses with Git's
  "untracked working tree files would be overwritten" and its path. An
  untracked directory where the target puts a file refuses with Git's
  "Updating the following directories would lose untracked files in them".
  `reset --hard` removes what is in the way and completes, as Git's does.
- **Two of these remove what you had, as Git does.** An ignored file, or a
  directory holding only ignored files, standing where the target adds a path
  is deleted, and the merge, checkout, switch, cherry-pick or reset
  completes. A file you staged
  with `add` but never committed, unchanged since, standing where the target
  adds a directory, is dropped from the index and deleted from the work tree,
  and a fast-forward, checkout or switch completes; its content stays in the
  object store only. If you changed that file after staging it, the transition
  refuses instead (and a true merge or cherry-pick refuses either way).
- The worktree leaf's `transition-obstruction` rows hold each case to the
  pinned Git: output, exit, HEAD, refs, index and work tree, and nothing
  changed where Git refuses. The `transition-rerun` rows' failure after
  writes began now comes from a target path whose 300-byte name no file
  system here can hold, since an untracked file in the way no longer gets
  that far.

## Unreleased — a transition's scratch freed before its cache tree

- A pull's merge or fast-forward moves the work tree in a transition. At
  its end the transition builds the next index's cache tree, and the
  command's peak is that build's end: everything the transition allocated
  before it was still held there. On the pull rows' repository (den#138) a
  merge's transition held 126.2 MB at the merge's peak of 202.4 MB, and the
  build itself 39.9 MB of that.
- The transition now runs up to the build in one region: the work tree's
  scan (itself in a region of its own unless the fast-forward's safety check
  made it already), the checks, the writes and the next index's entries.
  The kept staged paths whose trees the build leaves invalid are found
  there, before the build. Only the next index and that list are copied
  out, so the rest is freed before the build begins.
- A scan that fails in its region is run again outside it, where its
  error's message can leave. A failure after the scan is never run again,
  since the writes have begun: its message is copied out and raised once
  the region is freed. The worktree leaf's `transition-rerun` rows force a
  failure in the scan, in the checks, in a write after earlier writes, and
  in the cache tree, and hold trunk's refusal for each: its text, its exit,
  and the work tree and index after it.
- No row bounds the merge's or the fast-forward's peak yet. One bounds-only
  change, from this change's readings and the merge-base walk's, follows.

## Unreleased — a pull's ancestry walks stop at the merge base

- A pull asks two questions before it merges: is HEAD an ancestor of
  upstream (a fast-forward), and is upstream an ancestor of HEAD (already up
  to date). Each had its own walk, and a walk whose answer is no read every
  commit. On the pull rows' history of 5,000 commits (den#138), a merge pull
  read them all twice and a fast-forward once. The merge command then read
  every commit reachable from either tip again to find the merge base. The
  pull moves 20 commits.
- One walk now finds the merge base (`walk.common`, through
  `mergetree.bases`). It takes commits newest first and marks which tips
  reach each one. It stops when every queued commit is below a commit both
  tips reach. It reads the commits down to the base and the base's parents,
  and nothing under them. Dates only order the walk: a commit whose marks
  grow is walked again, so the bases do not depend on them. A candidate that
  another candidate reaches is dropped. The pull takes both answers from
  that base (`wiregit.pull_ancestry`): HEAD alone is a fast-forward, and
  upstream alone is up to date. Fetch and push keep their own ancestry check.
- Two refusals no longer happen, where Git has neither:
  - a history past 100,000 commits whose bases lie nearer no longer stops at
    `limit: more than 100000 commits in the ancestry walk`;
  - a commit absent deeper than the base's parents, as in a shallow clone
    deep enough, is no longer read. The merge proceeds, with Git's result.

  A commit absent on the walked path refuses as before. That includes a
  shallow boundary at the base itself, since den does not read
  `.git/shallow` here.
- The merge leaf's `ancestry` rows hold the commits a walk reads and its
  answers where history is incomplete or shallow. The merge-base rows add
  skewed, wide, deep and unrelated graphs, each printed with its seed.

## Unreleased — a merge pull row dated as a clock gives it

- The pull rows run every Git command under `tools/env`, whose clock is
  pinned at 1700000000, while the generated history is dated by fast-import
  from 1700000000 on. So the merge row's local commit is dated before its own
  parent, which a commit made after its parent never is. A walk that takes the
  newest commit first meets the whole upstream history before that commit.
- `pull-scale-merge-dated` is the same pull with the local commit dated one
  second after the remote's tip, as a commit made now is. The merge row is
  unchanged beside it.

## Unreleased — an index validated once per value

- A scan of the work tree checks the index it is given, as `index.serialize`
  does: the version, every entry, the extensions and the cache tree's spans.
  It made that check twice, once itself and once more in its rows. A merge pull
  scans five times, so on the pull rows' repository (den#138) it checked its
  index 10 times and serialized it whole each time. Yet one of the two values
  it scans is what `index.parse` just returned, which makes the same checks,
  and the other is checked by its first scan.
- A scan now checks at most once (`worktree.scan_index_held`). A caller that
  holds a value as `index.parse` returned it, or as a scan checked it,
  unchanged since, says so, and the scan makes no check. The merge command does
  this for its dirt and staging checks, both transitions and a fast-forward's
  safety scan, so a merge pull checks its index once, plus the write, and a
  fast-forward only at the write. Every other caller is still checked, in one
  pass where it was two, and a malformed index read from disk is still refused
  by `index.parse`.
- A scan counts its checks (`Snapshot.validations`), and the worktree leaf's
  `scan-validations` rows hold them: none for a held value, one for any other,
  and a value whose cache tree its entries disagree with still refused.

## Unreleased — a merge's transitions release what they read

- A pull or merge moves the work tree and the index in a transition. A
  transition scans the work tree, reads the target's trees and builds the
  next index's trees. All of that stayed in the command's memory until the
  command ended, so a merge's second transition stacked on its first. On the
  pull rows' repository (den#138) each transition kept 142.8 MB, and the
  merge's peak was 390,604 KiB, 23.8 times Git's.
- Each transition now runs in a region of its own, and only the index it
  made is copied out. A diagnostic raised inside is copied out too and raised
  once the region is freed. A transition is never run again to raise its
  error, since it writes files.
- No row bounds the merge's peak yet. The pull rows print it beside Git's,
  and a bound follows from held readings.

## Unreleased — wolf 0.2.41

- den is built with wolf 0.2.41 (0261597), the std it bundles (32a1cd06) and
  lupin 0.1.63 (2becebc4); the newest-release leaf builds with 0.2.41 too. Every
  pinned archive was read twice from the release API and hashed
  (`notes/pins-0.2.41/`). wolf's `Map` now finds keys through a hashed index,
  where the 0.2.36 `Map` compared a key with every entry: the record states what
  that does to the pulls' time.
- `probes/pack-client` built an error inside a region and returned it with `?`
  at two sites, which 0.2.41 refuses (E1010). Each name is now parsed before its
  region opens, and a read that fails inside runs again outside, where its error
  can leave.
- The checked machine's one recorded exception (a pack-payload row it rendered as
  `<value>`) held only for 0.2.36. 0.2.41's checked machine prints the tag, so the
  table is empty.
- The next-wolf candidate leaf and `candidate-wolf.toml` are retired: the build
  they checked (1add9bb) is in 0.2.41. The newest-wolf leaf now reads the pins
  against each other first (`tools/toolchain-pins-test.py`): the newest release is
  never older than the pin, and a candidate must stay ahead of it.
- The newest-wolf leaf now builds what the candidate leaf built: den and the
  five index-check programs on both tiers, and every test program under `src/`
  (nested ones too) on native, with their E1010 counts held equal across tiers.
  `src/mergefile/markers_test.lu` is built by no other leaf. The newest release
  can be downloaded by a workflow's own token, so hosted CI builds them too, which
  it could not do for the candidate.

## Unreleased — a pull's trees and merge plan without scans

- A pull that moves the work tree builds the index's trees, and a merge pull
  plans each path against three sides. Both scanned. Building the trees
  compared each entry's directories with every directory made so far, and the
  merge planner scanned a side for each path it looked up. On the pull rows'
  repository (10,500 files in 5,000 directories, 5,000 commits in 44 packs;
  den#138) that was 51 million comparisons for the trees and 276 million for
  the merge's lookups.
- Building the trees keeps open the directories of the entry before it.
  Entries come in path order, so every entry under one directory is
  contiguous, and an entry finds each of its directories by one comparison at
  its level: 19,999 comparisons for those 10,500 files.
- The merge planner finds a path by binary search where a side is in path
  order, as a side read from a tree or an index is: 758,158 comparisons for
  that merge. A side that is not in order is still scanned.
- On those pulls, instructions fall from 35.9 G to 29.8 G for the
  fast-forward and from 99.8 G to 50.3 G for the merge; the heap peaks fall
  slightly (191.5 MB to 189.4 MB, 404.8 MB to 402.8 MB). CPU falls by less,
  measured beside the previous build on one performance core: from 2.34 s to
  1.98 s for the fast-forward (15%; 25.4 to 21.5 times Git's) and from 5.72 s
  to 3.57 s for the merge (38%; 41.3 to 25.8 times Git's). The removed loops
  were the cheapest instructions, and the merge's system time, about half a
  second, is untouched.
- `index-trees-compares` and `mergetree-at-compares` bound those comparisons,
  and `index-trees-root` and `mergetree-at-plan` check that the trees and the
  plan are the same. The pull rows print den's and Git's user and system CPU
  and their ratio as a reading; they gate no ratio.

## Unreleased — an index read as Git reads it

- den refused an index whose trailing checksum was not the SHA-1 of its
  content. Git reads an index without checking that checksum, and where
  `index.skipHash` is set (`feature.manyFiles` sets it) Git writes twenty zero
  bytes in its place. So den refused every index Git wrote with that setting,
  with `fatal: checksum`. Every read also paid a SHA-1 of the whole index:
  1.6 M of the 11.0 M instructions of a warm `diff --quiet` on the status-speed
  leaf's fixture.
- A read now checks the index's structure as before, but not its trailing
  checksum. `fsck` checks the checksum as Git's does. It accepts the zeros and
  the content's SHA-1. It refuses anything else with Git's two lines,
  `error: bad index file sha1 signature` and `fatal: index file corrupt`, and
  Git's exit, 128, where it exited 2 before.
- What a read no longer catches: a damaged index whose structure still
  parses. A flipped bit in an entry's stat words or object name is now read as
  Git reads it, where den refused it as `checksum`. `fsck` still refuses it.
- den's writes still compute the checksum where `index.skipHash` is set; Git
  writes zeros there. Git reads either.
- `ls-files` on an index den refuses names the cause, as `status` does
  (`fatal: invalid_index`, and so on), not `fatal: den: invalid`. Its exit
  stays 128, as Git's.
- The stat pass of `diff` checked each index path's components again after
  the index read had checked them. It now checks none again. It looks only at
  the components past the directory it last verified, and copies a path only
  when the result keeps it.
- `diff` copied paths and file bodies a byte at a time; an owned path or body
  is now copied in one copy. A string's bytes still go through the byte copy,
  which wolf-lang#927 requires.

## Unreleased — an entry's end from its own stream

- A read found an entry's end from the next entry's offset, so the first read
  from a pack ordered every entry by offset (a radix sort over the whole index)
  and resolved every offset, even for a command that reads one object. It now
  finds the end from the entry's own zlib stream, as Git does, and checks the
  entry's CRC32 after the inflate, over the bytes the stream used; the
  reconstructed identity is checked as before. Opening an index resolves and
  orders nothing. An offset delta's base is read at its offset, and its slot,
  for its CRC, is the one its rebuilt identity names at that offset. An index
  is ordered only by a check of every entry (verify-pack, fsck, installation)
  or by a batch read that keeps its delta bases unhashed.
- A read reads an entry's header in one read of at most 4 KiB, then its
  stream in windows of at most a MiB, each read with one positional read and
  inflated in its own region into one output list. The inflater can now stop
  where its input ends and go on from the stream's last whole block when given
  more (`zlib.inflate_resume`), so each window starts at that block: a window
  reads again at most the block it stopped in, and a read holds one window of
  the pack at a time. The stream may run no further than the least of the bytes
  left before the trailer and the size hint (the declared size, a sixteenth
  more and 64 bytes). The CRC is taken window by window, and compared, as
  before, only once the stream has ended and its size holds, so a corrupt entry
  is refused as it was: by the inflater's name, then by its size, then by its
  CRC.
- A declared size is the entry's own claim, read before any of its bytes are
  checked. The output is reserved to the least of the size, a MiB and what the
  input can make (1,032 bytes a byte), and grows as it is made: doubling to an
  eighth of the size, then the size. A false claim of 400 MiB now reserves a
  MiB; it reserved all of it when the stream behind it was over 400 KiB. A
  sound 16 MiB entry reserves 19 MiB in all, once (1.19 times its size),
  against 16 MiB before.
- What a read of a 16 MiB entry charges, its bytes read and its reservations
  together, counted by the session, against den before this change and Git,
  which maps the entry and holds the output:
  - incompressible (a stream of 16.0 MiB, read in 16 windows): 2.20 times its
    size, against 2.0;
  - compressible (a stream of 0.66 MiB, one window): 1.25 times, against 1.04;
  - four symbols (a stream of 4.7 MiB, five windows): 1.50 times, against 1.29.
  The read reads at most its entry's bytes, a window past them and what each
  window reads again (1.5% more for the incompressible form), and holds a MiB
  of the pack at a time, where it held the whole stream.
- What changes against Git, and against den before:
  - bytes between entries no longer stop a read; Git reads past them too.
    verify-pack and fsck still refuse a stream that does not end where the next
    entry starts, as Git's do;
  - a bit a stream never reads, flipped, is refused by the entry's CRC; Git's
    read does not check the CRC;
  - a damaged stream is now refused by the inflater's name (`pack zlib …`)
    where it was refused as `pack entry CRC`, since the inflate comes first;
  - a false declared size over a stream that truly consumes more than a MiB of
    input is read through its stream and one window past it: 2.1 MB for a
    crafted 1.1 MB stream with 9.5 MB of pack after it, where Git inflates
    through the 1.1 MB. Both refuse it; its reservation stays at a MiB.
- New rows:
  - the inflater's robustness, before any of this: every zlib vector through
    `inflate_sized` (the pack reader's entry point), the codec fuzz through it
    with every prefix of three streams, an in-program fuzz on every tier and on
    the checked machine, and `tools/pack-entry-test.py`: eight corrupt entries
    read beside Git, each refused by name, and a bit-flip sweep of four
    entries' streams;
  - resumption: `tools/codec-resume-test.py` resumes four streams made by
    Python's zlib at every split point, and names the splits inside a stored
    block's length, a dynamic header and a code, between blocks, in the final
    block and in each Adler-32 byte; `src/zlib_resume_test.lu` resumes den's
    own streams and their mutants at seeded splits on every tier and on the
    checked machine; each must answer as whole-buffer inflation does;
  - what a read costs, from the session's counters
    (`probes/pack-client --read-counts`): no order and no offset resolved for
    a read with or without a delta; a false claim's read and reservation; the
    crafted stream's; three 16 MiB entries' reads, reservations and largest
    window, beside what Git's read holds; the incompressible entry's idx CRC
    flipped, refused as `pack entry CRC` across its sixteen windows;
  - `tools/read-scale-test.py`: a 16 MiB blob, incompressible and
    compressible, read beside Git, its CPU and peak bounded against Git's.

## Unreleased — status beside a large pack

- Opening a pack index read the file 64 KiB at a time and copied every byte
  into one list. It parsed each entry into a list of its own, copied the
  20-byte name table again, and ordered the entries by offset with a merge
  sort through that list, about 19 passes for 390,000 objects. It checked
  every entry: the fan-out against the names, the names' order, every offset,
  the large-offset table and duplicate offsets. A pack session then copied the
  parsed index once more to keep it. Beside a pack of 390,000 objects,
  `status` spent 98% of its instructions there: 1,163 M in all, against Git's
  1.26 M.
- The index is now kept as it was read, a MiB at a time, because the
  runtime's positional read returns at most a MiB. Each entry's offset is
  resolved once. The offsets are ordered by a radix sort whose keys carry
  their slot, on 8-bit digits under 65,536 entries and 16-bit digits from
  there. A small index pays 257 counters a pass, so a pull, which opens about
  a thousand small indexes, does not pay a large index's table on each. The
  session moves the index in instead of copying it.
- Opening an index now checks only what any use of it needs, as Git's open
  does: its header and version, a fan-out that never decreases and stays
  within the object count, and its length. A lookup searches the name's own
  fan-out bucket, as Git's does. A read checks the entry it uses: its offset,
  its large-offset reference and its CRC. `verify-pack`, `fsck` and
  installation check every entry. So a read no longer refuses a whole pack
  because some other entry is malformed, and reads of the objects a malformed
  entry does not touch answer as Git's do.
- `fsck` refuses every malformed index Git's `fsck` refuses, and two more by
  name: a name outside its fan-out bucket, and an unused large-offset entry,
  which Git's `fsck` passes. Two reads still differ from Git's, and den is the
  stricter in both. An offset-delta base at a pack offset no index entry names
  is refused, because a read checks each entry's CRC by its slot, while Git
  reads the base there. Where two slots hold one name, the object the lookup
  lands on is refused by its identity, while Git returns it.
- On Linux, in one take beside trunk's code (instructions counted by
  callgrind; resident peaks from the status-scale row):
  - `status` beside the 390,000-object pack: 189.3 M instructions, from
    1,163.0 M (Git: 1.26 M). Its resident peak fell from 67.6 MiB to
    45.2 MiB (Git: 4.8 MiB);
  - the three pull rows: up to date 358.6 M, from 763.9 M; fast-forward
    36.90 G, from 39.74 G; merge 101.05 G, from 104.54 G.
- New rows:
  - `tools/pack-test.py`'s open-counts rows hold an open to one read for each
    MiB of the index, no byte copied one at a time, and ordering work bounded
    by the index's entries. They read counters the session keeps, which
    `probes/pack-client --open-counts` prints. A 20-pack repository holds the
    cost of each open.
  - `tools/pack-idx-entries-test.py` holds six malformed indexes' reads,
    `fsck` and `verify-pack` to the pinned Git's.
  - `tools/status-scale-test.py`'s objects bounds are now 10 times Git's CPU
    plus 0.06 s, and 3 times Git's peak plus 40 MiB.

## Unreleased — the next wolf builds den's test programs too

- `tools/check-candidate-wolf` built only what den ships (den and the five
  index-check programs), not what den tests, so an E1010 in a test program, or
  in a module only a test imports, passed the leaf and the record. It now also
  builds every test program under `src/` (each `*_test.lu`, nested ones too,
  45 today), found when it runs, on native. A test program added later is
  built without an edit to the leaf. One of them,
  `src/mergefile/markers_test.lu`, was built by no gate leaf at all.
- The tests build on native alone because the checker's diagnostics do not
  depend on the tier. The leaf holds that on the programs it builds on both:
  their E1010 counts must agree (`candidate-wolf-tier-independent`).

## Unreleased — den builds with the next wolf

- The next wolf refuses a `?` that hands its caller an error whose payload
  was built inside a `region` block (E1010): the block's memory is freed
  before the caller reads the message, and native and release read freed
  bytes. Built with every diagnostic shown, den had 55 such sites (the first
  25 were listed when the compiler's default limit cut the list), and
  repairing the pack readers revealed 14 more in their callers: once a reader
  raises in its caller's region, a caller that calls it inside a region of its
  own is a site too. Each site now handles its error inside the region, copies
  the message into a binding declared before the region, and raises the same
  tag with it once the region is freed, leaving the region as the `?` did;
  payload-free tags still return from inside. No region is widened and nothing
  more is copied on a success path.
- In the replay loops of cherry-pick and rebase, whose step regions held 5 and
  15 such calls, each step's body moves unchanged into a function of its own
  that opens no region (`pick_step`, `rebase_step`), so each region holds one
  call to handle.
- `tools/check-candidate-wolf` builds den and the five index-check programs on
  both tiers with the next wolf (`candidate-wolf.toml`: the wolf-lang release
  workflow's build of 1add9bb, archives by digest), every diagnostic shown. It
  runs in the record (`tools/gate-record`) only: hosted CI cannot download
  another repository's workflow artifact with its own token. When wolf
  releases this compiler it becomes the newest release in `wolf-toolchain.toml`
  and the leaf and `candidate-wolf.toml` are retired.
- `tools/pack-payload-test.py` reads two malformed packs through every pack
  reader and holds each diagnostic, read after other regions have reused
  memory, to the one the reader built, on native, release and the checked
  machine. `tools/checked-exceptions.json` names the row whose tag the pinned
  compiler's checked machine renders as `<value>`; that entry fails once the
  pin moves or the machine renders the row correctly.

## Unreleased — status stops copying what it is done with

- A warm `status` on the speed rows' fixture (454 tracked files) made about
  11,500 deep list copies, each list costing 46 bytes before its contents in a
  region that never frees: a plain push copies its operand, and the walk, the
  index parser, HEAD's flattened tree and the status rows pushed values they
  never used again. They now move them (`push(take x)`), the walk keeps each
  directory's lstat scratch in its region, and a visit's path moves into its
  file. Measured against the previous trunk in one hold: minor faults 571 to
  440 (native) and 545 to 414 (release), heap peak 1.86 to 1.30 MB, CPU 0.18 ms
  less. Git's status reads about 162 faults; most of the rest is the runtime's
  cost per list (wolf-lang#1177).
- `tools/status-faults-test.py` gates it on both tiers (Linux): the least of
  nine runs, den from an in-memory copy of its binary, at most 448 and 422
  faults.
- `tools/http-live-stall-test.py` also checks that the live rows' pause is
  60 s when `DEN_LIVE_UNREACHABLE_PAUSE` is not set.

## Unreleased — a live row runs once more when the host is out of reach

- The live clone rows (the HTTP leaf's read, identity and self rows, and the
  submodule leaf's clone rows) failed at once when the pinned Git could not
  reach github.com for one of its reads: a record lost its HTTP leaf to a
  35-second outage that the native tier, minutes earlier, did not meet. When
  a read of the pinned Git fails with a failed name lookup or connect, the
  row now prints `RETRY <row> unreachable=<reads>`, waits 60 s
  (`DEN_LIVE_UNREACHABLE_PAUSE`) and runs once more; a second such failure
  fails the row, naming the reads, with no third attempt. Only Git's reads
  decide: a den clone that fails while Git's succeed is never rerun.
- `tools/http-live-stall-test.py` holds it with three local rows: the server
  stops listening after its first fetch and comes back within the pause
  (one RETRY, then PASS), never comes back (one RETRY, then FAIL), or answers
  Git and closes den's fetch (no RETRY, FAIL on the difference).
  `tools/submodule-live-unreachable-test.py` holds the first two for
  live-wolf-web. The live leaf checks its rule on Git's words from that
  outage each time it starts.

## Unreleased — status refreshes the index as Git's does

- `status` writes the index again when an entry it read was stat-dirty with
  its content and mode unchanged, with the stat words Git's status writes. The
  next command then finds the entry stat-clean instead of reading the file
  again. On a clean tree it takes no lock (Git takes one and drops it). A
  lock another process holds leaves the index as it was, silently.
- `GIT_OPTIONAL_LOCKS` is read as Git reads it, and only by status. false,
  no, off, an empty value, or an integer that is zero turns the refresh off.
  A value that is neither a boolean nor an integer ends status with Git's
  message and exit 128. `--no-optional-locks` before the command sets it to
  0, as git(1) has it. Git's diff refreshes the index whatever the variable
  says, and den's diff still does too.
- `tools/status-refresh-test.py` holds the refresh to Git on a clean tree,
  stat-dirty files, changed ones, both together and files dated ahead of the
  index, with optional locks on, off by the variable or the option, and with
  the lock already held, and holds the variable's values to Git's reading.
- The README states that the timed speed rows run with optional locks off.

## Unreleased — status finds each path among its own directory's entries

- `status` looked each path its walk visited up by a binary search of the
  whole index, and looked each file up again the same way to tell tracked
  from untracked: about ten path compares a lookup, each over the full path,
  a fifth of a warm status's instructions on a 454-entry index. The walk now
  searches only the index entries beneath the directory it is in, comparing
  names past the directory's prefix, and the second lookup starts where the
  last file's landed: 6.8 and 3.0 compares a lookup on the test's 600 paths,
  from 10.2.
- The walk sorted its files into path order by comparing their paths (6.4
  compares a file on the test's paths). It now sorts them by the index
  position each lookup already found, and compares paths only between
  untracked files that would sit at one position: 35 to 41 compares for 600
  files, as the host lists the directories.
- When the index's cache tree names HEAD's tree, HEAD's entries are the
  index's own, and status compared each of them, path and id, with its own
  copy. It now takes them as one, looks for further stages only after a
  conflict entry, and passes a file once it has matched it: 2.0 compares a
  path, from 7.0.
- The status scan counts that work and its compares (`Snapshot.walk_lookups`,
  `row_lookups`, `merge_counts`, `sort_counts`). `probes/status-phases`
  prints them and `tools/status-lookups-test.py` bounds them: 8 and 5 a
  lookup, 3 a merge step, 1 a sorted file. The lookup and merge counts are
  exact on every host and tier; the sort's depends on the order the host
  lists a directory, within its bound.
- The warm `status` ceiling of the native build is 3.5, from 4: the record
  read 2.30 against Git's 0.92 ms (ratio 2.52), from 2.63 ms.
- `tools/status-lookups-test.py` makes its probe's directory itself, so it
  runs in a checkout no build has touched.

## Unreleased — a warm diff --quiet without the duplicate work

- A diff of the worktree against the index no longer runs its autoRefreshIndex
  step when every entry was stat-clean and nothing was hashed: that step took
  the index lock, parsed the index a second time and checked every entry's
  stat a second time, and found nothing to refresh. Git takes neither the
  lock nor a second pass there; den now matches it. A tree whose files are
  stat-dirty with their contents unchanged, or that has a racily clean
  entry, refreshes exactly as before.
- Such a diff opens the packs only when it reads a body from them; on a
  clean tree it reads no object and parses no pack index.
- A whole-file read of 64 KiB or less keeps its one chunk as the answer
  instead of copying it into a buffer a byte at a time (about twenty
  instructions a byte). A larger file is still read in chunks into one buffer
  of its size: read in one chunk it was held twice, and `hash-object` of a
  64 MiB file peaked at 131 MiB instead of 67.
- `tools/diff-racy-test.py` observes what each tool does to `.git` (any file
  created or removed there, and whether the index was written again) and
  holds den's worktree diffs to Git's on a clean tree and on a stat-dirty one.
- The warm `diff --quiet` ceilings are 4.5 (native) and 4 (release), from 7
  and 6.

## Unreleased — den builds with the newest wolf release

- The newest wolf release, 0.2.40, refused to compile den (E1010 at the two
  calls of the fetch closure walk's `follow`, `src/wiregit/objects.lu`), while
  the pinned 0.2.36 accepted it. The refusal is right: typing an object the
  repository held (`object.kind_cached`, through `pack.session_kind`) loaded
  the reader's packs when they were not loaded yet, so a first call inside the
  walk's per-step region would have left the reader holding pack indexes the
  region frees. The walk never took that path (its reader's packs load before
  the walk), but the code allowed it. `pack.session_kind` now reads the session
  and never loads it, answering an unopened session through a whole read as
  `pack.session_cached` does. What a fetch or pull checks, prints and writes is
  unchanged, and so are their timings.
- `tools/check-newest-wolf` builds `src/den.lu` on both tiers with the newest
  wolf release and the std it bundles, warnings denied, as well as with the pin;
  it is a gate leaf, so CI and every record run it. The release is pinned by
  digest beside the toolchain (`[wolf-newest]` in `wolf-toolchain.toml`,
  staged by `tools/fetch-newest-wolf`) and raised by hand when wolf releases.
- `tools/pack-test.py` types a base, an offset delta and a reference delta
  through a reader whose packs are not loaded, one region each, and requires
  each kind and the packs still unloaded after every call.

## Unreleased — the speed rows' sampling and band

- The four speed rows whose Git side takes about a millisecond of CPU or less
  (warm `status`, warm `diff --quiet`, and `diff --cached --quiet` cold and
  warm) sum each sample to 1 s of CPU and take nine samples, where they took
  five of 0.2 s. Across the records taken with the rows on, they moved by up
  to 22% between takes, more than the fifth a ceiling leaves above the
  measured ratio; seven takes of the longer sampling on two core sets moved
  by at most 11% (least over least; 7% as the median of per-sample ratios,
  which every row now prints beside it). The other rows keep five samples
  of 0.2 s.
- The ratchet rule is code (`ceiling_for`), and the short rows have a band of
  their own: the spread between takes of their sampling, rounded up to a
  twentieth and never under a fifth. Measured, it is 1.20, the same as every
  other row's fifth, so no ceiling moves. Each row prints the ceiling its take
  would set. `tools/speed-band-test.py` holds the rule, the sampling and the
  band to recorded takes, on every host.
- The speed leaf counted PASS lines and ignored its scripts' exit statuses,
  so a measuring script that stopped after printing its rows (one did, at a
  head of this change, before writing its report) still read sixteen passes.
  The leaf now counts a row only when its line and its script's report agree,
  removes an earlier take's reports first, and fails a missing report by name
  (`tools/speed-summary.py`, held by `tools/speed-summary-test.py`).
- Den's own speed and memory are unchanged: these are the measuring tools.

## 0.1.0 — 2026-11-20

- First 0.1.0 preview of Git-compatible objects, local history, worktree operations and experimental transports. This is not a complete replacement for Git.
- Align the package and CLI release version. Release builds record the compiler observed at build time; local source builds report unrecorded provenance.
- Require every gate leaf at the exact tag before staging macOS arm64 and Linux x86-64 archives with SHA-256 sidecars. Releases remain drafts until explicitly published.
- Pull, merge, diff and commit handle files up to 1,000,000,000 bytes where they stopped at 16 MiB; a fast-forward pull of one commit takes about 2 to 3 times Git's CPU, and the diff and pull speed rows carry ceilings checked on every gate take.
- Reading the index of a large tree takes near-linear time, adding thousands of files is held to Git's index and a memory bound, and change summaries count lines with no bound on differing lines.
- Follow symbolic links in pulls, read clones Git made, pull a week's work, and end a fetch from a remote that stops sending with a named line (30 seconds without pack data, 120 before the first byte).
- Read local time zones and identities as Git does, name directories the walk cannot open, and handle submodules and the everyday wire gaps over smart HTTP.
- The entries below, headed Unreleased, give the detail of each part of this release.

## Unreleased — fast-forward pull

- A fast-forward `pull` of one commit over `file://` on the 454-file speed
  fixture takes about 2 to 3 times Git's CPU where it took 5 to 23 times
  (record host, den over Git, cold / warm index): native 12.69 / 23.26 ->
  2.08 / 2.92, release 5.14 / 8.77 -> 1.42 / 1.91; den's CPU 841 / 760 ms
  -> 137 / 93 ms native and 337 / 274 ms -> 94 / 62 ms release, against
  Git's 66 / 32 ms. Peak memory 19.6 -> 18.1 MB native and 16.8 -> 15.4 MB
  release, about twice Git's 8.5 MB.
- A fetch's closure check typed each object the received trees name that
  the repository already held by reading it whole: inflating it, checking
  its pack entry's CRC-32 and hashing it, for every unchanged file of the
  tree (most of a pull's time). It now types such an object from its pack
  entry's header, a delta's from its base's (a loose one is still read), and
  does not read it again: a fetch does not re-verify packed objects the
  repository already held, as Git's does not; `fsck` checks every object.
  What a fetch receives is checked as before, and
  `tools/fetch-damage-test.py` (in `tools/check-wire`) holds a pull to
  refusing a received object damaged in transit, leaving the repository as
  it was.
- A fast-forward merge scanned the work tree twice, once for its checks and
  once for its transition, hashing every stat-dirty tracked file each time,
  and built and stored every tree of its target, which it never used; it
  now scans once and assembles no trees.
- A rename's score below 1 MiB sums its span weights from two sorted lists
  instead of a Map, whose every update and lookup scanned its keys: a
  pull's change summary scores each deleted path against each added one,
  twice. The scores are the same.
- A packed read checks an entry of 2,048 bytes or more against its CRC-32
  through the 256-entry table, a byte a step, where it took eight steps a
  byte; the value is the same.
- A fetch of fewer than 100 objects writes them loose through packs opened
  once, where each write's check for a stored copy parsed every pack index
  again.
- The pull speed rows' ceilings came down in two steps, each by the README's
  rule from the record host's measurement and each committed before the
  changes that earn it: native 18 / 34 -> 5 / 6.5 -> 3 / 4, release 7 / 12
  -> 3.5 / 4 -> 3 / 3 (cold / warm). The second step covers four smaller
  changes together, since none alone moves a ceiling by a half step.
- The warm `diff --quiet` speed row of the native build has a ceiling of 7
  where it had 6.5. Three takes of the row on two core sets read 4.89 and
  5.57 (den at 54dc6c8 and at 4f73a20) and 5.93 (den at d7927e2, which also
  carries den#146's changes to object reads); the last fails 6.5 once the
  1.10 guardband applies. Git's side of the row is about 0.6 ms of CPU, and
  the spread between takes of so short a row is wider than the fifth the
  ceilings leave. No other ceiling rises.

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
- `tools/module-deps.py`, run first by the format gate, holds every package
  manifest (`src/*/wolf.pkg`, `probes/*/wolf.pkg`) to the den modules its
  files `use`: den's own build resolves a sibling module without the entry,
  so a probe that builds the module as a path dependency was the first to
  find `commit` using `difftext` unlisted.

## Unreleased — speed rows for diff and pull

- `tools/check-status-speed` measures sixteen rows where it measured two:
  `status --porcelain`, `diff --quiet`, `diff --cached --quiet` and a
  fast-forward `pull` over `file://`, each with a cold and a warm index, for
  the native and the release build, on the 454-file fixture. A row holds
  den's CPU time to a multiple of the pinned Git's (the least of five
  interleaved samples, a 1.10 guardband) with exit status, output and end
  state equal to Git's, and states both tools' peak memory. The ceilings are
  one table, `tools/speed-bounds.json`, one per row, index state and build,
  set from the record host's measurements: 3 where den is already within 3
  times Git, up to 6.5 for a warm `diff --quiet` and 34 for a warm native
  `pull`, each to be lowered toward 3 by the change that earns it.
- The rows are timed in records taken on the record host, which holds a block
  of cores alone and declares it with `DEN_PERF_ROWS=1`, and not in hosted CI,
  whose runners are shared: there each row prints `NOT MEASURED` by name.
  `tools/speed-rows-test.py` fails if a workflow or the container wrapper
  sets the switch.

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
