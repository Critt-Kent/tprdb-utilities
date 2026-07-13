"""
Pause-based typing metric utilities for TPR-DB DataFrames.

Functions
---------
recompute_pause_based_metrics
    Recompute typing-burst metrics (TB, TG, TD) for a custom pause threshold
    and append them to an SG DataFrame.
"""

from __future__ import annotations

import warnings

import pandas as pd


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compute_burst_metrics_for_session(
    sg_session: pd.DataFrame,
    kd_session: pd.DataFrame,
    threshold: int,
) -> pd.DataFrame:
    """Compute typing-burst metrics for one study session at a given pause threshold.

    Iterates through keystrokes in chronological order, tracking burst
    boundaries: a new burst begins whenever the inter-keystroke interval (IKI)
    is >= *threshold* milliseconds, or when the active target segment changes.

    Parameters
    ----------
    sg_session:
        SG-table rows for a single study session.  ``TTseg`` must already be
        ``str`` type.
    kd_session:
        KD-table rows for the same session, in chronological keystroke order.
        ``TTseg`` must already be ``str`` type.
    threshold:
        Pause threshold in milliseconds.

    Returns
    -------
    pandas.DataFrame
        One row per unique ``TTseg`` found in *sg_session*, with columns
        ``TTseg``, ``TB{threshold}``, ``TG{threshold}``, and ``TD{threshold}``.
        Segments with no matching keystrokes receive zero for all three metrics.
    """
    if kd_session.empty:
        warnings.warn(
            f"recompute_pause_based_metrics: no keystrokes found for session "
            f"{sg_session['StudySession'].iloc[0]!r}; metrics will be zero.",
            stacklevel=4,
        )
        return pd.DataFrame({
            "TTseg": sg_session["TTseg"].unique(),
            f"TB{threshold}": 0,
            f"TG{threshold}": 0,
            f"TD{threshold}": 0,
        })

    # ------------------------------------------------------------------
    # Initialise per-segment accumulators and a keystroke → segment map.
    #
    # seg_stats: SG TTseg group → {bursts, gap_total, duration, burst_start}
    #   burst_start is the Time of the first keystroke in the current burst;
    #   it is an internal bookkeeping value and is not included in the output.
    #
    # seg_key_map: individual KD TTseg value → SG TTseg group.
    #   Handles merged segments: SG may list TTseg as "3+4" while KD rows
    #   carry individual values "3" or "4"; both map to the group "3+4".
    # ------------------------------------------------------------------
    seg_stats: dict[str, dict[str, int]] = {}
    seg_key_map: dict[str, str] = {}

    for tt_seg in sg_session["TTseg"].unique():
        seg_stats[tt_seg] = {
            "bursts": 0,
            "gap_total": 0,
            "duration": 0,
            "burst_start": 0,
        }
        for component in tt_seg.split("+"):
            seg_key_map[component] = tt_seg

    active_seg: str = ""
    last_time: int = 0

    for row in kd_session.itertuples():
        kd_tt_seg: str = str(row.TTseg)
        current_time: int = int(row.Time)  # type: ignore[arg-type]

        if kd_tt_seg not in seg_key_map:
            warnings.warn(
                f"recompute_pause_based_metrics: keystroke {row.Char!r} belongs "
                f"to segment {kd_tt_seg!r} which has no matching SG entry; skipping.",
                stacklevel=4,
            )
            continue

        new_seg = seg_key_map[kd_tt_seg]

        if active_seg == "":
            # First keystroke: open the first segment.
            active_seg = new_seg
            seg_stats[active_seg]["burst_start"] = current_time

        elif new_seg != active_seg:
            # Segment transition: close the previous burst, open the next.
            seg_stats[active_seg]["bursts"] += 1
            seg_stats[active_seg]["duration"] += (
                last_time - seg_stats[active_seg]["burst_start"]
            )
            active_seg = new_seg
            seg_stats[active_seg]["burst_start"] = current_time

        else:
            # Continuing within the same segment.
            inter_keystroke_interval = current_time - last_time
            if inter_keystroke_interval >= threshold:
                # Pause long enough to end the current burst and start a new one.
                seg_stats[active_seg]["bursts"] += 1
                seg_stats[active_seg]["gap_total"] += inter_keystroke_interval
                seg_stats[active_seg]["duration"] += (
                    last_time - seg_stats[active_seg]["burst_start"]
                )
                seg_stats[active_seg]["burst_start"] = current_time

        last_time = current_time

    # Close the final open burst.
    if active_seg:
        seg_stats[active_seg]["bursts"] += 1
        seg_stats[active_seg]["duration"] += (
            last_time - seg_stats[active_seg]["burst_start"]
        )

    records = [
        {
            "TTseg": tt_seg,
            f"TB{threshold}": stats["bursts"],
            f"TG{threshold}": stats["gap_total"],
            f"TD{threshold}": stats["duration"],
        }
        for tt_seg, stats in seg_stats.items()
    ]
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def recompute_pause_based_metrics(
    sg_df: pd.DataFrame,
    kd_df: pd.DataFrame,
    threshold: int,
) -> pd.DataFrame:
    """Add pause-based typing metrics to an SG DataFrame for a custom threshold.

    TPR-DB SG tables ship with typing-burst metrics pre-computed at a 1000 ms
    pause threshold (``TB1000``, ``TG1000``, ``TD1000``).  This function
    recomputes the same three metrics for any other threshold and appends them
    as new columns.

    A typing burst is an uninterrupted run of keystrokes: a new burst begins
    whenever the inter-keystroke interval (IKI) is >= *threshold* ms, or when
    typing moves to a different target segment.  The three output metrics per
    segment are:

    * **TB** (*typing bursts*) — number of bursts.
    * **TG** (*total gap*) — cumulative inter-burst pause time in ms.
    * **TD** (*typing duration*) — cumulative active typing time in ms
      (total segment time minus inter-burst pauses).

    Parameters
    ----------
    sg_df : pandas.DataFrame
        SG-table DataFrame as returned by
        ``read_TPRDB_tables(..., extension="sg")``.  May span multiple
        study sessions.
    kd_df : pandas.DataFrame
        KD-table DataFrame as returned by
        ``read_TPRDB_tables(..., extension="kd")``, covering the same
        sessions as *sg_df*.  Rows must be in chronological keystroke order
        within each session (as stored in TPR-DB tables).
    threshold : int
        Pause threshold in milliseconds.  Must not be ``1000``; metrics at
        that threshold are already present in SG tables as ``TB1000``,
        ``TG1000``, and ``TD1000``.

    Returns
    -------
    pandas.DataFrame
        A copy of *sg_df* with three new columns:

        ==================  =================================================
        ``TB{threshold}``   Number of typing bursts per segment.
        ``TG{threshold}``   Total inter-burst pause time (ms) per segment.
        ``TD{threshold}``   Total active typing duration (ms) per segment.
        ==================  =================================================

        For example, ``threshold=500`` adds columns ``TB500``, ``TG500``,
        ``TD500``.

        If any of these columns already exist in *sg_df* (e.g. from a
        previous call with the same threshold), they are silently replaced.

    Raises
    ------
    ValueError
        If *threshold* equals ``1000``.  Use the pre-existing ``TB1000``,
        ``TG1000``, and ``TD1000`` columns in the SG table directly.

    Notes
    -----
    Computation is performed independently for each unique ``StudySession``
    in *sg_df*, then the per-session results are merged back.  Sessions
    present in *sg_df* but absent from *kd_df* (or with no matching
    keystrokes) receive zero values for all three new metrics.

    The ``TTseg`` column is coerced to ``str`` internally; the caller does
    not need to pre-cast either DataFrame.

    Examples
    --------
    >>> from tprdb_utilities import read_TPRDB_tables, recompute_pause_based_metrics
    >>> path = "/path/to/tprdb-mothership-clone"
    >>> sg = read_TPRDB_tables(["BML12"], "sg", path)
    >>> kd = read_TPRDB_tables(["BML12"], "kd", path)
    >>> sg_500 = recompute_pause_based_metrics(sg, kd, threshold=500)
    >>> sg_500[["StudySession", "TTseg", "TB500", "TG500", "TD500"]].head()
    """
    if threshold == 1000:
        raise ValueError(
            "threshold=1000 is not allowed: TB1000, TG1000, and TD1000 are "
            "already pre-computed in every SG table. Use those columns directly."
        )

    new_cols = [f"TB{threshold}", f"TG{threshold}", f"TD{threshold}"]

    # Drop any existing columns for this threshold so repeated calls are
    # idempotent and do not produce duplicate/suffixed column names.
    sg_work = sg_df.drop(
        columns=[c for c in new_cols if c in sg_df.columns]
    ).copy()
    sg_work["TTseg"] = sg_work["TTseg"].astype(str)

    session_results: list[pd.DataFrame] = []
    for session in sg_work["StudySession"].unique():
        sg_session = sg_work[sg_work["StudySession"] == session]
        kd_session = kd_df[kd_df["StudySession"] == session].copy()
        kd_session["TTseg"] = kd_session["TTseg"].astype(str)

        session_metrics = _compute_burst_metrics_for_session(
            sg_session, kd_session, threshold
        )
        session_metrics["StudySession"] = session
        session_results.append(session_metrics)

    if not session_results:
        for col in new_cols:
            sg_work[col] = pd.NA
        return sg_work

    all_metrics = pd.concat(session_results, ignore_index=True)
    return sg_work.merge(all_metrics, on=["StudySession", "TTseg"], how="left")
