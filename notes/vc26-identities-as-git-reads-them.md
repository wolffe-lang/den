# vc26 — identities as Git reads them

den refused to clone `https://github.com/i3/i3.git` (`den: wire: Unsupported(fsck identity diagnostics)`), which Git clones: commit `5f453914a04c193baf5b4239d83116d33a74de62` has `author walker0643 <>` and the same committer, an empty email. The receive path ran den's commit-identity parser on every author, committer and tagger line. Now den takes identity lines as the pinned Git does, measured shape by shape: receiving, serving and pushing validate none (Git's `transfer.fsckObjects` defaults to false); `fsck` reports them with Git's message ids and text; log, show, tags, blame and a new user-format engine print them byte for byte as Git does; and commit, commit-tree, tag, amend, cherry-pick and rebase write them as Git does. An object's bytes and id never change by reading it.

Footprint: module

## Forbidden

Clean room: Git's documentation (the 2.56.0 release tarball's `Documentation/` only, its digest checked against `den-oracle.toml`) and black-box runs of the pinned Git and a field Git. No Git, libgit2, JGit or other implementation source was read. Every rule below (the fsck checks, the readers' split, the date rules, the writers' cleanup) is inferred from measured runs and written in den's own words. Organisation code read: den itself. The live witness is i3's public upstream repository.

| hardware | used for |
|---|---|
| Linux x86-64 desktop, 46 GiB | the measurements, every Linux build and row, the census, in the pinned oracle container on a six-CPU block holding both of its locks (12 GiB cap), or a two-CPU light slot (6 GiB) |
| Apple silicon laptop, macOS arm64 | editing, commits, native builds behind the build lock, the identity rows against the field Git, the census against the field Git, the macOS record |
| Apple silicon laptop (a second one) | native builds while the first laptop's lock was held |

## Inputs verified

- **Base:** den trunk `474a926`, branch `vc26`.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58 and wolf-std `d4a4d4c`, unchanged; archives checked by digest by `tools/fetch-toolchain`.
- **Oracle:** Git 2.56.0, executable `c4848492…`, checked by digest by every row script.
- **Field Git:** Homebrew's Git 2.56.0 on macOS (`--field`).
- **Pages:** git-fsck(1) (`--strict`, FSCK MESSAGES, `fsck-msgids`), git-config(1) (`fsck.<msg-id>`, `fsck.skipList`, `fetch.fsckObjects`, `receive.fsckObjects`, `transfer.fsckObjects`, `user.*`, `author.*`, `committer.*`), git-commit(1) (COMMIT INFORMATION), git-commit-tree(1), git-var(1), pretty-formats, rev-list-options (`--date`). `docs/SOURCES.md` (vc26) lists them.

## Prediction

`tests/vc26-prediction.txt`, committed first (`5a79fde`), before any measurement.

- **P1, git fsck:** 21 of 26 predicted verdicts held. Missed: an empty name with its space (` <e@x>`, ` <>`) is clean, not `badName`; two spaces before the date are clean, not `badDate`; a date of 2^63 is `badDateOverflow` (the limit is signed 64-bit), not clean. The witness's shape is clean, as predicted: Git's own fsck accepts `5f453914`.
- **P2, `--strict`:** held; identical to plain for every shape.
- **P3, clone and fetch:** held. With its defaults Git clones every shape; with `transfer.fsckObjects=true` it refuses exactly the shapes fsck reports, exit 128.
- **P4, reading:** held in part. Git never refuses a shape, but it re-spells lines from its split rather than printing their bytes (`A<a@x>` prints `A <a@x>`, `Jo<e <a@x>` prints `Jo <e <a@x>`), prints no Author line for a line it cannot split, and leaves some placeholders as written when a line or its date cannot be read. Not predicted: `git blame` refuses dates of 2^63 and above (`Timestamp too large for this system`).
- **P5, writing:** held: an explicitly empty email is written as `<>`, an empty name refused by name; the configuration form prints Git's "identity unknown" advice first.
- **P6, den at the base:** held: its receive path refused 37 of the 62 measured shapes, the witness included, and accepted 13 that Git's fsck reports; its fsck, log, show, blame and writers differed as predicted.
- **P7, the fix:** as below.

