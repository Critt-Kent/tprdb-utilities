# tprdb-utilities

[![PyPI version](https://img.shields.io/pypi/v/tprdb-utilities.svg)](https://pypi.org/project/tprdb-utilities/)
[![Python](https://img.shields.io/pypi/pyversions/tprdb-utilities.svg)](https://pypi.org/project/tprdb-utilities/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python toolkit for downloading and reading data tables from the
[CRITT Translation Process Research Database (TPR-DB)](https://critt.as.kent.edu/tpr/).

These functions cover the full workflow:

| Function | What it does |
|---|---|
| `fetch_TPRDB_tables` | Downloads study tables from the CRITT API and saves them to a local directory structure |
| `read_TPRDB_tables` | Reads those tables from a local clone into a single `pandas.DataFrame` |
| `prep_parallel_texts` | Builds segment-aligned bitext and tritext DataFrames ready for MT evaluation |
| `recompute_pause_based_metrics` | Recomputes typing-burst metrics (TB, TG, TD) for a custom pause threshold and appends them to an SG DataFrame |
| `ST_entropy_df` | Computes word translation entropy metrics for a Source Token (ST) DataFrame |
| `SG_entropy_df` | Aggregates word translation entropy metrics onto a Segment (SG) DataFrame |
| `DF_entropy_df` | Aggregates word translation entropy metrics onto any DataFrame with a `SGid` column |

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
    studies=["DG21"],
    extensions=["ss", "st"],
    public=True,
)
```

**Private study** (requires your TPR-DB username and API token):

```python
from tprdb_utilities import fetch_TPRDB_tables

fetch_TPRDB_tables(
    path="/path/to/local/data",
    studies=["MYSTUDY"],
    extensions=["st"],
    public=False,
    username="myTPRDBusername",   # case-sensitive, must match your account
    token="my-api-token",
)
```

After downloading, the function always prints a summary like this:

```
DG21 [ss]: Done fetching (^_^)
DG21 [st]: Done fetching (^_^)

=== fetch_TPRDB_tables Summary ===
StudyID  : DG21
Clone dir: /path/to/local/data/tprdb-mothership-clone
User dir : PUBLIC

Extension  Status            Time
---------  ----------------  ------
ss         Downloaded        1.23s
st         Downloaded        0.98s

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
The timestamp is read once per study, before the first request, so all
conditional requests in the same call are checked against the state of your
clone as it was before the call. The summary will reflect the outcome:

```
Extension  Status            Time
---------  ----------------  ------
ss         Up to date (304)  0.21s
st         Updated           1.05s
```

**Stale clones are re-synced automatically.** If a response reveals that the
server data for a study is newer than your local clone (the study's tables
were regenerated on the server), every extension already present locally for
that study is re-downloaded — even extensions you did not request in that
call. This guarantees that all table files in the clone stay in step with the
study's `studySummary.xml`, and therefore with the data on the server.
Re-downloaded extensions appear in the summary as `Auto-updated`:

```
Extension  Status             Time
---------  -----------------  ------
ss         Updated            1.05s
kd         Auto-updated.      2.31s
```

---

### 2 — Read data (reader)

Use the `path` and `user` values printed by `fetch_TPRDB_tables` at the end of
its summary output.

**Public study** (`user="PUBLIC"`):

```python
from tprdb_utilities import read_TPRDB_tables

df = read_TPRDB_tables(
    studies=["DG21", "AR22"],
    extension="st",
    path="/path/to/local/data/tprdb-mothership-clone",
    user="PUBLIC",
)
```

**Private study** (`user="<your TPR-DB username>"`):

```python
from tprdb_utilities import read_TPRDB_tables

df = read_TPRDB_tables(
    studies=["MYSTUDY"],
    extension="st",
    path="/path/to/local/data/tprdb-mothership-clone",
    user="USER_DIRECTORY_NAME",
)
```

---

### 3 — Transform data (transformer)

Once you have the SG, ST, and TT tables loaded, `prep_parallel_texts` aligns
translation segments across participants and builds parallel-text DataFrames
suitable for automatic MT evaluation with tools like BLEU or COMET.

```python
from tprdb_utilities import read_TPRDB_tables, prep_parallel_texts

path = "/path/to/local/data/tprdb-mothership-clone"

sg = read_TPRDB_tables(["RUC17"], "sg", path)
st = read_TPRDB_tables(["RUC17"], "st", path)
tt = read_TPRDB_tables(["RUC17"], "tt", path)

parallel_texts = prep_parallel_texts(sg, st, tt)
```

The return value is a dictionary. Keys follow two patterns:

| Key pattern | Contains |
|---|---|
| `"ST_{part}"` | Bitext — source text + one participant's translations |
| `"ST_{p1}_{p2}"` | Tritext — source text + two participants' translations |

```python
# Bitext: source text aligned with P01's translations
parallel_texts["ST_P01"]
# Study  Task  Text  STseg  String_ST                   String_P01
# RUC17  P     4     1      Developing countries are …  发展中国家不愿 …
# …

# Tritext: source text aligned with P01's and P02's translations
parallel_texts["ST_P01_P02"]
# Study  Task  Text  STseg  String_ST                   String_P01       String_P02
# RUC17  P     4     1      Developing countries are …  发展中国家不愿 …  虽然我们可以 …
# …

# Extract just the text columns for evaluation
bitext = parallel_texts["ST_P01"][["String_ST", "String_P01"]]
tritext = parallel_texts["ST_P01_P02"][["String_ST", "String_P01", "String_P02"]]
```

By default both bitexts and tritexts are produced. To generate only one kind:

```python
# Bitexts only
parallel_texts = prep_parallel_texts(sg, st, tt, prep_tritexts=False)

# Tritexts only
parallel_texts = prep_parallel_texts(sg, st, tt, prep_bitexts=False)
```

Tritext DataFrames contain only source segments that **both** participants
translated (inner join on study, task, text, and segment number). Merged
segments that could not be split are included in bitexts (with the component
source strings concatenated) but excluded from tritexts.

---

### 4 — Recompute pause-based metrics (transformer)

SG tables already include typing-burst metrics computed at the standard 1000 ms
pause threshold (`TB1000`, `TG1000`, `TD1000`). Use `recompute_pause_based_metrics`
to compute the same three metrics at any other threshold and append them as new
columns.

```python
from tprdb_utilities import read_TPRDB_tables, recompute_pause_based_metrics

path = "/path/to/local/data/tprdb-mothership-clone"

sg = read_TPRDB_tables(["BML12"], "sg", path)
kd = read_TPRDB_tables(["BML12"], "kd", path)

sg_500 = recompute_pause_based_metrics(sg, kd, threshold=500)
```

This appends three new columns to the returned DataFrame:

| Column | Description |
|---|---|
| `TB500` | Number of typing bursts per segment |
| `TG500` | Total inter-burst pause time (ms) per segment |
| `TD500` | Total active typing duration (ms) per segment |

The column names reflect the threshold you pass in, so `threshold=250` would
add `TB250`, `TG250`, and `TD250`.  Calling with `threshold=1000` raises a
`ValueError` since those columns are already in the table.

If you call the function a second time with the same threshold, the existing
columns are silently replaced (the call is idempotent).

---

### 5 — Recompute word translation entropy (transformer)

Word translation entropy quantifies how consistently a source token is
rendered across participants: low entropy means everyone converged on (nearly)
the same translation, high entropy means renderings vary widely. Three
functions work together to compute and propagate these metrics.

`ST_entropy_df` computes the entropy values from **ST** (source-token)
table and returns a new ST DataFrame with the metrics added. `SG_entropy_df`
and `DF_entropy_df` then aggregate those per-token values up to the **SG**
(segment) table or to any other DataFrame that references source tokens via a
`SGid` column, so `ST_entropy_df` must always be run first.

```python
from tprdb_utilities import read_TPRDB_tables, ST_entropy_df, SG_entropy_df, DF_entropy_df

path = "/path/to/local/data/tprdb-mothership-clone"

st = read_TPRDB_tables(["RUC17"], "st", path)
sg = read_TPRDB_tables(["RUC17"], "sg", path)

# 1. Compute entropy per source token (must run first)
st = ST_entropy_df(st)

# 2a. Aggregate the entropy metrics to the segment level
sg = SG_entropy_df(sg, st)

# 2b. Or aggregate them onto any DataFrame with a 'SGid' column that
#     references one or more STid values (e.g. a word-alignment table)
# df = DF_entropy_df(df, st)
```

`ST_entropy_df` groups sessions by source text (parsed from the session name)
and requires every session of the same text to share identical source tokens;
texts that don't match are skipped and reported as an error. It appends the
following columns to the returned ST DataFrame:

| Column | Description |
|---|---|
| `Count` | Number of occurrences counted for this source token |
| `AltT`, `ProbT`, `InfT` | Number of alternatives, probability, and information content of the target-group rendering |
| `HTra`, `HTraN` | Target-group entropy (raw and normalized) |
| `AltS`, `ProbS`, `InfS` | Alternatives, probability, and information content of the source-group grouping |
| `HSgrp`, `HSgrpN` | Source-group entropy (raw and normalized) |
| `AltC`, `ProbC`, `InfC` | Alternatives, probability, and information content of the cross-alignment grouping |
| `HCross`, `HCrossN` | Cross entropy (raw and normalized) |
| `AltSTC`, `ProbSTC`, `InfSTC` | Alternatives, probability, and information content of the joint source/target/cross grouping |
| `HSTC`, `HSTCN` | Joint source/target/cross entropy (raw and normalized) |

`SG_entropy_df` and `DF_entropy_df` both expect a DataFrame paired with an ST
table that has already been processed by `ST_entropy_df`, and append four
aggregated columns:

| Column | Description |
|---|---|
| `HTot` | Sum of `HTra` across the source tokens in the segment/unit |
| `HTraN` | Mean of `HTraN` across the source tokens in the segment/unit |
| `InfS` | Mean of `InfS` across the source tokens in the segment/unit |
| `InfT` | Mean of `InfT` across the source tokens in the segment/unit |

`SG_entropy_df` matches tokens to segments by splitting each `STseg` value on
`+` (to handle merged segments). `DF_entropy_df` instead splits `SGid` on `+`
and looks up the corresponding `STid` values in the ST table, skipping rows
whose `SGid` is `'---'` or `'0'`.

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
    │           ├── session1.st
    │           └── ...
    └── <username>/             ← private studies
        └── <StudyID>/
            ├── studySummary.xml
            └── Tables/
                ├── session1.st
                └── ...
```

Each zip response bundles a `studySummary.xml` file alongside the table files.
`fetch_TPRDB_tables` places it in the `<StudyID>/` directory (one level above
`Tables/`) and uses it on subsequent calls to detect whether the server data
has changed. When it has, all locally present extensions for the study are
re-downloaded so every table file matches the new `studySummary.xml`.

`read_TPRDB_tables` expects this exact layout, so the two functions are designed
to work together seamlessly.

---

## Supported Table Extensions

`ag`, `au`, `ex`, `fd`, `fu`, `hc`, `hs`, `kd`, `ku`, `pu`, `sg`, `ss`, `st`, `tt`
---

## License

MIT — see [LICENSE](LICENSE).

