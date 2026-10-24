# Changes

## Unreleased — M1 codec

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
