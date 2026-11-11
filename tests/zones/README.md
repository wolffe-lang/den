# Zone files for the zone rows

`tools/zone-test.py` points `TZDIR` here so that both the pinned Git and den
read the same zone database, whatever the host holds. The files are copied
byte for byte from the oracle image's tzdata (Ubuntu 24.04,
`tzdata 2026e-0ubuntu0.24.04.1`, `/usr/share/zoneinfo`). There is
deliberately no `posixrules` file: the rows that need one add it to a copy.

| file | bytes | sha256 |
|---|---:|---|
| `America/New_York` | 3552 | `e9ed07d7bee0c76a9d442d091ef1f01668fee7c4f26014c0a868b19fe6c18a95` |
| `Europe/Berlin` | 2298 | `5ee475f71a0fc1a32faeb849f8c39c6e7aa66d6d41ec742b97b3a7436b3b0701` |
| `Australia/Lord_Howe` | 1860 | `2ee7f42f1fe2247ba1de465de0bc518dfdfab4b179fb05b650531534a353ee08` |
| `Asia/Kolkata` | 285 | `e90c341036cb7203200e293cb3b513267e104a39a594f35e195254e6bc0a17cf` |
| `EST5EDT` | 2310 | `7f0cc4313d638276367438ddd04a83976ebfecb0bea05e3c05de27839df5d47d` |

The time zone database is in the public domain.
