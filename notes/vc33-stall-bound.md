# vc33 — a remote that stops sending (den#118)

`den clone` and `den submodule update` over HTTPS could wait for ever on a remote that had stopped sending the pack. On PAX, a recursive submodule update stalled at 51 MB of an 85 MB pack and waited until its script killed it. The gate's live rows stalled twice for thirty minutes.

den's HTTP client already gave every read a 30-second deadline. That deadline ends total silence: it fired at 30 s over TLS as over plain HTTP, measured below. But a remote that keeps the connection busy without sending the pack (git's documented upload-pack keepalive, an empty packet every 5 seconds, or progress packets) renews it on every packet, and den waited exactly as Git does.

Now a fetch's pack stream needs pack data:
- 30 seconds with none, once the pack has begun;
- four times that before its first byte;
- it ends with a named line.

Footprint: module

## Forbidden

Clean room: Git's documentation (the 2.56.0 release tarball's `Documentation/` only, its digest checked against `den-oracle.toml`) and black-box runs of the pinned Git 2.56.0. No Git, libgit2, JGit or other implementation source was read. Organisation code read:
- den itself;
- wolf-std's `std.net`, `std.time` and TLS client at den's pin `d4a4d4c`, and wolf_rt's socket table at the wolf pin `5adf3d9`, for how the read deadline is armed;
- PAX's `kernel/ready` (`5da8daa`), for `epoll_wait`'s timeout.

The stall server follows the http-live-stall rows from the gate-hardening work, given the gateway's TLS mode.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, 46 GiB | every build and row, in the pinned oracle container (12 GiB cap), on a six-CPU block's four heavy CPUs or a two-CPU light slot |
| Apple silicon laptop | editing and commits |

## Inputs verified

- **Base:** den trunk `f908c9b`.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58 and wolf-std `d4a4d4c`, unchanged.
- **Oracle:** Git 2.56.0, executable `c4848492…`, checked by digest by the row script; OpenSSL pinned as `tools/http-git-test.py` pins it.
- **Pages:**
  - `config/uploadpack.adoc` (`uploadpack.keepAlive`);
  - `gitprotocol-v2.adoc` (the packfile section's side-band, `0005\2` as a keepalive under `sideband-all`);
  - `config/http.adoc` (`http.lowSpeedLimit`, `http.lowSpeedTime`).

## Prediction

`tests/vc33-prediction.txt`, committed first (`a3d02fb`).

- **P1:** held. At the base, keepalive and progress cues, plain and TLS: den never ended; the row stopped it at 90 s.
- **P2:** held. Silent cue at the base: den ended near 30 s with `Unsupported(TLS timeout)` or `HTTP read timeout`, exit 2.
- **P3:** held. At the head, every stall cue: exit 128 within the bound plus about 1 s, the named line last, the destination removed.
- **P4:** held, over plain HTTP: both clone attempts end with the named line, the update aborts (exit 1), and the module directory is removed. Over TLS the row's gateway cannot see a client leave (it serves one connection at a time through `s_server`'s pipes), so a held response reaches the retry's connection; the submodule row runs over plain HTTP.
- **P5:** held for the clone. For the submodule, Git does not refuse a module directory with no refs: it reuses it and fetches into it, as den already does (below).
- **P6:** held. The control clones as Git does at both commits.
- **P7:** see the record.

## R-list, as applied

- **R-vc33-1 = (b):**
  - 30 seconds without pack data once the pack has begun;
  - four times the bound (120 s) before its first byte, while the remote may still be preparing the pack: a large repository's server can be quiet that long and send only keepalives;
  - every read of a connection keeps the 30-second deadline.
  - Options not taken:
    - (a) 30 s throughout;
    - (c) Git's `http.lowSpeedLimit`/`lowSpeedTime`, a rate, off by default (den still refuses every `http.*` setting).
- **R-vc33-2:** `DEN_STALL_SECONDS` (whole seconds, 1 to 86400) sets the bound. With it set, the lines name the variable, as bound messages are literals.
- **Named lines:**
  - `fatal: the remote sent no pack data for 30 seconds` (`for 120 seconds` before the first byte);
  - `fatal: the remote sent nothing for 30 seconds` for a read that receives nothing at all;
  - before, the last was `den: wire: Unsupported(TLS timeout)` or `Unsupported(HTTP read timeout)`, exit 2;
  - exit codes now: 128 for clone, fetch and ls-remote, 1 for pull. A submodule update prints the line, then its own clone-failure lines.

