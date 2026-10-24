# vc01 — zlib

**Draft for adoption by the orchestrator, not a launched lane. Model:
GPT-6-Astra. Track 16 den, M1. Base: vc00's merged final head (resolve it;
never guess the commit).** Build the codec den's loose-object and pack readers
need, clean-room from RFC 1950/1951. No VCS porcelain in this lane.

## Preconditions

Read `wolf/sprints/vcs/index.md`, RULES §§1–10, vc00's MAP, FORMATS and SOURCES,
the wolf guide, den README and licences. Re-derive the toolchain and oracle
pins; read release archive digests twice. The exact toolchain is wolf 0.2.35,
lupin 0.1.56 and bundled std 2386522e unless the adopted contract names a new
pin. Do not follow “latest”. The interpreter tag rev is 28547b4; its printed
embedded pin is 294d626, as the verified archive records.

Resolve **R-vc00-2** before promising loose-file byte equality: Git's default
zlib level 1 and a new fixed-Huffman encoder do not generally emit identical
compressed bytes. Recommendation pending the maintainer: identical raw bytes
and oid, valid interoperable compressed representation, measured sizes. If
strict compressed-file equality is chosen, stop for a revised encoder scope;
do not silently add a blanket harness waiver. Pack bytes already have R4c's
interop/fsck and 1.5x corpus-size bar.

## Working setup

Own branch/worktree `vc01`, never shared trunk. The orchestrator assigns the
host and CPU block before launch. Expected kasumi lane clone/container pattern
from vc00, a named block under flock, taskset inside the lane's rootless pinned
Ubuntu container, core dumps disabled. No Mac builds. Never kill by process
group; end only owned pids. All scratch, downloads and build artifacts remain
under the lane directory. The lane may not install host packages, write
~/.claude or memory, push another repository, merge, tag, release or file issues.

## Deliverables

1. **Prediction before code.** Predict block coverage, malformed-input rows,
   checked-machine budget limits, size ratio to zlib level 1 on the corpus,
   native throughput and peak memory on incompressible/repetitive 100-MB data.
   Commit it before the first implementation change. Record results against
   each prediction, including misses.
2. **RFC readers.** Read RFC 1950 §§2.1–2.3 and RFC 1951 §§3.1–3.2.7 fully,
   citing exact sections in SOURCES. Write original decoding tables/logic.
   Read no zlib/miniz/libdeflate/Git/other codec implementation source, no
   snippets from blogs. No C ABI, external codec command or Python in the
   shipped executable. Python zlib/OpenSSL/etc may be black-box test drivers,
   never implementation dependencies. Never copy the RFC sample C routines;
   derive Adler-32 from the stated recurrence.
3. **Inflate first.** Stored, fixed and dynamic Huffman blocks; multiple blocks;
   32-KiB history across block boundaries; lengths 3–258; overlapping copies;
   canonical code construction; explicit handling of incomplete/oversubscribed
   trees, illegal codes 286/287 and distances 30/31, impossible distances,
   repeated code-length overflow, LEN/NLEN mismatch, truncated fields, reserved
   BTYPE. Every input-controlled bound is checked before indexing; malformed
   input returns a row, never a trap. No unchecked recursion or unbounded
   allocation from an attacker-supplied length. Enforce caller output limit.
4. **Zlib framing.** CM=8, CINFO<=7, FCHECK divisible by 31, FDICT refused by
   name, Adler-32 validated. The decoder reports consumed input through the
   checksum and does not eat bytes from the next object. Trailing bytes remain
   for the caller. Empty streams, all padding boundaries and concatenated
   streams get independent cases. Corruption is not turned into EOF.
5. **Encoder.** Start with stored and fixed-Huffman output, then bounded
   LZ77 matching with a 32-KiB window and a measured lazy-match strategy.
   No quadratic all-history search. Support level 0 and level 1 honestly;
   reject other requested levels until their contracts are implemented, rather
   than pretending to honor core.compression. If the adopted ruling requires
   more levels for vc02, amend this item explicitly. Emit correct framing,
   BFINAL, bit ordering, empty-input stream and Adler checksum. Never use
   `str` for binary data; window/buffer lifetimes use bounded regions.
