# vc23 — directories the walk cannot open (den#80)

`den status` stopped with a bare `fatal: denied` (exit 128) when the work tree held a directory it could not open, and so did `add -A`, `add .` and `commit -a` whenever the walk met one. Git warns, names the directory, and carries on. Now den's work-tree walk does what the pinned Git does with a directory or path it may not open, for status and for the commands that walk the tree, and it leaves an ignored directory unopened when it adds, as Git does.

Footprint: module

## Forbidden

Clean room: Git's documentation and black-box runs of the pinned Git 2.56.0 only, as an unprivileged user in the oracle container (root inside it bypasses permissions, so both tools run as uid 65534). No Git or other implementation source was read. Organisation code read: den, and wolf-std's `fs.entries`.

## Inputs verified

- **Base:** den trunk `291011d`, branch `vc23-denied`.
- **Toolchain:** wolf 0.2.36, lupin 0.1.58, wolf-std `d4a4d4c`, unchanged.
- **Oracle:** Git 2.56.0, executable `c4848492…`, checked by digest.

## What Git does, measured

Ten shapes (`tools/denied-test.py`), each under status in its long, short, porcelain, `-uall`, `-uno` and `--ignored` forms, `add -A`, `add .`, `add -u` and `commit -a`:

- **A directory that cannot be listed** (mode 000, or 111: searchable, not readable): when untracked files are looked for, `warning: could not open directory 'DIR/': Permission denied` on stderr, and the walk goes on as if the directory were empty; exit 0. An empty-looking directory is not listed as untracked, so the issue's `nt-locked.tmp/locked` gives the warning and no `??` row (the issue expected `?? nt-locked.tmp/`; the pinned Git does not print it). Several such directories warn in the order the walk meets them: the host's listing order, depth first. `status -uno`, `add -u` and `commit -a` look for no untracked files and print no warning.
- **Tracked paths below it** are looked up by name: one that can be is compared as usual (a 111 directory's tracked file is clean); one whose lookup is denied (below a 000 directory) is `PATH: Permission denied` and unchanged. Status prints those lines before the walk's warnings.
- **An ignored directory** is never opened by status or add: no warning. `status --ignored` opens it, warns, and lists nothing for it.
- **A directory that can be listed but not searched** (mode 444): its entries are seen but cannot be looked up, and its `.gitignore` cannot be read: `warning: unable to access 'DIR/.gitignore': Permission denied`. Status lists the entries as untracked (`?? rdonly/`, or `?? rdonly/x` with `-uall`); add stops with `fatal: unable to stat 'rdonly/x': Permission denied`, exit 128.

## den's walk

`src/worktree/scan.lu`, `walk_submodules`: a listing that is denied is the warning above when untracked files are wanted, and the tracked paths below are visited by name; a denied lookup is the notice and an unchanged entry for status. An entry that cannot be looked up takes its kind from the listing for status, and is Git's fatal line for a full walk. Subdirectories are entered depth first in listing order, so warnings come in Git's order. `add` passes `skip_ignored` (unless `-f`), so an ignored directory with no tracked path below it is not opened; the walk's warnings now reach `add`'s output. `src/ignore/query.lu`: a work-tree `.gitignore` that cannot be looked up or opened for want of permission is the warning above and no rules.

## Evidence index

### Commits

Listed in the pull request.

### The rows

`tools/denied-test.py` (in `tools/check-worktree`, both tiers): 100 rows, ten shapes by ten commands, each den's status, stdout and stderr equal to Git's, and the index and HEAD tree each command leaves; eight are the named refusals below, with the index and tree unchanged. Red first at trunk `291011d`: every row that opens a denied directory or path ends `fatal: denied` in den.

## Refused by name

A tracked path below a directory that cannot be listed, whose lookup is denied, in a walk that would stage it: `add -A`, `add .`, `add -u` and `commit -a` refuse with `worktree tracked path PATH: Permission denied` and change nothing. Git keeps the entry, prints `PATH: Permission denied` once and goes on (staging or committing the rest). Status matches Git here. Doing the same in den needs the staging and commit paths to carry an entry they could not look at, and commit to print a walk notice once across its three walks; it is left as a refusal rather than an approximation.

## Remaining limits

- Other I/O failures in the walk (an `io` row, a file that can be looked up but not read) still end in a bare `fatal: io` or `fatal: denied`, not Git's message naming the path and the operation; den#80's second half stays open for them.
- `stash -u` and `ls-files -o`, which Git also runs through this walk, stay refused by name as before.
- Not this lane's: `add -A --dry-run` lists a tracked file whose stat changed but whose content did not; Git does not.