## The stall, as measured (den 0469f02, before this branch)

A local remote: the pinned `git-http-backend` behind the smart-HTTP gateway, plain or TLS (the pinned OpenSSL `s_server`). The fetch response is cut at the pkt-line boundary nearest half a 2 MiB pack. Each client was stopped at 120 s.

| cue | den, plain | den, TLS | Git 2.56.0 |
|---|---|---|---|
| none | — | exit 0 | exit 0 |
| silent | exit 2 at 30.1 s (`HTTP read timeout`) | exit 2 at 30.2 s (`TLS timeout`) | waits |
| keepalive (`0005\x01` every 5 s) | — | waits | waits |
| progress (band 2 every 5 s) | — | waits | waits |

While den waited, its reactor thread sat in `epoll_wait` with a 30,000 ms timeout, renewed by every packet.

## Evidence index

- `a3d02fb` the prediction.
- `eea7972` red: `tools/http-stall-test.py`, the stall rows; `76344e9` runs them in `tools/check-http`.
- `2aee7de`: every HTTP read's deadline is the stall bound, its failure named.
- `b2eee50`: the pack stream's clock counts pack data only.
- `6b3e504`: clone, fetch, pull and submodule update print the line as itself.
- `24fffb9`: the submodule row runs over plain HTTP, where the gateway sees a client leave.
- `f361c04` (green at both commits): the rerun rows, a clone and a submodule update cut off mid-fetch and run again, held to Git.
- `574689b` README, `51a3340` CHANGELOG, `a9e9317` SOURCES; this note.

## Cut off mid-fetch, then run again

What a clone or a submodule update leaves when it is cut off mid-fetch:
- the state is copied while the tool waits on a stalled remote, the moment a kill would leave it; no signal is sent;
- then each tool reruns the command against a remote that answers;
- measured with den `0469f02` and the pinned Git (a harness outside the tree), and held by the rerun rows at both commits.

| state | den left | Git left | rerun by den | rerun by Git |
|---|---|---|---|---|
| clone | `dest/.git` with `HEAD`, `config`, `refs/` and the temporary pack | the same, with its own temporary pack | exit 128, `fatal: destination path 'dest' already exists and is not an empty directory.` | the same line, exit 128 |
| submodule update | `.git/modules/mod` with no refs and the temporary pack; no work-tree directory | the module directory the same, and `mod/.git` naming it | exit 0, checked out at the recorded commit | exit 0, the same commit, files and stdout; Git also prints two fetch reports on stderr (`From …` / `* branch HEAD -> FETCH_HEAD`, then the commit's), den none |

Both tools, when the remote ends the connection instead (an error rather than a kill), remove what they made: the clone's destination, and the module directory.
- So a rerun recovers from den's own cut-off submodule state, as Git's does: the module directory is reused and the recorded commit fetched into it, and the temporary pack stays behind unused in both.
- The rerun rows hold this, and the same with the empty gitlink directory a superproject's checkout leaves (the state on PAX).
- No den change was needed for it.

## Remaining limits

- A silent stall on a pipe transport (`file://`, ssh) has no read deadline. The pack-data clock bounds a pipe remote that keeps sending keepalives or progress, but not one that sends nothing.
- A trickle counts as progress: one pack byte every 29 seconds never trips the bound. Git's `http.lowSpeedLimit` (a rate) would; den refuses `http.*` settings.
- Discovery and `ls-refs` responses are read whole under the read deadline alone.
- On the rerun of a cut-off submodule update, den does not print Git's two fetch reports on stderr. That is den's submodule fetch output generally, not this change.
- The PAX leg is not measured here. PAX's `epoll_wait` keeps a timeout, so a silent stall should end at 30 s there as on Linux, and the new clock needs no timer of its own. A run on PAX hardware is the witness.

## Done-when

- [x] Prediction committed first
- [x] Stall rows red at the base, both transports
- [x] Stall rows green at the head
- [x] Rerun rows hold den to Git after a cut-off clone and submodule update
- [x] Formatting; pinned native and release builds
- [x] The final record and the plant (in the pull request)
