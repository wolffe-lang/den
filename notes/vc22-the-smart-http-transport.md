# vc22 — the smart-HTTP transport

den clones, fetches and pushes over `http://` (loopback only) and `https://`, with a Basic token, over the standard library's public-PKI TLS client. Fetch is protocol v2 (`ls-refs`, then `fetch`); push is receive-pack with the status report, leases, atomic pushes and side-band-64k. Every wire, pack, lease and publication path is shared with the stream transports.

Footprint: cross-cutting (the std pin in `wolf-toolchain.toml`, `tools/gate`, `tools/gate-record`, `tools/gate-prune.py`, `ci/tiers-test.py`)

## Forbidden

Clean room: git's documentation, the RFCs, and the pinned Git and OpenSSL run as black boxes in the oracle container. No Git, libcurl, HTTP-library or TLS-library implementation source was read. wolf-std is organisation code and was read (`std/x/tls`, `std/net`, `std/fs`, the public-PKI note), as was wolf's memory-region note. A token lives only in the environment of the process using it: rows use fresh synthetic tokens, and every retained output is scanned for the token and its encodings before a row passes. The live rows send no credentials. No host name appears here; the hardware table below stands in.

## Inputs verified

- **Base:** den trunk `ef0bb0c`, branch `vc22`, rebased once onto trunk `ce939e2` (vc18's merge). The rebase had no textual conflict; the one semantic one is under R-vc22-6.
- **Toolchain:** wolf 0.2.36 (`5adf3d91`; binary `f7b73fba…`), lupin 0.1.58 (binary `47c646a6…`), unchanged. The std pin moves from `78b9d3cb` to wolf-std `d4a4d4c` (`cb16de5`), after a red row requiring its public-PKI signature schemes (`5449585`). 0.2.36 builds against it, so no toolchain re-pin was needed.
- **Oracle:** Git 2.56.0, executable `c4848492…`; OpenSSL 3.0.13 from the oracle image, `/usr/bin/openssl` `b4f547c0…`, `libssl.so.3` `a40e7b67…`, `libcrypto.so.3` `6866ed71…`, each read twice before a TLS row runs.
- **Roots for the live rows:** the image's distribution bundle, 120 certificates, 128,549 bytes of concatenated DER, sha256 `98a12f1a…`, decoded from PEM per RFC 7468 by the harness.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, i7-12700KF, 46 GiB | every build and row: a six-CPU block holding both of its locks for builds and gates, a two-CPU light slot for single-threaded rows; containers capped at 12 GiB (block) or 6 GiB (light), taskset inside |
| Apple silicon laptop, macOS arm64 | editing, commits and the planner/runner tests only; no den build |

## Prediction

`tests/vc22-prediction.txt`, committed first (`3209728`).

- **P1, the std pin:** held. 0.2.36/0.1.58 build den against `d4a4d4c`; the import probe was red at the old pin (`5449585`) and green after (`cb16de5`).
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

Shas name the commits as rebased onto `ce939e2`. A row measured before the rebase is cited by the rebased commit that carries the same change.

### Commits

- `3209728` the prediction.
- `5449585`, `cb16de5` the std pin, red then green.
- `fd7731c`, `fb980f4` URL and framing rows, then the parsers.
- `812972c`, `ddee85a`, `3eac5e9` raw-peer client rows, then bounded exchanges and cleanup on failure.
- `a950827`, `429cb1f`, `9afe03d`, `894d302` TLS rows, formatting, the framed-HTTPS row (wolf-std#133), then HTTPS with roots, entropy and UTC.
- `5018022`, `c0061d5`, `31919b1`, `2203eab` the gate pruner on Linux without `lsof`, red first, with a named preflight.
- `97b283f`, `56309e8`, `fce2020` Basic authentication rows, then credentials and the no-echo prompt.
- `520f9d9`, `9542ce8`, `4f1c1fd`, `6c99d4b` discovery, interop, redirect and policy rows; `757ef56`, `29eee57`, `1b1b9ea`, `6947dfe`, `b591015` redirects, HTTP peers, shared fetch/push over RPCs, roots and redaction.
- `ba128d6`, `833dad5`, `0c84a56`, `2b1deaa` receive-pack side-band rows, the bounded oracle timeout (R-vc22-3), then exact demultiplexing.
- `e2ab3cb`, `449fedc`, `23ca307`, `3b6e54f` GitHub's wrapped discovery: the capture, two red rows, then the envelope (R-vc22-4).
- `312816c` certificate signature, name, expiry and UTC controls.
- `653db36` the live rows.
- `94fd26b`, `d315d0b` the memory row, then a region per read (R-vc22-5).
- `3aa39d9`, `c74788e` discovery and RPC refusal rows with failed-clone cleanup, then the cleanup (R-vc22-6).
- `9a28290`, `a648f68` the planner's smart-HTTP gate assertion, then the gate wiring.
- `7474c7b`, `a0bfa42`, `3c3badc`, `c1b2987` hostile peer, policy and certificate rows.
- `a0b1944` formatting with the pinned compiler; then the README, MAP, SOURCES and CHANGELOG.
- `e21de88`, `d2c78f8`, `8a84516`, `c3b3aa7`, `fbf5637` the ssh program word (R-bw03-7): the argv as a pure function, the unit and recording-ssh rows red, a plain word sent bare, then formatting.
- `78651de`, `1ca1c2c`, `876db7e`, `2471362`, `45ed608`, `fad50a5` the evidence upload: the readable-and-keyless check, red, then each row's fixture PKI out of `target/runs` and the recorder's log directory readable.

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
| live github.com | `tools/http-live-test.py` | 3: read and limit (named SKIPs without network), and push (a named SKIP without its variables) |

### The over-limit refusal (R-vc22-5)

den's repository is a 311,900,659-byte pack (297.4 MiB, measured by the pinned Git's clone), beyond den's 140,000,000-byte wire cap. den refuses with exactly `den: wire: limit` and exit 2. den#61 tracks the limit itself.

| head | tier | elapsed | peak RSS | partial clone |
|---|---|---|---|---|
| `653db36` (before the fixes) | release | 102.2 s | 6,279,204 KiB | left (an initialised skeleton) |
| `653db36` (before the fixes) | native | 97.0 s | 6,270,644 KiB | left |
| `c1b2987` (after both fixes) | release | 82.8 s | 422,676 KiB | none |
| `c1b2987` (after both fixes) | native | 115.8 s | 423,484 KiB | none |

The 6 GiB peak was the light container's cap, so den was near an out-of-memory kill. On loopback, one 32,000,000-byte body measured:

| head | plain, Content-Length | plain, chunked | TLS |
|---|---|---|---|
| `94fd26b` | 5.13x | 5.18x | 65.51x |
| `d315d0b` | 3.14x | 3.14x | 3.26x |

### The live read

den and the pinned Git cloned the same public repository at the same ref (284 objects), with identical refs, HEAD, reachable canonical objects, worktree and remote configuration; Git's `fsck --full` and `status` are clean on den's clone. At `653db36`: den 7.27 s and 85,252 KiB in release, 10.22 s and 86,356 KiB natively; Git 0.50–0.55 s and about 38,000 KiB. Later reads of the same repository (480 objects, as it grew) took den 8–69 s, against Git's 0.5 s. A TCP relay timeline (encrypted byte counts only) put the whole exchange, discovery, `ls-refs` and the pack, on one reused connection, done at 1.63 s. den then sat for about 9 s, with about 0.3 s of CPU, before its TLS close: local I/O wait in the fetch import every transport shares, not HTTP. den#62 tracks it.

### The ssh program word (R-bw03-7)

A live row against GitHub found den sending `'git-receive-pack' 'owner/repo.git'`. A POSIX shell accepts that, but GitHub's ssh service parses the command itself and refuses it (`Invalid command`, exit 128 after a successful key login). The pinned Git, run with a recording `ssh` through `GIT_SSH`, sends one remote-command word: the program bare and the path single-quoted, `git-upload-pack '/srv/a b'\''c.git'`, with overrides inserted raw.

den now sends a plain program word (letters, digits and `._/+-`) bare and quotes any other as a literal executable; the path stays quoted. This covers `upload-pack`, `receive-pack` and their `--upload-pack=`/`--receive-pack=` overrides. Sources: `gitprotocol-pack(5)` (ssh transport) and `git-shell(1)` (the commands it accepts), and the black-box argv; no Git source.

| row | at `8a84516` | at `fbf5637` |
|---|---|---|
| `ssh-command-*` units, native, release and checked | 5 red (`receive-plain`, `upload-plain`, `override-plain`, `plain-word-set`, `scp`), 4 non-plain guards green; checked `exit(1)` | 9/9 in both tiers; checked `exit(0)` |
| `ssh-cli-*` against the pinned Git and `sh -c`, both tiers | 4 red (`clone-plain`, `clone-override-plain`, `push-plain`, `push-override-plain`), `clone-override-space` green | 5/5 in both tiers |

`ssh-cli-*` also runs each command through `/bin/sh -c` with recording service programs: the far side receives the same argv for den's command as for the fully quoted form, so den's existing sshd rows see no difference. At `fbf5637`, `ssh-peer-scope` and every `tools/check-porcelain` step, including the format check, end with exit 0.

### The evidence upload

The PR's labelled run (`42204935504`) failed only at the linux job's last step, which uploads `target/runs` and the other listed paths: `EACCES: permission denied, open '…/target/runs/http-git-tls-native-auth/pki/ca.key'`. CI's gate runs in a container as root, so everything it writes is root-owned, and the upload reads as the runner user. OpenSSL writes a private key as mode 0600 even under umask 0022 (measured in the oracle image: every `*.key` `600 root:root`, every file Python writes `644`), so the runner could not read the test CA's key. The recorder's own leaf-log directory, from `mktemp -d`, was 0700 for the same reason.

`tools/evidence-modes.py` reads the upload's path list from the workflow and refuses, by name, any collected file without the others-read bit, any directory without others-read and others-search, and any PEM private key; it runs last in `tools/gate` and as the last leaf of `tools/gate-record`. Red at `1ca1c2c` (`FAIL evidence-modes: 9 unreadable, 9 private keys in the upload`), and read as uid 1001 over a read-only mount, the runner's view, nine `EACCES` among 74 collected files. The fix keeps every row's fixture PKI out of the uploaded tree: the TLS, memory and smart-git harnesses generate it under `target/pki/<row>`, which no upload path names, and remove it when the row ends; the recorder makes its log directory 0755. The upload step is unchanged. Green at `fad50a5`: `PASS evidence-modes`, and as uid 1001 none of the 21 collected files denied.

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
- [ ] The final gauntlet, the plant and the audit at the rebased head; their records and every END line are in the PR body.

### Applied R-list

- **R-vc22-1 — applied:** close-delimited HTTPS bodies are refused by name, citing wolf-std#133. The TLS fixture serves with `-HTTP` and Content-Length.
- **R-vc22-2 — applied:** side-band-64k push messages are HTTP-only here; ssh and `git://` are den#60's.
- **R-vc22-3 — applied:** the truncated side-band frame is an explicit ORACLE-TIMEOUT non-parity row, Git reaped and no strays; den's refusal holds with its state unchanged.
- **R-vc22-4 — applied:** discovery accepts direct v2 or exactly the matching banner, flush and v2. A mismatched banner, a missing flush, v0 (with or without the banner, including a NUL capability line) and v1 are refused by name. Lines are compared as bytes, not text, so a v0 capability line reads as "not v2" rather than malformed.
- **R-vc22-5 — accepted, applied:** the over-limit refusal stays den's existing `den: wire: limit`, exit 2; the row bounds it at 600 s and 1 GiB peak RSS, and the shared limits are not relaxed. Each read runs in its own region and appends to one long-lived buffer. Options: (A) as built; (B) stream bodies to the pack parser instead of buffering whole responses, a larger change touching every transport. A was accepted; streaming bodies is den#61's.
- **R-vc22-6 — accepted, applied:** a failed clone removes the directory it created, for every transport, as the pinned Git does (measured black-box: a new directory is removed, an existing empty one kept). den already refuses an existing destination, so it never removes anything it did not create in that command. Options: (A) as built; (B) leave partial clones and file an issue. A was accepted. The cleanup is one small commit (`c74788e` after the rebase), a `defer` around clone. On the rebase, vc18 had split clone into `clone_mode`, which creates the destination and gained a local-path flag. Git applied the hunk there without a conflict, but the moved body no longer saw that flag, so the commit itself now passes it through. Both intents hold: vc18's local-path clone, and the removal of a failed clone's directory on every path.
- **R-bw03-7 = (a) — applied:** a plain program word goes bare, as Git sends it; any other is quoted; the path stays quoted. Red first (`d2c78f8`, `8a84516`), then `c3b3aa7`.

### Remaining limits

Credential helpers, cookies, proxies, content codings, HTTP/2, protocol upgrade, close-delimited HTTPS bodies, protocol v0/v1 advertisements, RPC redirects, `http.*` configuration beyond `http.followRedirects=initial`, and side-band push messages over ssh and `git://` remain named limits. den cannot clone its own repository over any transport until its 140,000,000-byte wire cap and 128 MiB pack payload cap allow it, or until bodies stream (den#61). A small clone waits on local I/O after the network exchange ends (den#62). The live push waits for its variables.

### For PAX

An https push from PAX needs:

1. **A root store on the image**, as one file of concatenated DER certificates named by `DEN_TLS_ROOTS` (the distribution bundle used here is 120 certificates, 128,549 bytes).
2. **A correct clock.** den validates certificates against the host clock in UTC; a clock far off fails `expired` or `not_yet_valid`. pax#293 tracks PAX's clock.
3. **A resolver.** den connects by host name through `std.net.connect`; PAX has no resolver yet (wolf-lang#831), so `github.com` cannot be reached by name.
4. **`/dev/urandom`.** den reads 64 bytes of entropy per TLS connection and refuses by name without it.

PAX should carry the den sha this lane merges as; a px lane does that re-pin.
