# vc02 — objects and plumbing

**Draft for adoption by the orchestrator, not a launched lane. Model:
GPT-6-Astra. Track 16 den, M1. Base: the merged vc01 final head; resolve the
commit and read the adopted codec API.** Implement loose Git objects and the
first plumbing, no index/porcelain/history walker or wire protocol.

## Preconditions and setup

Read the track index (R1–R10), RULES §§1–10, wolf guide, den README/licences,
MAP, FORMATS, SOURCES, vc00's evidence and vc01's adopted contract/results.
Re-derive every pin and read release digests twice. The default inherited pin
is wolf 0.2.35/lupin 0.1.56/std 2386522e, Git 2.56.0 signed tarball in the
pinned Ubuntu container. Use a lane branch/worktree `vc02`, never shared trunk.
The orchestrator assigns a named host CPU block under flock and taskset before
launch. No Mac build, host package install, process-group kill, or write beyond
the lane directory. Own and reap all subprocesses. No memory/config edits,
other-repo push, merge, tag, release, issue write or PR label.

Do not start until vc01's inflate/deflate API and **R-vc00-2** loose-compression
parity outcome are settled. Keep the byte-comparing harness strict unless a
reviewed row approved under that outcome says otherwise. **R-vc00-1** corrected
SHA provenance must also be adopted or the source replaced as directed.

## Deliverables

1. **Prediction before code.** Predict exact init file inventory/config/HEAD
   bytes, object ids for empty/abc blob and empty tree, smallest commit/tag
   sizes, the number of plumbing cases, cross-tool fsck outcomes, memory
   growth at 100-MB objects and malformed-object row coverage. Commit before
   implementation and report misses as well as hits.
2. **Read primary docs.** gitrepository-layout(5), repository format versions,
   gitformat-loose(5), git-mktree(1), git-commit-tree(1) with date-formats and
   i18n includes, git-mktag(1), gitformat-signature(5) Description and multiline
   headers, Git user manual's Object Database/Object storage format. Read
   hash-object/cat-file/init/write-tree manuals for option/error contracts,
   recording page and section in SOURCES. Never read implementation source,
   another VCS library, or a blog's code. No source licence guess is a ruling.
3. **OID and hash boundary.** A documented type carries algorithm plus owned
   bytes, validates hex and exact width, and supports abbreviated lookup with
   explicit missing/ambiguous outcomes. SHA-1 is the repository format in this
   milestone; keep the 32-byte SHA-256 shape possible without public [20]byte
   assumptions. Reject unsupported objectFormat/repository extensions before
   writes. Use the vendored hash module and the existing tested std SHA-256
   wrapper, not subprocess hashes. Header sizes count bytes, not characters.
4. **Loose store.** Read/write `<type> <decimal-size>\0<body>` zlib streams,
   parse types/size, validate declared size and oid, and report bad headers,
   trailing data, truncation, corrupt checksum, missing objects, unsupported
   formats and output caps as documented rows. Every input is binary data,
   not a str. Bound allocation before trusting size; a 100-MB object must not
   induce quadratic copies. No read-all repository/pack fallback. Casefold
   and path separators cannot change object ids.

   Write with an exclusive temp file in the object fanout directory, correct
   permissions, complete data, sync, close, rename/install and parent-directory
   sync according to the measured Unix surface. Handle races where another
   writer installs the same oid; never overwrite unrelated objects or leave
   a truncated object. Failure injection tests must cover write/sync/rename
   cleanup and an existing object, not only the success path. Git's lock-file
   protocol uses exclusive creation; fs_lock is not a substitute. Document
   the cross-platform rename guarantee and avoid claiming more than it says.
5. **Body parsers/builders.** Blobs preserve all bytes. Trees have octal modes,
   raw non-NUL names, raw oid and directory-aware byte order (directory `a`
   after file `a.c`, before `a0`). Validate duplicates/illegal modes/names;
   preserve non-UTF-8 bytes in object data even when checking out such paths
   is blocked upstream. A tree parser must not decode a basename to str.
   Commits preserve tree, parents in order, author/committer and arbitrary
   headers with SP-prefixed continuation lines; understand encoding/gpgsig
   without verifying signatures. Build deterministic unsigned commits in the
   measured canonical header order. Tags parse/write object/type/tag/tagger,
   blank line/message; mktag strict validation differs from generic storage.
   Unknown header round-trip tests prevent lossy parsing. Commit/tag message
   bytes, final newline rules and invalid UTF-8 need oracle cases.
6. **Repository init.** Plain and bare, -q/--quiet, default branch and explicit
   -b only where the adopted command census supports them. Measure exactly
   what the pinned Git writes: HEAD, config, description, objects/{info,pack},
   refs/{heads,tags}, info/exclude and hooks policy. vc00's empty-template
   corpus is deliberate so no Git sample hook source is read. The track asks
   empty hooks for den: if default Git sample files conflict with the byte
   bar, ask **R-vc02-1** with options (pinned empty template for parity, or a
   named reviewed template difference), recommend the empty-template parity
   surface and carry it while awaiting a ruling. Do not read/copy sample hook
   scripts. Existing-directory reinit and bare/working config differences
   require fixtures. Never mistake a .git gitfile for an absent repository.
