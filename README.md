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
    extension=["kd", "ss"],
    public=True,
)
```

**Private study** (requires your TPR-DB username and API token):

```python
from tprdb_utilities import fetch_TPRDB_tables

fetch_TPRDB_tables(
    path="/path/to/local/data",
    StudyID="MYSTUDY",
    extension=["kd"],
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
User dir : TPRDB

Extension  Status      Time
---------  ----------  ------
kd         Downloaded  1.23s
ss         Downloaded  0.98s

To read these files with read_TPRDB_tables:
  path      = "/path/to/local/data/tprdb-mothership-clone"
  user      = "TPRDB"
  studies   = ["DG21"]
```

Copy those argument values directly into `read_TPRDB_tables`.

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
    user="TPRDB",
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
    ├── TPRDB/                  ← public studies
    │   └── <StudyID>/
    │       └── Tables/
    │           ├── session1.kd
    │           └── ...
    └── <username>/             ← private studies
        └── <StudyID>/
            └── Tables/
                ├── session1.kd
                └── ...
```

`read_TPRDB_tables` with `mothership=False` expects this exact layout, so the
two functions are designed to work together seamlessly.

---

## Supported Table Extensions

`ss`, `sg`, `st`, `tt`, `kd`, `fd`, `au`, `pu`, `hof`, `pol`

---

## License

MIT — see [LICENSE](LICENSE).

