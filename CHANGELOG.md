# Changes

## Unreleased — daily use

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
