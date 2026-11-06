# Changes

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
- A clone keeps the received pack, as Git does, and so does a fetch of 100
  objects or more; a smaller fetch becomes loose objects. The fetch asks for no
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
