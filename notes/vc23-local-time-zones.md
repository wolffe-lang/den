# vc23 — local time zones (den#84)

With `TZ` set to anything but UTC, `den commit` stopped with `den: not yet implemented: commit implicit local timezone <TZ>`; a `TZ` exported from a shell startup file was enough to stop every commit. The other writers did not stop: `tag -a`, `merge`, `stash`, `rebase`, `notes`, `branch`, `switch` and `reset` wrote `+0000` where Git writes the local offset. Now every date den writes without being given one, and every date it is given without a zone, takes the local zone exactly as the pinned Git does: from `TZ`, or `/etc/localtime` when `TZ` is unset, read as Git's C library reads it, at the instant the date names.

Footprint: module

## Forbidden

Clean room: Git's documentation (the 2.56.0 release tarball's `Documentation/`, its digest checked against `den-oracle.toml`) and black-box runs of the pinned Git. No Git, libgit2 or other implementation source was read, and no C library or tzcode source either: how Git's C library reads a `TZ` value was measured through Git (`git var GIT_COMMITTER_IDENT`, `git commit`), and, to find a change's exact instant quickly, through the same C library's `localtime` in the oracle container, each such reading then confirmed through Git. Organisation code read: den, and wolf-std's `std.time` (which den uses unchanged).

## Inputs verified

- **Base:** den trunk `291011d`, branch `vc23-tz`.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58 and wolf-std `d4a4d4c`, unchanged; archives checked by digest by `tools/fetch-toolchain`. No newer std was needed.
- **Oracle:** Git 2.56.0, executable `c4848492…`, checked by digest by every row script; Ubuntu 24.04 with its C library 2.39.
- **Zone files:** `tests/zones/` holds America/New_York, Europe/Berlin, Australia/Lord_Howe, Asia/Kolkata and EST5EDT, copied byte for byte from the oracle image's tzdata 2026e (sha256 in `tests/zones/README.md`). The rows point `TZDIR` at them, or at an empty directory for "no zone database", so no row depends on the host's database.

## What Git does, measured

### When a date is not given

The offset in force at that instant, exactly: rules whose change is two hours ahead of or behind the moment of the commit give the offset on each side (`stamp/change-*`, west and east of Greenwich, start and end of daylight saving). The author, committer, tagger and reflog lines all take it.

### How a TZ value is read

| `TZ` | Git |
|---|---|
| unset | `/etc/localtime`; UTC when it is missing |
| empty, `:` | UTC |
| a POSIX rule (`EST5EDT,M3.2.0,M11.1.0`, `CET-1CEST,M3.5.0,M10.5.0/3`, `<+1030>-10:30<+11>-11,M10.1.0,M4.1.0`, `J` and day-number rules, explicit times) | as POSIX describes it |
| a fixed offset (`JST-9`, `<+0530>-5:30`, `UTC-3`, `LMT0:44:30`, `ABC-24:59:59`) | that offset, written in whole minutes toward zero (`-0:44:30` is `-0044`; 30 seconds is `+0000`) |
| a zone name (`America/New_York`, `EST5EDT`) with a zone database | the file below `TZDIR` (default `/usr/share/zoneinfo`) |
| a zone name with no such file | UTC |
| `:name` | the file `name` below `TZDIR`, never in the working directory; UTC when missing |
| an absolute path | that file; UTC when missing |
| daylight saving with no rules (`EST5EDT`, `XXX3YYY`, `CET-1CEST`) and no file of that name | with no `posixrules` file in the zone directory: the US rules, `M3.2.0,M11.1.0` at 02:00; with one, that file's changes adapted to the value's offsets |

### How a malformed TZ value is read

Git's C library reads a value it cannot parse leniently, and deterministically:

| shape | example | Git |
|---|---|---|
| no designation of three or more letters | `E5`, `<AB>5`, ` EST5` | UTC |
| no offset after the designation | `garbage`, `EST` (no file) | UTC |
| an offset field out of range | `EST25`, `EST5:60`, `EST5:59:60` | held at 24 hours, 59 minutes, 59 seconds: `-2400`, `-0559`, `-0559` |
| a `+` after the sign | `JST-+9` | skipped: `+0900` |
| a `:` that no digit follows | `EST5:EDT` | the offset ends before it |
| no daylight designation, something else after the offset | `EST5x`, `IST-5:30x`, `EST5,M3.2.0,M11.1.0` | daylight saving at UTC under the rules that follow |
| after the daylight part, neither `,` nor the `M` or `J` of a rule | `EST5EDT/2`, `EST5EDT4x`, `EST5EDT;M3.2.0,M11.1.0` | both changes at 00:00 on day 0: a zone west of Greenwich reads as daylight saving (or UTC, as above) all year but its first hours; one east of it as its standard offset |
| a first rule that is no rule at all | `EST5EDT,garbage`, `EST5EDT,,M11.1.0`, `EST5EDT,366,300` | the same |
| no comma before the first rule | `XXX3YYY-J60/2,J300/2` | read as if it were there |
| a first rule and no second | `EST5EDT,M3.2.0`, `EST5EDT,M4.1.0`, `EST5EDT,M3.2.0,` | the second is `M11.1.0` |
| a second rule that is no rule at all | `EST5EDT,M3.2.0,garbage` | the second change at 00:00 on day 0 |
| a byte after a complete second rule | `EST5EDT,M3.2.0,M11.1.0x`, `…M11.1.0 ` | `,` ends the value; any other byte makes an unwritten second change time 00:00 (an explicit one stays) |
| a rule time's minutes past 59 | `…,M11.1.0/2:60` | they add up: 3:00 |
| other malformed rules: out-of-range fields (`M13.1.0`, `J0`, `M3.6.0`), incomplete ones (`M3.2`), a byte after the first rule (`M3.2.0;M11.1.0`) | | readings den does not reproduce: some daylight saving starts at UTC midnight, some a whole year, some never |
| a daylight offset out of range | `EST5EDT4:60` | changes at instants den does not reproduce |

### Dates given without a zone

- A wall-clock reading (`2024-03-10 02:30:00`, `Sun, 10 Mar 2024 02:30:00`, `03/10/2024 02:30:00`): Git takes the offset in force at the reading counted as if it were UTC, corrects it once, and checks it. Inside a change's skipped hour it takes the offset in force before the change (the smaller of the two); inside a repeated hour, the first correction decides, so a zone west of Greenwich takes the earlier instant and one east of it the later. The instant is the reading less the offset in whole minutes. Measured every 30 minutes for three hours either side of both 2024 changes of four POSIX rules, three zone files and a rule-less zone.
- `@N` and nine or more bare digits: the instant N as written, with the offset Git gives the reading N (so near a change it is not always the offset in force at N). Below 100000000 such a date is `fatal: invalid date format`, in every zone.
- A reading before the epoch in the local zone is `fatal: invalid date format`.
- With a zone (`+0100`, `Z`, `EDT`), the zone as written, whatever `TZ` says.

### Amend

An author whose stored zone is not four digits is re-read as `@SECONDS` in the local zone: the offset Git gives the reading SECONDS; below 100000000 it is `fatal: invalid date format: @SECONDS ZONE`.

## Why the refusal appeared only for some values

The issue's loop on a machine with no zone database, in a fresh repository with no identity: `TZ=EST5EDT,M3.2.0,M11.1.0` gave the timezone refusal, while `EST5EDT`, `America/New_York` and a malformed rule gave `commit missing author identity`. It was not the order of a root commit's checks. The refusal sat in `hooks_empty`, which runs before the identity is read, and asked `std.time` for the offset: a value std.time read was refused, and a value it could not read (a zone name with no database, a rule-less `EST5EDT`, which std.time does not take without a database, and any malformed value) was taken for UTC, passed, and the next check, the identity, failed. With an identity configured, those values would have been committed at `+0000`, where Git writes `-0500` for `EST5EDT` and `-0400` for `EST5EDT,garbage`. Measured at trunk: `stamp/rule-less-no-database` and `stamp/malformed-rule-word` committed `+0000`.

## den's reading

`src/commit/zone.lu`:

