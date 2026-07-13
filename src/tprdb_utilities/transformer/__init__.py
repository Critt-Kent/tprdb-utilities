"""
Transformation utilities for TPR-DB DataFrames.

Functions
---------
prep_parallel_texts
    Build segment-aligned bitext and tritext DataFrames from TPR-DB segment,
    source-token, and target-token tables.
recompute_pause_based_metrics
    Recompute typing-burst metrics (TB, TG, TD) for a custom pause threshold
    and append them to an SG DataFrame.
"""

from .parallel_texts import prep_parallel_texts
from .pause_metrics import recompute_pause_based_metrics

__all__ = ["prep_parallel_texts", "recompute_pause_based_metrics"]
