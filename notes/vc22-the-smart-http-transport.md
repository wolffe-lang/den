# vc22 — the smart-HTTP transport

den clones, fetches and pushes over `http://` (loopback only) and `https://`, with a Basic token, over the standard library's public-PKI TLS client. Fetch is protocol v2 (`ls-refs`, then `fetch`); push is receive-pack with the status report, leases, atomic pushes and side-band-64k. Every wire, pack, lease and publication path is shared with the stream transports.

Footprint: cross-cutting (the std pin in `wolf-toolchain.toml`, `tools/gate`, `tools/gate-record`, `tools/gate-prune.py`, `ci/tiers-test.py`)

## Forbidden

Clean room: git's documentation, the RFCs, and the pinned Git and OpenSSL run as black boxes in the oracle container. No Git, libcurl, HTTP-library or TLS-library implementation source was read. wolf-std is organisation code and was read (`std/x/tls`, `std/net`, `std/fs`, the public-PKI note), as was wolf's memory-region note. A token lives only in the environment of the process using it: rows use fresh synthetic tokens, and every retained output is scanned for the token and its encodings before a row passes. The live rows send no credentials. No host name appears here; the hardware table below stands in.

## Inputs verified

- **Base:** den trunk `ef0bb0c`, branch `vc22`.
- **Toolchain:** wolf 0.2.36 (`5adf3d91`; binary `f7b73fba…`), lupin 0.1.58 (binary `47c646a6…`), unchanged. The std pin moves from `78b9d3cb` to wolf-std `d4a4d4c` (`5cfd023`), after a red row requiring its public-PKI signature schemes (`7bfcc2e`). 0.2.36 builds against it, so no toolchain re-pin was needed.
- **Oracle:** Git 2.56.0, executable `c4848492…`; OpenSSL 3.0.13 from the oracle image, `/usr/bin/openssl` `b4f547c0…`, `libssl.so.3` `a40e7b67…`, `libcrypto.so.3` `6866ed71…`, each read twice before a TLS row runs.
- **Roots for the live rows:** the image's distribution bundle, 120 certificates, 128,549 bytes of concatenated DER, sha256 `98a12f1a…`, decoded from PEM per RFC 7468 by the harness.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, i7-12700KF, 46 GiB | every build and row: a six-CPU block holding both of its locks for builds and gates, a two-CPU light slot for single-threaded rows; containers capped at 12 GiB (block) or 6 GiB (light), taskset inside |
| Apple silicon laptop, macOS arm64 | editing, commits and the planner/runner tests only; no den build |

## Prediction

`tests/vc22-prediction.txt`, committed first (`414ced9`).

- **P1, the std pin:** held. 0.2.36/0.1.58 build den against `d4a4d4c`; the import probe was red at the old pin (`7bfcc2e`) and green after (`5cfd023`).
- **P2, bounded exchanges:** held. HTTP is a request/response peer beside the stream channels; fetch and push reuse every existing parser and publication path.
- **P3, discovery:** did not hold as written. "V2 discovery begins directly with version 2" is true of `git-http-backend` but not of github.com, which sends the `# service=git-upload-pack` banner, a flush and then v2 (captured, 191 bytes, sha256 `52c327cc…`). Accepting exactly that envelope is R-vc22-4.
- **P4, framing and reclaiming scratch:** the framing half held. The reclaiming half did not, at first: each read replaced the connection's buffer, and the TLS client's per-record temporaries were charged to the connection's region, so a body peaked at 5.1x its size over plain HTTP and 65.5x over TLS. The over-limit live row found it (about 6 GiB before refusing). Fixed by a region per read (R-vc22-5); now 3.1x and 3.3x.
- **P5, redirects:** held: five same-scheme initial redirects, credentials bound to the origin, RPC redirects refused.
- **P6, TLS:** held. Every named refusal survives as its client name, and a TLS 1.2-only server ends in `handshake_failure`.
- **P7, Basic authentication:** held: environment or no-echo prompt, helpers refused, secrecy scans on every retained artifact.
- **P8, the checked machine:** held: both HTTP unit programs return `exit(0)` from `conform-run --checked --json`, counted by verdict, never by exit status.
- **P9, records and the plant:** pending the final take.
- **Rows:** `http-live-read` reads a small public repository rather than den's own (amended), and a second row clones den's own repository to record its limit refusal. `http-live-push` waits for its variables.