- `local_zone` reads `TZ` (unset: `:/etc/localtime`), and `zone_reading` chooses the spelling `std.time` is given: an empty value is UTC; `:name` becomes a path below the zone directory; a value `std.time` reads is read as it reads it; any other value goes through `lenient`, the measured reading above as a well-formed POSIX spelling, which `std.time` must then read. A file that cannot be opened or read is UTC.
- `local_offset(t)` is the offset in force at t; `wall_instant(reading)` is Git's instant and offset for a zone-less reading; `offset_text` writes whole minutes.
- `commit_format.read_date` reads a date apart from its zone (a `Reading`), so the commit side applies the local zone; `parse_date` keeps its fixed-offset contract.
- The writers already share `commit.environment_identity`, so commit, amend, tag, merge, stash, revert, cherry-pick, rebase, notes, branch, switch, reset and the transports' reflog lines all take the local zone through it. `history`'s `--date=local` check uses the same reading: a value the C library reads as UTC is UTC.

## Evidence index

### Commits

- `bc1e5ab` `commit_format.read_date`; `26b4969`, `7fe757d`, `4ed4b8e` the local zone (`zone.lu`); `3120c23` the writers and the dropped refusal.
- `c0a556d` the zone files; `4ade53c`, `2dabddd` the rows (`tools/zone-test.py`); `197cdd7` the unit rows; `944a6d2` the rows in `tools/check-commit`.
- This note, MAP, SOURCES, README and CHANGELOG follow.

### The rows

`tools/zone-test.py` (in `tools/check-commit`, both tiers), every row den's status, stdout and stderr equal to the pinned Git's plus the written objects:

- `stamp`: 71 values, a commit with no dates given: the zones of the author, committer and both reflog lines, each tool's seconds inside its own run.
- `dated`: 7 zones × 23 date forms through `GIT_*_DATE`, and three forms through `--date`: the summary, the commit and its reflog line, byte for byte.
- `wall`: 442 readings about each 2024 change, as calendar text and as `@N`.
- `amend`: 15 stored zones that are not four digits.
- `verbs`: 24 rows, tag -a, a reflogged tag, merge, stash, revert, cherry-pick, rebase, notes, branch, switch, reset and amend under two zones: every new identity and reflog line's zone and message.
- `shell`: `TZ=EST5EDT,M3.2.0,M11.1.0` exported from `~/.profile`, then `add`, `commit` and `log` in a new repository under a login shell, end to end; and each tool reads den's commit the same.
- `corpus`: 240 values made by a seeded mutation of well-formed ones, no zone database: each commit's dates at two instants are Git's, or den refuses the value by name. None is read differently from Git.

Red first: the same rows against trunk `291011d` (Linux, the pinned Git, the oracle image): 679 of 727 rows differ (the corpus came later). `commit`, `revert`, `cherry-pick` and `amend` refuse; `tag -a`, `merge`, `stash`, `rebase`, `notes`, `branch`, `switch` and `reset` write `+0000`.

The records (the gauntlet at the head and the plant, `vc23-plant-zone-utc`, which forces every local offset to zero) are in the pull request.

## Refused by name

- Daylight saving with no rules when the zone directory holds `posixrules` (the Ubuntu database does): `commit local timezone XXX3YYY: daylight saving with no change rules, read from the zone database's posixrules`. A zone name with its own file (`EST5EDT`, `PST8PDT`) is read from that file and is not refused.
- The malformed rules and out-of-range daylight offsets in the last rows of the table: `commit local timezone <TZ>: a malformed daylight-saving rule` or `…: an out-of-range daylight-saving offset`. 72 of the corpus's 240 values.

Each is refused only when a date needs the local zone: dates given with a zone never read `TZ`.

## Remaining limits

- History's `--date=local` and the other local styles still refuse a zone that is not UTC, and history still takes an unset `TZ` for UTC rather than reading `/etc/localtime`.
- The oracle's C library is the measured one. A Git built on another C library (the macOS field leg's) may read a malformed value differently; the field leg does not run these rows.
- std.time tries a complete POSIX rule before a file of the same name, where the C library tries the file first; no zone database ships a file whose name is a complete rule with another meaning.
- A zone file with leap seconds (the `right/` tree, absent from the oracle image) is untested.