The measured table at the base is `notes/vc26-evidence/measured-base.txt` (62 shapes, 1,292 rows; the extended rows add 13 shapes and the replay, format and configuration families).

## R-list, as applied

- **R-vc26-1 = (b):** no identity line is validated on any receive or serve path (clone, fetch, push, `upload-pack`, `receive-pack`), as Git's `transfer.fsckObjects=false` default does; the typed links and the closure stay.
  - `den fsck` reports identities as `git fsck` does: the same message ids and text, the first one of each object, exit 1, in Git's order.
  - A configuration that asks for Git's object checks (`fetch.fsckObjects` or `receive.fsckObjects`, else `transfer.fsckObjects`, set true) is refused by name (`… den does not run git's full object checks`): den never claims a validation it does not do.
  - `links()` keeps its tree-path and tag-name refusals, including `.GIT` case-insensitively: den's checkout refuses only an exact `.git`, so on a case-insensitive file system the receive check alone guards hooks (recorded as a follow-up; checkout unchanged here).
  - Options not taken: (a) refuse what git fsck reports, which would refuse 35 measured shapes Git clones with its defaults; (c) (b) plus fsck-style refusal under the fsckObjects settings and `fsck.<msg-id>` severities, which is the follow-up once den's fsck covers Git's full check set.
- **Scope rulings:** the minimal user-format engine is in this lane (every other placeholder, and `%ar %ah %cr %ch`, refused by name); amend, cherry-pick and rebase rows keep the raw bytes wherever Git does.

## The rules, as measured

### Git fsck's identity checks (the first that applies)

1. the value starts with `<`: `missingNameBeforeEmail` (its text reads "missing space before email");
2. before any `<`, a `>`: `badName`; no `<` at all: `missingEmail`;
3. the byte before the first `<` is not a space: `missingSpaceBeforeEmail`;
4. after it, a `<` or the end before any `>`: `badEmail`;
5. the byte after that `>` is not a space: `missingSpaceBeforeDate`;
6. then any whitespace; a `0` followed by anything but a space: `zeroPaddedDate`;
7. no digit: `badDate`; digits above 9223372036854775807: `badDateOverflow`;
8. the digits not followed by one space: `badDate`;
9. not `+` or `-`, four digits and the end of the line: `badTimezone`.

One line per object (the first failing author, committer or tagger line), `error in <commit|tag> <id>: <msgId>: invalid author/committer line - <what>`, exit 1. Order: loose objects first, by object directory; then a pack's objects in pack order. den refuses by name the orders it has not measured: two reported objects in one object directory, an object both loose and packed, reports across packs, identity lines beside other diagnostics.

### How Git's readers split a line

- The name is the bytes before the first `<`, trailing whitespace dropped; the email runs to the next `>`. No `<`, or no `>` after it: the line does not split, and log and show print no Author or Date line, blame prints `(unknown)` with time 0.
- The date is read after the last `>`: whitespace, digits, whitespace, then a sign and digits. A missing date shows as the epoch (`Thu Jan 1 00:00:00 1970 +0000`; blame porcelain time 0, zone `(unknown)`).
- `%at` and blame porcelain's zone print the stored text; blame porcelain's time is the stored digits as an unsigned 64-bit number, saturated.
- A date above 9223372036854775807 shows as `0 +0000` in log and show; blame refuses it with Git's `Timestamp too large for this system: N`, N the sum with the zone, after the id of its row.
- A zone value moves the clock by its hundreds in hours and the rest in minutes (`+0099` is 99 minutes, `+12345` is 123 h 45 min) and prints as a sign and at least four digits; `-0000` prints `+0000`. A year past 9999 prints as is; one Git's C calendar cannot hold (past 2147485547) shows as the epoch at `+0000`; years past 2147483647 print wrapped to 32 bits, as Git's do. A local time before the epoch is Git's fatal `Timestamp before Unix epoch: SECONDS ZONE`, after the bytes Git wrote first.
- The placeholders of a line that does not split: `%an %ae` expand to nothing, `%al %aN %aE %aL` print as written; of a missing date: `%ad %aD %at %ai` expand to nothing, `%aI %as` print as written.
- A blame name's display width is its bytes when they are not UTF-8.

### How Git writes identities

- `<`, `>` and LF are removed, then whitespace and `, : ; " \ '` are trimmed from both ends of a name or email; `.` is kept. An empty email is written `<>`.
- An empty name: `fatal: empty ident name (for <EMAIL>) not allowed`, exit 128, after the "Author identity unknown" (or "Committer") advice when the name came from configuration; a name of disallowed characters alone: `fatal: name consists only of disallowed characters: NAME`.
- cherry-pick and rebase keep the picked author's stored bytes, except bytes that are not UTF-8, which Git repairs (Latin-1 as its characters) with its encoding warning; the cherry-pick summary shows the split (`Author:  <>` for a line that does not split) and its date, empty when none can be read.
- amend re-reads the author: the split name and email, cleaned; the stored date re-read as `@SECONDS ZONE` (a zone of other than four digits is the local one; `+0099` becomes `+0139`); no readable date, the commit's own; a line that does not split is `fatal: commit 'HEAD' has malformed author line`; a date saturating 64 bits is `fatal: invalid date format: @STAMP ZONE`.