6. **Object-store API.** Implement `src/zlib` with documented public items.
   The proposed API below is binding once adopted; propose any change before
   vc02 depends on it. Default object-store path uses level 1.

   ```wolf
   pub error InflateErrors = {truncated, bad_header, dictionary, checksum, invalid, limit}
   pub struct Inflated {
       data: List[byte],
       consumed: int,
   }
   pub fn inflate(src: List[byte], max_output: int) -> Inflated ! InflateErrors
   pub fn inflate_raw(src: List[byte], max_output: int) -> Inflated ! InflateErrors
   pub fn deflate(src: List[byte], level: int, max_output: int) -> List[byte] ! {invalid, unsupported_level, limit}
   pub fn deflate_raw(src: List[byte], level: int, max_output: int) -> List[byte] ! {invalid, unsupported_level, limit}
   pub fn adler32(src: List[byte]) -> int
   ```

   Negative limits are invalid; reaching the output cap is limit. `consumed`
   counts whole source bytes up through the current stream, not inflated size.
   The public Adler value fits a signed 64-bit int and represents an unsigned
   32-bit value. Returned data owns its storage; no returning a lent input.
   A streaming extension may follow only if measurements show whole-object
   allocation is unsuitable; no new universal I/O abstraction in this lane.
7. **Independent harness.** A tiny lane-owned zpipe-style oracle uses the
   container's zlib API (Python zlib is acceptable, no implementation source
   opened), reporting container/library version, uncompressed digest, encoded
   size and consumed bytes. Test both directions: zlib→den inflate and den
   deflate→zlib inflate. “Den decodes its own encoding” alone is insufficient.
   Generate random and structured inputs deterministically, stored/fixed/
   dynamic examples with zlib's flags, payloads at 0/1/2/3/55/56/63/64/65/
   257/258/259/32767/32768/32769/65535/65536 lengths, repeated zeroes and all
   byte values, many blocks, long distance and maximum-length overlaps.
   Track exact sizes and ratios; do not assert compressed equality unless
   R-vc00-2 requires it. Distinguish invalid streams from decoder budget skips.
8. **Integration and end-to-end.** Inflate every loose object and pack entry
   in vc00's nine-repo corpus; reconstruct raw header/oid with SHA-1 and compare
   Git cat-file bytes. Create loose objects using den's encoder and ask the
   pinned Git to cat-file/fsck them in a scratch repo. Include a two-object
   pack stream boundary test and a truncated/corrupt object refusal. No oracle
   subprocess in production den. Checked/native/release tests, with every
   unsupported checked row loud and counted. Deterministic bounded fuzz tests
   in the assigned container; no soak on the Mac.
9. **CI and plants.** Add the codec unit/integration/e2e gates to tier pr.
   Plant branches `vc01-plant-*` are granted in this draft: one-byte Adler,
   Huffman or size-limit corruption on an isolated branch, observe the smallest
   CI gate red, close that PR unmerged; cite run/job. Never alter a golden to
   accept a bug. The lane never adds labels or waits on CI: read final PR
   status once immediately after pushing and hand back; orchestrator watches.
10. **Docs and closeout.** Refresh MAP/SOURCES/README/CHANGELOG, including
    supported levels, refusal rows, input/output limits and measured size/time/
    memory. Decide extraction to a shared component repository only by a
    maintainer ruling; no new repository created here. Report any language or
    library gap with a minimal probe and proposed upstream issue, not a hidden
    workaround.

## Forbidden

Git or any other implementation's source, external production dependencies,
whole-pack reads sold as streaming, unchecked malformed data, a silent change
to R4/R9, labels/merges/releases/issues, Mac builds, another host block or
repository, memory edits. Follow R2 exactly and the no-attribution commit rule.

## Done-when and hand-back

- [ ] Prediction committed before code; primary RFC sections cited
- [ ] All inflate block forms and malformed rows tested on actual checked and native
- [ ] Encoder round trips through independent zlib; sizes and limits recorded
- [ ] Git corpus inflate and den-written loose-object Git interop/fsck green
- [ ] Container integration/e2e and planted red evidence, then clean local gate
- [ ] README read/current; per-item terse commits pushed; no coauthor trailers
- [ ] PR has Forbidden, Inputs verified, Prediction, Evidence index, Done-when,
      commit-sha bullets, test checklist and `Footprint: cross-cutting`
- [ ] Run `bash wolf/tools/lane-audit.sh den vc01 <PR>` from the org root;
      quote last line literally, never hide failure through a pipe
- [ ] Final status read once, no label, no wait; hand back PR/head/run/audit,
      measurements, proposed rulings/issues, owned pid/log/marker if an allowed
      long local job is still running, and exact prune paths

This draft requires the orchestrator's final host/block allocation and adoption
of R-vc00-2's outcome; it is not permission to choose either ruling.
