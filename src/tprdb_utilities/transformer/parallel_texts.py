"""
Parallel-text preparation utilities for TPR-DB DataFrames.

Functions
---------
prep_parallel_texts
    Build segment-aligned bitext and tritext DataFrames from TPR-DB segment,
    source-token, and target-token tables.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd


# Sentence-final punctuation tokens used as a fallback split boundary.
_SENT_PUNCT = {"。", "！", "？", ".", "!", "?"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _to_int(x) -> int | None:
    """Robust scalar → int; returns None on failure."""
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _recover_labels(
    token_group: pd.DataFrame,
    st_seg_of: dict[int, int],
) -> list[int]:
    """Return per-token source-segment labels for *token_group*.

    *token_group* is a slice of the TT table containing the target tokens for
    one merged TTseg.  *st_seg_of* maps ``STid → STseg`` and is built from the
    ST table for the same session.

    Primary source: each token's own ``STseg`` value.
    Recovery path: when ``STseg`` is 0 or missing, resolve the label from the
    token's ``STid`` / ``SGid`` alignment field (which may look like ``"84+85"``
    for cross-segment tokens) via *st_seg_of*, taking the majority segment.

    Returns a list of ``int`` labels (``0`` = unknown / abstain).
    """
    labels: list[int] = []
    for _, tok in token_group.iterrows():
        lab = _to_int(tok.get("STseg")) or 0
        if lab == 0:
            ids = str(tok.get("SGid", tok.get("STid", ""))) or ""
            segs = [st_seg_of.get(_to_int(p)) for p in ids.split("+")]
            segs = [s for s in segs if s]
            if segs:
                lab = max(set(segs), key=segs.count)
        labels.append(lab)
    return labels


def _best_boundary(
    labels: list[int],
    seg_a: int,
    seg_b: int,
) -> tuple[int | None, int]:
    """Find split index *k* that maximises agreement with per-token labels.

    Tokens assigned to *seg_a* should fall in ``[:k]`` and tokens assigned to
    *seg_b* should fall in ``[k:]``.  Tokens labelled ``0`` abstain.

    Returns ``(k, n_labeled)``; *k* is ``None`` if no labeled tokens exist.
    """
    labeled = [(i, lbl) for i, lbl in enumerate(labels) if lbl in (seg_a, seg_b)]
    if not labeled:
        return None, 0
    best_k, best_score = None, -1
    for k in range(1, len(labels)):
        score = sum(1 for i, lbl in labeled if (lbl == seg_a) == (i < k))
        if score > best_score:
            best_k, best_score = k, score
    return best_k, len(labeled)


def _split_merged_segments(
    segments: pd.DataFrame,
    stokens: pd.DataFrame,
    ttokens: pd.DataFrame,
    min_tokens: int = 2,
    verbose: int = 1,
) -> pd.DataFrame:
    """Replace merged SG rows (``STseg`` like ``"1+2"``) with one row per
    source segment where a defensible split exists; otherwise keep the row
    whole and flag it ``Merged=True``.

    Three columns are added to every output row:

    ``Merged``
        ``True`` when the row represents two or more source segments that
        could not be split.
    ``TTidFrom``, ``TTidTo``
        First and last TT token IDs for split rows (``NaN`` otherwise).

    Parameters
    ----------
    segments:
        SG-table DataFrame for a **single participant**.
    stokens:
        ST-table DataFrame for the whole study (all participants).
    ttokens:
        TT-table DataFrame for the whole study (all participants).
    min_tokens:
        Minimum TT-token count required on each side of a proposed split.
    verbose:
        ``0`` = silent; ``≥1`` = print per-segment split/keep decisions and
        a summary line.

    Returns
    -------
    pandas.DataFrame
        Modified segment-level DataFrame.
    """
    st_by = dict(tuple(stokens.groupby(["Session"])))
    tt_by = dict(tuple(ttokens.groupby(["Session"])))
    out: list[dict] = []
    log: list[str] = []

    for _, row in segments.iterrows():
        stseg = str(row["STseg"])

        if "+" not in stseg:
            r = row.to_dict()
            r["Merged"] = False
            r["TTidFrom"] = np.nan
            r["TTidTo"] = np.nan
            out.append(r)
            continue

        ids = [int(x) for x in stseg.split("+")]
        sess = row["Session"]

        g = tt_by.get((sess,), tt_by.get(sess))
        if g is None:
            r = row.to_dict()
            r["Merged"] = True
            r["TTidFrom"] = np.nan
            r["TTidTo"] = np.nan
            out.append(r)
            log.append(f"{sess} ST {stseg}: kept merged (no TT data for session)")
            continue

        g = g[g["TTseg"].astype(str) == str(row["TTseg"])].sort_values("TTid")
        toks = g["TToken"].astype(str).tolist()
        method = None
        k = None

        if len(ids) == 2 and len(toks) >= 2 * min_tokens:
            # Strategy 1: alignment-based boundary using STid/SGid token labels.
            st_sess_pre = st_by.get((sess,), st_by.get(sess))
            if st_sess_pre is not None:
                st_seg_of = {
                    _to_int(i): _to_int(s)
                    for i, s in zip(st_sess_pre["STid"], st_sess_pre["STseg"])
                }
                k, n_lab = _best_boundary(
                    _recover_labels(g, st_seg_of), ids[0], ids[1]
                )
                if (
                    k is not None
                    and n_lab >= 4
                    and min_tokens <= k <= len(toks) - min_tokens
                ):
                    method = "alignment"

            if method is None:
                # Strategy 2: punctuation fallback — exactly one sentence-final
                # token inside the sequence (not at the very end).
                punct_pos = [
                    i + 1
                    for i, t in enumerate(toks[:-1])
                    if t in _SENT_PUNCT
                ]
                if (
                    len(punct_pos) == 1
                    and min_tokens <= punct_pos[0] <= len(toks) - min_tokens
                ):
                    k, method = punct_pos[0], "punctuation"

        if method is None:
            # Strategy 3: keep whole, flag as merged.
            r = row.to_dict()
            r["Merged"] = True
            r["TTidFrom"] = np.nan
            r["TTidTo"] = np.nan
            out.append(r)
            log.append(f"{sess} ST {stseg}: kept merged (no usable split signal)")
            continue

        st_sess = st_by.get((sess,), st_by.get(sess))
        for seg_id, sub in [(ids[0], g.iloc[:k]), (ids[1], g.iloc[k:])]:
            st_seg = (
                st_sess[st_sess["STseg"] == seg_id]
                if st_sess is not None
                else pd.DataFrame()
            )
            r = row.to_dict()
            r["STseg"] = str(seg_id)
            r["String"] = "_".join(sub["TToken"].astype(str))
            r["Merged"] = False
            r["TTidFrom"] = sub["TTid"].min()
            r["TTidTo"] = sub["TTid"].max()
            r["TokT"] = len(sub)
            for c in ("Ins", "Del", "Dur", "FixT", "TrtT"):
                if c in sub.columns:
                    r[c] = sub[c].sum()
            if not st_seg.empty:
                r["TokS"] = len(st_seg)
                r["LenS"] = int(
                    st_seg["SToken"].astype(str).str.len().sum()
                ) + max(len(st_seg) - 1, 0)
                for c in ("FixS", "TrtS"):
                    if c in st_seg.columns:
                        r[c] = st_seg[c].sum()
            r["Nedit"] = np.nan
            out.append(r)
        log.append(
            f"{sess} ST {stseg}: split by {method} at token {k} "
            f"({k}/{len(toks) - k} tokens)"
        )

    result = pd.DataFrame(out)
    if verbose:
        for entry in log:
            print("  " + entry)
        n_split = sum("split by" in entry for entry in log)
        print(
            f"  Merged-segment rows: {n_split} split, "
            f"{int(result['Merged'].sum())} kept whole (flagged Merged=True)"
        )
    return result


def _build_source_string(
    session: str,
    stseg_orig: str,
    src_lookup: dict[tuple[str, int], str],
) -> str:
    """Return the space-tokenised source-segment string.

    For merged-and-unsplit rows (``stseg_orig`` like ``"1+2"``), the strings
    for each component segment are concatenated with a space.
    """
    if "+" in stseg_orig:
        parts = stseg_orig.split("+")
        segs = [
            src_lookup.get((session, _to_int(p)), "")
            for p in parts
            if _to_int(p) is not None
        ]
        return " ".join(s for s in segs if s)
    stseg_int = _to_int(stseg_orig)
    return "" if stseg_int is None else src_lookup.get((session, stseg_int), "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def prep_parallel_texts(
    sg_df: pd.DataFrame,
    st_df: pd.DataFrame,
    tt_df: pd.DataFrame,
    prep_bitexts: bool = True,
    prep_tritexts: bool = True,
    min_tokens: int = 2,
    verbose: int = 1,
) -> dict[str, pd.DataFrame]:
    """Build segment-aligned bitext and tritext DataFrames from TPR-DB tables.

    Given the three segment-level and token-level tables for a single study
    (the output of :func:`read_TPRDB_tables` called with extensions ``"sg"``,
    ``"st"``, and ``"tt"`` respectively), this function:

    1. Splits any *merged* source segments (``STseg`` values like ``"1+2"``)
       back into individual segments using token-level alignment evidence or
       sentence-final punctuation as a fallback.
    2. Assembles segment-aligned DataFrames — *bitexts* (source text paired
       with one participant's translation) and/or *tritexts* (source text
       paired with two participants' translations) — suitable for automatic
       MT evaluation metrics such as BLEU or COMET.

    Parameters
    ----------
    sg_df : pandas.DataFrame
        Concatenated SG-table DataFrame for the study, as returned by
        ``read_TPRDB_tables(..., extension="sg")``.
    st_df : pandas.DataFrame
        Concatenated ST-table DataFrame for the study, as returned by
        ``read_TPRDB_tables(..., extension="st")``.
    tt_df : pandas.DataFrame
        Concatenated TT-table DataFrame for the study, as returned by
        ``read_TPRDB_tables(..., extension="tt")``.
    prep_bitexts : bool, optional
        When ``True`` (default), include one bitext DataFrame per participant
        in the output.
    prep_tritexts : bool, optional
        When ``True`` (default), include one tritext DataFrame per unique
        pair of participants in the output.  Only source segments translated
        by *both* participants appear (inner join on ``Study``, ``Task``,
        ``Text``, and ``STseg``).
    min_tokens : int, optional
        Minimum number of target tokens required on each side of a proposed
        split when resolving merged segments.  Default ``2``.
    verbose : int, optional
        Verbosity level for the segment-splitting step.
        ``0`` = silent; ``≥1`` = print split/keep decisions per participant.

    Returns
    -------
    dict[str, pandas.DataFrame]
        A dictionary mapping string keys to aligned DataFrames.

        **Bitext keys** follow the pattern ``"ST_{part}"``, e.g.::

            parallel_texts["ST_P01"]   # source text + P01's translations

        **Tritext keys** follow the pattern ``"ST_{p1}_{p2}"``, e.g.::

            parallel_texts["ST_P01_P02"]  # source + P01's + P02's translations

        Participant codes in tritext keys are sorted lexicographically, so
        ``"ST_P01_P02"`` is always used rather than ``"ST_P02_P01"``.

        Each DataFrame contains the following columns:

        ================  ====================================================
        ``Study``         Study identifier (e.g. ``"RUC17"``).
        ``Task``          Task type (e.g. ``"P"`` for production).
        ``Text``          Numeric text identifier within the study.
        ``STseg``         Source-segment number (integer; ``pd.NA`` for merged
                          segments that could not be split).
        ``String_ST``     Space-tokenised source-language segment text.
                          For merged-and-unsplit rows the strings of all
                          component segments are concatenated.
        ``String_{X}``    Space-tokenised translation by participant *X* (one
                          column per participant in the DataFrame, e.g.
                          ``String_P01``).
        ================  ====================================================

        Rows are sorted by ``(Task, Text, STseg)``.  Target strings are
        derived from the SG-table ``String`` column (token separator ``_``
        replaced with a space).  Source strings are reconstructed from the
        ST-table ``SToken`` column, joining tokens in ``STid`` order with a
        single space.

    Notes
    -----
    Merged segments that cannot be split (no alignment evidence and no single
    sentence-final punctuation boundary) appear in **bitexts** as a single
    row with ``Merged=True`` semantics: ``STseg`` is ``pd.NA``, ``String_ST``
    is the concatenation of all component source-segment strings, and
    ``String_{part}`` is the combined translation.  Such rows are **excluded**
    from tritexts because a reliable cross-participant alignment key is not
    available.

    The split is attempted only when exactly two source segments were merged
    and the target-token group is long enough to satisfy *min_tokens* on both
    sides.

    Examples
    --------
    >>> from tprdb_utilities import read_TPRDB_tables, prep_parallel_texts
    >>> path = "/path/to/tprdb-mothership-clone"
    >>> sg = read_TPRDB_tables(["RUC17"], "sg", path)
    >>> st = read_TPRDB_tables(["RUC17"], "st", path)
    >>> tt = read_TPRDB_tables(["RUC17"], "tt", path)
    >>> parallel_texts = prep_parallel_texts(sg, st, tt)
    >>>
    >>> # Bitext: one row per source segment translated by P01
    >>> parallel_texts["ST_P01"]
    >>>
    >>> # Tritext: source segments translated by both P01 and P02
    >>> parallel_texts["ST_P01_P02"]
    >>>
    >>> # Access just the text columns for evaluation
    >>> bitext = parallel_texts["ST_P01"][["String_ST", "String_P01"]]
    >>> tritext = parallel_texts["ST_P01_P02"][["String_ST", "String_P01", "String_P02"]]
    """
    participants = sorted(sg_df["Part"].dropna().astype(str).unique())

    # ------------------------------------------------------------------
    # Build source-string lookup: (session, stseg_int) → "tok1 tok2 …"
    # ------------------------------------------------------------------
    src_lookup: dict[tuple[str, int], str] = {}
    for (session, stseg), grp in st_df.groupby(["Session", "STseg"]):
        stseg_int = _to_int(stseg)
        if stseg_int is None:
            continue
        tokens = grp.sort_values("STid")["SToken"].astype(str).tolist()
        src_lookup[(str(session), stseg_int)] = " ".join(tokens)

    # ------------------------------------------------------------------
    # Split merged segments per participant; normalise STseg to Int64
    # ------------------------------------------------------------------
    split_sgs: dict[str, pd.DataFrame] = {}
    for part in participants:
        if verbose:
            print(f"[{part}] Resolving merged segments...")
        part_sg = sg_df[sg_df["Part"].astype(str) == part].copy()
        split_sg = _split_merged_segments(
            part_sg, st_df, tt_df, min_tokens=min_tokens, verbose=verbose
        )
        # Preserve original STseg string for source-string lookup (handles "1+2").
        split_sg["_STseg_orig"] = split_sg["STseg"].astype(str)
        # Normalise to nullable integer; merged-and-unsplit rows become pd.NA.
        split_sg["STseg"] = pd.to_numeric(
            split_sg["STseg"], errors="coerce"
        ).astype("Int64")
        split_sgs[part] = split_sg

    result: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # Bitexts: source text + one participant's translation
    # ------------------------------------------------------------------
    if prep_bitexts:
        for part in participants:
            split_sg = split_sgs[part]
            string_st = split_sg.apply(
                lambda row: _build_source_string(
                    str(row.get("Session", "")),
                    str(row.get("_STseg_orig", "")),
                    src_lookup,
                ),
                axis=1,
            )
            string_part = (
                split_sg["String"].astype(str).str.replace("_", " ", regex=False)
            )
            df = pd.DataFrame(
                {
                    "Study": split_sg["Study"].to_numpy(),
                    "Task": split_sg["Task"].to_numpy(),
                    "Text": split_sg["Text"].to_numpy(),
                    "STseg": split_sg["STseg"].to_numpy(),
                    "String_ST": string_st.to_numpy(),
                    f"String_{part}": string_part.to_numpy(),
                }
            )
            df["STseg"] = pd.array(df["STseg"], dtype="Int64")
            df = df.sort_values(["Task", "Text", "STseg"]).reset_index(drop=True)
            result[f"ST_{part}"] = df

    # ------------------------------------------------------------------
    # Tritexts: source text + two participants' translations (inner join)
    # ------------------------------------------------------------------
    if prep_tritexts:
        for p1, p2 in itertools.combinations(participants, 2):
            sg1 = split_sgs[p1][
                ["Study", "Task", "Text", "STseg", "Session", "String"]
            ].copy()
            sg2 = split_sgs[p2][
                ["Study", "Task", "Text", "STseg", "Session", "String"]
            ].copy()

            merged = pd.merge(
                sg1,
                sg2,
                on=["Study", "Task", "Text", "STseg"],
                suffixes=(f"_{p1}", f"_{p2}"),
                how="inner",
            )

            if merged.empty:
                continue

            string_st = merged.apply(
                lambda row: src_lookup.get(
                    (
                        str(row.get(f"Session_{p1}", "")),
                        _to_int(row["STseg"]),
                    ),
                    "",
                ),
                axis=1,
            )
            df = pd.DataFrame(
                {
                    "Study": merged["Study"].to_numpy(),
                    "Task": merged["Task"].to_numpy(),
                    "Text": merged["Text"].to_numpy(),
                    "STseg": merged["STseg"].to_numpy(),
                    "String_ST": string_st.to_numpy(),
                    f"String_{p1}": merged[f"String_{p1}"]
                    .astype(str)
                    .str.replace("_", " ", regex=False)
                    .to_numpy(),
                    f"String_{p2}": merged[f"String_{p2}"]
                    .astype(str)
                    .str.replace("_", " ", regex=False)
                    .to_numpy(),
                }
            )
            df["STseg"] = pd.array(df["STseg"], dtype="Int64")
            df = df.sort_values(["Task", "Text", "STseg"]).reset_index(drop=True)
            result[f"ST_{p1}_{p2}"] = df

    return result