## Evidence index

### Commits

- `5a79fde` the prediction; `1dd89ec`, `9500e0d` the rows (`tools/identity-test.py`), red; `445dc34` the measured table; `43596db`, `952d4ee` the replay, format, configuration, date, fsck-order and committer-only rows, red, with den's named refusals per row.
- `47ed333` `commit_format.raw_identity` and `identity_problem`; `36bd651` `shown_date`; `1266377` Git's cleanup and the empty email; `d266329` their unit rows.
- `47e57c5` no identity validation on receipt, and fsck's identity lines; `87a83c7` the fsckObjects refusals.
- `5e4f518` the walk's committer dates; `7f0c5b6` pretty and the user format engine; `d706d75` log and show; `594fca9` blame.
- `ddfa632` commit (picked, amended and empty-name identities); `5b12626` commit-tree; `c7747c0` rebase's author script.
- `7ba1b45`, `17a1bc4` the census; `0bccdcd` the live row; `08e592f` the rows in `tools/check-commit`.
- `f428924` history rows past the walk's 10,000-commit bound, red (`fatal: limit`, 576 of 581 exact, Linux, the pinned Git); `e1c2538` the walk stops after the count plus the skip when nothing is excluded (581 of 581).
- `823f57d`, `b5b5714`, `6229146`, `348bbc4` MAP, SOURCES, README, CHANGELOG; `3924114`, `26aa81f`, `6081b54` the walk's stop in MAP, README and CHANGELOG; this note.

### The rows