7. **Plumbing and CLI.** Replace only the implemented scaffold refusals:
   - `hash-object` (-w, --stdin, -t types, binary file/stdin), measured errors;
   - `cat-file -p/-t/-s` (blob/tree/commit/tag, missing and ambiguous ids);
   - `mktree` if adopted for round-trip tree tests, and `commit-tree` (-p/-m/-F)
     with pinned identities/dates and exact output id/newline;
   - `mktag` from stdin, strict header/object checks;
   - `write-tree` after defining its index boundary. Since vc03 owns the index,
     initially read only a minimal valid v2 index fixture written by Git, or
     explicitly leave the existing refusal with a named dependency; do not
     invent an empty-tree implementation for every repository. A change of
     milestone scope here is a proposed ruling, not a lane's decision.

   Parse no unsupported command as success. Other M2+ commands remain exact
   not-yet refusals, counted apart by the harness. No production Git or shell
   subprocess. stderr wording and exit status are oracle observations; exit 2
   from wolf build is a compile error, never a skip.
8. **Compatibility witnesses.** Extend `tests/cases.json`, keeping stable case
   names. Cases transition from not-yet to exact parity only when the actual
   stdout/stderr/status/.git snapshot agrees. Read each command's byte diff;
   no global index/object exclusion. If R-vc00-2 changes representation parity,
   implement a typed, case-bound approved review without wildcarding unrelated
   metadata; include corruption plants proving the oid/checksum gate remains
   live. Every reviewed row names case, exact both-side bytes, reason, ruling/
   issue and appears in README. Preserve vc00's --filter and empty-filter error.
9. **Integration and e2e.** Git writes→den reads, den writes→Git cat-file and
   fsck; same raw bytes/oid for every object. Empty/abc/NUL/all-byte data,
   executable and symlink modes, nested tree ordering, root/multiple-parent
   commit, encoding and continuation headers, annotated tag. Reproduce a repo
   twice under tools/env with independent fixed dates. Concurrent same-object
   writers inside the container, interrupted writes and permission failures
   use only owned fixtures/pids. Malformed objects must never crash the process.
   Checked, native and release unit runs; container command-level tests; every
   checked budget refusal loud and counted. No remote/network feature needed.
10. **CI and closeout.** Wire the new gates into tier pr and planner tests,
    update README/MAP/FORMATS/SOURCES/CHANGELOG, stage binary and source digests
    as evidence only (no release). Plant branches `vc02-plant-*` are granted:
    one-byte object/header/checksum corruption, smallest CI job observed red,
    PR closed unmerged. Keep the fix on vc02 before planting. Rulings are
    written R-vc02-N with options/recommendation; issues are proposed with
    minimal reproducer, never filed. No label or CI wait; status read once at
    final head and handed to the orchestrator to watch.

## API expected by vc03

Document owned object bytes and explicit failure rows. Suggested boundary:
`Oid`, `Object { kind, data }`, `read_object(repo, oid, max_output)`,
`write_object(repo, kind, data) -> Oid`, tree/commit/tag parse/build functions,
and repository discovery/init functions. Final signatures must be written
before vc03 starts and tested through a small client. A parser returns owned
or explicitly copied storage, never a lent buffer that outlives its caller.

## Forbidden

Git/other implementation source, sample hook scripts, external production
dependencies, manual golden edits, discarding unknown object headers,
pretending write-tree works without reading an index, silent format/ruling
choices, Mac builds, another host/core block, labels, issues, merges, tags,
releases, attribution trailers or writes to memory/config.

## Done-when and hand-back

- [ ] Prediction before code; primary command/format docs cited by section
- [ ] Init inventory/bytes and all implemented plumbing measured against Git
- [ ] Raw bytes and oids agree; compressed-byte rule expressly settled
- [ ] Cross-tool object reads and fsck, corruption/race/failure e2e witnesses
- [ ] Actual checked/native/release unit tests; skips explicit and counted
- [ ] Readable row diffs and exact reviewed exceptions; planted CI red cited
- [ ] README read/current and API for vc03 documented; per-item terse commits
- [ ] PR five named sections, sha bullets, checklist, `Footprint: cross-cutting`
- [ ] Audit from org root `bash wolf/tools/lane-audit.sh den vc02 <PR>`;
      quote the literal last line, no masking pipeline
- [ ] Final head pushed, status read once, no label or wait; hand back PR/head,
      run id, audit result, unresolved rulings, issues with probes, next-lane
      contract adjustments and exact prune paths

This draft is not launch authorization: the orchestrator must settle the
codec/parity preconditions and assign the host block first.
