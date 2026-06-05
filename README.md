# tprdb-utilities

[![PyPI version](https://img.shields.io/pypi/v/tprdb-utilities.svg)](https://pypi.org/project/tprdb-utilities/)
[![Python](https://img.shields.io/pypi/pyversions/tprdb-utilities.svg)](https://pypi.org/project/tprdb-utilities/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python toolkit for downloading and reading data tables from the
[CRITT Translation Process Research Database (TPR-DB)](https://critt.as.kent.edu/tpr/).

Two functions cover the full workflow:

| Function | What it does |
|---|---|
| `fetch_TPRDB_tables` | Downloads study tables from the CRITT API and saves them to a local directory structure |
| `read_TPRDB_tables` | Reads those tables (locally or on the CRITT server) into a single `pandas.DataFrame` |

---

## Installation

```bash
# pip
pip install tprdb-utilities

# uv
uv add tprdb-utilities

# poetry
poetry add tprdb-utilities
```

---

## Quick Start

### 1 — Download data (fetcher)

**Public study** (no credentials needed):

```python
from tprdb_utilities import fetch_TPRDB_tables

fetch_TPRDB_tables(
    path="/path/to/local/data",
    StudyID="DG21",
    extensions=["ss", "st"],
    public=True,
)
```

**Private study** (requires your TPR-DB username and API token):

```python
from tprdb_utilities import fetch_TPRDB_tables

fetch_TPRDB_tables(
    path="/path/to/local/data",
    StudyID="MYSTUDY",
    extensions=["st"],
    public=False,
    username="myTPRDBusername",   # case-sensitive, must match your account
    token="my-api-token",
)
```

After downloading, the function always prints a summary like this:

```
=== fetch_TPRDB_tables Summary ===
StudyID  : DG21
Clone dir: /path/to/local/data/tprdb-mothership-clone
User dir : PUBLIC

Extension  Status            Time
---------  ----------------  ------
kd         Downloaded        1.23s
ss         Downloaded        0.98s

To read these files with read_TPRDB_tables:
  path      = "/path/to/local/data/tprdb-mothership-clone"
  user      = "PUBLIC"
  studies   = ["DG21"]
```

Copy those argument values directly into `read_TPRDB_tables`.

**Subsequent calls are bandwidth-efficient.** When files for an extension are
already present, `fetch_TPRDB_tables` sends the `X-Client-Tables-Timestamp`
header (sourced from the `studySummary.xml` bundled with the study). The server
returns `304 Not Modified` when nothing has changed, so no data is transferred.
The summary will reflect the outcome:

```
Extension  Status            Time
---------  ----------------  ------
kd         Up to date (304)  0.21s
ss         Updated           1.05s
```

---

### 2 — Read data (reader)

**From a local clone** (`mothership=False`) — after running `fetch_TPRDB_tables`:

```python
from tprdb_utilities import read_TPRDB_tables

df = read_TPRDB_tables(
    studies=["DG21", "AR22"],
    extension="kd",
    mothership=False,
    path="/path/to/local/data/tprdb-mothership-clone",
    user="PUBLIC",
)
```

**Directly on the CRITT TPR-DB server** (`mothership=True`):

```python
from tprdb_utilities import read_TPRDB_tables

df = read_TPRDB_tables(
    studies=["DG21", "AR22"],
    extension="kd",
    mothership=True,   # path is set automatically; no path argument needed
)
```

---

## Directory Structure

`fetch_TPRDB_tables` creates the following layout under `path`:

```
<path>/
└── tprdb-mothership-clone/
    ├── PUBLIC/                  ← public studies
    │   └── <StudyID>/
    │       ├── studySummary.xml
    │       └── Tables/
    │           ├── session1.kd
    │           └── ...
    └── <username>/             ← private studies
        └── <StudyID>/
            ├── studySummary.xml
            └── Tables/
                ├── session1.kd
                └── ...
```

Each zip response bundles a `studySummary.xml` file alongside the table files.
`fetch_TPRDB_tables` places it in the `<StudyID>/` directory (one level above
`Tables/`) and uses it on subsequent calls to detect whether the server data
has changed.

`read_TPRDB_tables` with `mothership=False` expects this exact layout, so the
two functions are designed to work together seamlessly.

---

## Supported Table Extensions

`ag`, `au`, `ex`, `fd`, `fu`, `hc`, `hs`, `kd`, `ku`, `pu`, `sg`, `ss`, `st`, `tt`
---

## License

MIT — see [LICENSE](LICENSE).