## Evidence index

### Commits

- `414ced9` the prediction.
- `7bfcc2e`, `5cfd023` the std pin, red then green.
- `c21e3b4`, `490104d` URL and framing rows, then the parsers.
- `9286ad0`, `d3a6e18`, `016ee1f` raw-peer client rows, then bounded exchanges and cleanup on failure.
- `7c3cd2f`, `9500c5b`, `c4c3daa`, `b1aecd8` TLS rows, formatting, the framed-HTTPS row (wolf-std#133), then HTTPS with roots, entropy and UTC.
- `2db1e7f`, `9e1febb`, `fc8a22b`, `83db33e` the gate pruner on Linux without `lsof`, red first, with a named preflight.
- `ed93f2f`, `5d2e450`, `1f52985` Basic authentication rows, then credentials and the no-echo prompt.
- `21d690f`, `286fc28`, `a13a0eb`, `d3c2356` discovery, interop, redirect and policy rows; `769d102`, `aca80d9`, `f09a556`, `027d4bf`, `067b0dd` redirects, HTTP peers, shared fetch/push over RPCs, roots and redaction.
- `4e47b71`, `d2d7a4c`, `b72b759`, `b38f045` receive-pack side-band rows, the bounded oracle timeout (R-vc22-3), then exact demultiplexing.
- `ec06265`, `00c0959`, `0e478ad`, `d398284` GitHub's wrapped discovery: the capture, two red rows, then the envelope (R-vc22-4).
- `f2fe674` certificate signature, name, expiry and UTC controls.
- `3ca92a3` the live rows.
- `ac224e7`, `12112ab` the memory row, then a region per read (R-vc22-5).
- `170976b`, `ec20219` discovery and RPC refusal rows with failed-clone cleanup, then the cleanup (R-vc22-6).
- `819db8a`, `0a8da97` the planner's smart-HTTP gate assertion, then the gate wiring.
- `5abe6ab`, `3b208b3`, `772af53`, `28639d3` hostile peer, policy and certificate rows.
- `3577148` formatting with the pinned compiler; then the README, MAP, SOURCES and CHANGELOG.

### Rows (`tools/check-http`, native and release unless marked)

| family | harness | rows |
|---|---|---|
| URL, heads, chunk sizes | `src/http_test.lu` | 3 groups; also on the checked machine |
| discovery envelopes, redirect resolution | `src/http_redirect_test.lu` | 16; also on the checked machine |
| raw peers and hostile input | `tools/http-client-test.py` | 27 |
| TLS against the pinned OpenSSL | `tools/http-tls-test.py` | 17 |
| one large body's memory | `tools/http-memory-test.py` | 3 |
| redirects and origin-bound credentials | `tools/http-redirect-test.py` | 4 |
| Basic authentication and secrecy | `tools/http-auth-test.py` | 6 |
| policy refusals | `tools/http-refusal-test.py` | 12 |
| discovery and RPC refusals, clone cleanup | `tools/http-discovery-test.py` | 13 |
| receive-pack side-band | `tools/http-sideband-test.py` | as inherited, with one ORACLE-TIMEOUT non-parity row (R-vc22-3) |
| smart-git interop, plain and authenticated TLS | `tools/http-git-test.py` | 8 + 8, and token secrecy |
| live github.com | `tools/http-live-test.py` | 2, or 2 named SKIPs without network |

### The over-limit refusal (R-vc22-5)

den's repository is a 311,900,659-byte pack (297.4 MiB, measured by the pinned Git's clone), beyond den's 140,000,000-byte wire cap. den refuses with exactly `den: wire: limit` and exit 2.

| head | tier | elapsed | peak RSS | partial clone |
|---|---|---|---|---|
| `3ca92a3` (before the fixes) | release | 102.2 s | 6,279,204 KiB | left (an initialised skeleton) |
| `3ca92a3` (before the fixes) | native | 97.0 s | 6,270,644 KiB | left |

The 6 GiB peak was the light container's cap, so den was near an out-of-memory kill. On loopback, one 32,000,000-byte body measured:

| head | plain, Content-Length | plain, chunked | TLS |
|---|---|---|---|
| `ac224e7` | 5.13x | 5.18x | 65.51x |
| `12112ab` | 3.14x | 3.14x | 3.26x |

### The live read

den and the pinned Git cloned the same public repository at the same ref (284 objects), with identical refs, HEAD, reachable canonical objects, worktree and remote configuration; Git's `fsck --full` and `status` are clean on den's clone. At `3ca92a3`: den 7.27 s and 85,252 KiB in release, 10.22 s and 86,356 KiB natively; Git 0.50–0.55 s and about 38,000 KiB.

## Done-when

- [x] Prediction first.
- [x] The std pin, red then green; toolchain unchanged.
- [x] The bounded HTTP/1.1 client with hostile-input rows.
- [x] Smart HTTP discovery, v2 clone and fetch, push with the status report, leases and atomic; the dumb protocol refused by name.
- [x] TLS with caller-supplied DER roots, the host clock, SNI and names; no insecure mode; plain HTTP only on loopback.
- [x] Basic authentication from the environment or a no-echo prompt; helpers refused; secrecy scans.
- [x] Interop against the pinned `git-http-backend` behind the pinned OpenSSL, den and Git compared.
- [x] The live read; the over-limit row.
- [ ] The live push (waits for its variables).
- [ ] The final gauntlet, the plant and the audit, after vc18 merges and one rebase.

### Applied R-list

- **R-vc22-1 — applied:** close-delimited HTTPS bodies are refused by name, citing wolf-std#133. The TLS fixture serves with `-HTTP` and Content-Length.
- **R-vc22-2 — applied:** side-band-64k push messages are HTTP-only here; ssh and `git://` are den#60's.
- **R-vc22-3 — applied:** the truncated side-band frame is an explicit ORACLE-TIMEOUT non-parity row, Git reaped and no strays; den's refusal holds with its state unchanged.
- **R-vc22-4 — applied:** discovery accepts direct v2 or exactly the matching banner, flush and v2. A mismatched banner, a missing flush, v0 (with or without the banner, including a NUL capability line) and v1 are refused by name. Lines are compared as bytes, not text, so a v0 capability line reads as "not v2" rather than malformed.
- **R-vc22-5 — applied, recommended:** the over-limit refusal stays den's existing `den: wire: limit`, exit 2; the row bounds it at 600 s and 1 GiB peak RSS, and the shared limits are not relaxed. Each read runs in its own region and appends to one long-lived buffer. Options: (A) as built; (B) stream bodies to the pack parser instead of buffering whole responses, a larger change touching every transport. **Recommended: A** now, with B as follow-on work if den is to clone its own repository.
- **R-vc22-6 — applied, recommended:** a failed clone removes the directory it created, for every transport, as the pinned Git does (measured black-box: a new directory is removed, an existing empty one kept). den already refuses an existing destination, so it never removes anything it did not create in that command. Options: (A) as built; (B) leave partial clones and file an issue. **Recommended: A**, since the ruled live row requires it.

### Remaining limits

Credential helpers, cookies, proxies, content codings, HTTP/2, protocol upgrade, close-delimited HTTPS bodies, protocol v0/v1 advertisements, RPC redirects, `http.*` configuration beyond `http.followRedirects=initial`, and side-band push messages over ssh and `git://` remain named limits. den cannot clone its own repository over any transport until its 140,000,000-byte wire cap and 128 MiB pack payload cap allow it, or until bodies stream. The live push waits for its variables.

### For PAX

An https push from PAX needs:

1. **A root store on the image**, as one file of concatenated DER certificates named by `DEN_TLS_ROOTS` (the distribution bundle used here is 120 certificates, 128,549 bytes).
2. **A correct clock.** den validates certificates against the host clock in UTC; a clock far off fails `expired` or `not_yet_valid`. pax#293 tracks PAX's clock.
3. **A resolver.** den connects by host name through `std.net.connect`; PAX has no resolver yet (wolf-lang#831), so `github.com` cannot be reached by name.
4. **`/dev/urandom`.** den reads 64 bytes of entropy per TLS connection and refuses by name without it.

PAX should carry the den sha this lane merges as; a px lane does that re-pin.