`tools/identity-test.py` (in `tools/check-commit`, both tiers): 75 shapes, each in a commit's author and committer and a tag's tagger, through the read family (cat-file, log, fuller, raw and strict dates, show of commit and tag, every identity placeholder, blame default, porcelain and `-e`), fsck (plain, `--strict`, packed, mixed, committer-only), wire (clone, bare, local, push, serving a fetch and a push, and the fsckObjects settings), replay (amend, cherry-pick, rebase); a format family (the engine over a history with merges and odd messages, and 24 placeholders refused by name); a write family (14 commit, commit-tree and tag cases). Every row is den's status, stdout and stderr equal to the pinned Git's, plus the received objects and refs or the written commit, except the named refusals in `REFUSED`: the three fsckObjects settings, `fsck --strict`, the 24 placeholders and amend of a date above 9223372036854775807 (den's dates are 64-bit signed).

### The census

`tools/identity-census.py` over bare mirrors (`git clone --mirror`, 2026-11-08) of i3, sway and curl and the organisation's 32 public repositories, den `a17eedf`. Three verdicts per history: den's identity check names, object for object, what the pinned Git's `fsck` reports; `den clone --bare` and `git clone --bare` over file:// give the same refs and objects; and every commit or tag with an identity line outside the plain canonical form, plus a fixed sample of 100 others, reads the same through `show -s --pretty=fuller`, every identity placeholder (raw and default dates) and `show -s` of a tag.

| history | commits and tags | identity lines | Git's fsck | empty email | unusual objects | read commands | verdicts |
|---|---:|---:|---|---:|---:|---:|---|
| i3 | 9,046 | 18,058 | all clean | 2 | 1 | 301 | equal |
| sway | 12,839 | 25,575 | all clean | 4 | 4 | 312 | equal |
| curl | 91,768 | 183,417 | all clean | 32 | 24 | 372 | equal |
| the organisation's 32 | 27,084 | 54,066 | all clean | 0 | 0 | 8,784 | equal |

Pinned Git, Linux, a two-CPU light slot: 34 histories in 418 s, curl in 563 s. Field Git, macOS: i3, sway and burrow, equal, with the same tallies. Every identity line in these histories is clean to Git's fsck. The lines outside the plain canonical form are empty emails (the witness's two lines in i3, four lines in sway, 32 in curl) and names of one character (sway and curl). The unusual lines themselves are kept in the census's JSON, not in this repository.

### The live row

`http-live-identity` (`tools/http-live-test.py`, in `tools/check-http`): den and the pinned Git each clone `https://github.com/i3/i3.git` (the public refs read before and after, the row taken again if they moved), the two clones have the same refs, objects and checkout, den's clone passes `git fsck --full` and its worktree is clean, and `log -1`, `show -s` and `log -1 --format=%an|%ae|%al|%ad|%at|%cn|%ce|%cd` of `5f453914` are byte for byte Git's. Without a network it prints `SKIP http-live-identity reason=no network (…)`.

At `e1c2538`, Linux, the pinned Git, a two-CPU light slot, 2026-11-08: `LIVE http-live-identity objects=41515 den=72.60s/283464KiB git=5.82s/39428KiB`, `PASS http-live-identity`. At `a17eedf`, before the walk stopped after its count, `den log -1 5f453914` alone took 130.65 s on the Apple silicon laptop, over the row's 120 s for each read (see Remaining limits).

## Remaining limits

- `fsck --strict` stays refused by name (it adds a file mode check den does not make); `fsck.<msg-id>`, `fsck.skipList` and their fetch/receive forms stay refused, and so do the fsckObjects settings.
- Placeholders beyond the engine are refused by name; so are user formats with a patch or stat and `show` of a tag with a user format; a mailmap is still refused for all of history.
- Amend of a date above 9223372036854775807 is refused by name; Git keeps it.
- den's history walk reads a pack's index again for each object it reads. With a count and no exclusions it now stops after the count plus the skip (`f428924` rows, `e1c2538`): `den log -1 5f453914` on a packed clone of i3 read all 6,060 ancestors and took 130.65 s on the Apple silicon laptop, more than the live row's 120 s, before that change. `log` without a count, or with exclusions, still walks up to 10,000 commits and refuses a longer history by name, and is slow on a long packed one. The census reads from a loose copy for that reason.
- Tree-path and tag-name checks stay on receipt; checkout's `.git` guard is exact-case only (a follow-up).

## Done-when

- [x] Prediction first (`5a79fde`).
- [x] The measured table, and R-vc26-1 ruled (b).
- [x] Rows red first at the base, then exact on both tiers.
- [x] The census and the live row (above).
- [ ] The final gauntlet, the plant and the macOS record: their records and every END line are in the PR body.
