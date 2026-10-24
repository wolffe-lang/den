# Exact reviews

There are **zero accepted review rows** at M0. Refusals are the distinct
not-yet class, not parity and not an approval to differ.

A proposed `CASE.json` must contain `case_sha256` (the SHA-256 of Python's
sorted-key JSON case encoding), `git`, `den`, `reason` and `issue_or_ruling`.
Each complete result is `{stdout, stderr, status, repository}`. stdout/stderr
are hex bytes; repository maps every file below .git to its mode and complete
hex contents (or a symlink target). The runner writes these observations to
`target/runs/CASE/{git,den}.json`; it never promotes them into a review.

A reviewer must approve the exact difference and its cited issue/ruling.
Change either case or result and the review stops matching. Equal results
cannot consume a review. No regexes, PID wildcards, ignored index fields or
blanket excluded paths are supported. A later need for a typed exception is
a reviewed API change with its own planted proof, not an untracked filter.

The README's counts must be updated when a reviewed row joins or retires.
Use `tools/oracle --strict` to make all not-yet rows fail as well.
