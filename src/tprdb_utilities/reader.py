import os
import glob
from pathlib import Path

import pandas as pd


def read_TPRDB_tables(studies, extension, path, user="PUBLIC", verbose=0):
    """
    Load TPR-DB data tables into a single concatenated DataFrame.

    Scans the expected TPR-DB directory layout for files matching the given
    extension across one or more studies and concatenates them into one
    ``pandas.DataFrame``.

    The directory layout expected (and created by ``fetch_TPRDB_tables``) is::

        <path>/
        └── <user>/
            └── <StudyID>/
                └── Tables/
                    ├── session1.<extension>
                    ├── session2.<extension>
                    └── ...

    Parameters
    ----------
    studies : list of str
        Study identifiers to load, e.g. ``["BML12", "SG12", "AR22"]``.
        Each must correspond to a subfolder under ``<path>/<user>/``.
    extension : str
        File extension identifying the table type, e.g.,
        ``"ag"``, ``"au"``, ``"ex"``, ``"fd"``, ``"fu"``, ``"hc"``,
        ``"hs"``, ``"kd"``, ``"ku"``, ``"pu"``, ``"sg"``, ``"ss"``,
        ``"st"``, or ``"tt"``.  A leading dot is not required.
    path : str
        Root directory of the TPR-DB clone.  This should be the
        ``tprdb-mothership-clone`` folder — i.e. the full path *including*
        the ``tprdb-mothership-clone`` segment — that was created by
        ``fetch_TPRDB_tables``.  Use the ``path`` value printed by
        ``fetch_TPRDB_tables`` at the end of its summary output.  The path
        is expanded and resolved before use, so ``"~"``/``"~/..."`` (home
        directory), ``"."``/``"./..."`` and ``".."``/``"../..."`` (relative
        to the current working directory), and absolute paths all work the
        same way on Linux, macOS, and Windows — including inside Jupyter
        notebooks, where no shell expansion takes place.  On Windows, write
        backslash paths as raw strings (``r"C:\\Users\\me\\data"``) or use
        forward slashes (``"C:/Users/me/data"``).
    user : str, optional
        Name of the user sub-folder directly under ``path``.  Default is
        ``"PUBLIC"``, which corresponds to the public corpus.  When working
        with private studies downloaded via ``fetch_TPRDB_tables``, set
        this to your TPR-DB username (the same value passed as ``username``
        to ``fetch_TPRDB_tables``).
    verbose : int, optional
        Verbosity level.  Default ``0`` (silent).

        ``1``
            Print the study name and the number of table files found for
            each study.

        ``2`` or higher
            Also print the full path of each file as it is read.

    Returns
    -------
    pandas.DataFrame
        Concatenated DataFrame containing all rows from all matching table
        files across every requested study.  Column names and dtypes are
        inferred automatically.

    Raises
    ------
    ValueError
        If the resulting DataFrame contains no data rows (i.e. no matching
        files were found or all matched files were empty).

    Notes
    -----
    Files are expected to be tab-separated values (TSV).  Each file
    corresponds to one recording session.

    The ``extension`` argument is matched as a file-name suffix, so passing
    ``"st"`` will match any file whose name ends with ``"st"``
    (e.g. ``"P01_T1.st"``).

    Examples
    --------
    **Public studies** (``user="PUBLIC"``):

    Data must have been previously downloaded with ``fetch_TPRDB_tables``
    (or arranged manually in the identical directory structure).  Use the
    ``path`` and ``user`` values printed by ``fetch_TPRDB_tables`` at the
    end of its summary output.

    >>> from tprdb_utilities import read_TPRDB_tables
    >>> df = read_TPRDB_tables(
    ...     studies=["DG21", "AR22"],
    ...     extension="st",
    ...     path="/path/to/tprdb-mothership-clone",
    ...     user="PUBLIC",
    ... )

    **Private studies** (``user="<your TPR-DB username>"``):

    For private studies, set ``user`` to the TPR-DB username that was passed
    as ``username`` to ``fetch_TPRDB_tables``.

    >>> from tprdb_utilities import read_TPRDB_tables
    >>> df = read_TPRDB_tables(
    ...     studies=["MYSTUDY"],
    ...     extension="st",
    ...     path="/path/to/tprdb-mothership-clone",
    ...     user="USER_DIRECTORY_NAME",
    ... )
    """
    path = str(Path(path).expanduser().resolve())

    df = pd.DataFrame()
    for study in studies:
        pattern = os.path.join(path, user, study, "Tables", f"*{extension}")
        files = glob.glob(pattern)
        if verbose:
            print(f"Reading: {study}\twith {len(files)} '{extension}' Tables")
        for fn in files:
            if verbose > 1:
                print(f"\t{fn}")
            df = pd.concat(
                [df, pd.read_csv(fn, sep="\t", dtype=None)],
                ignore_index=True,
            )

    if df.empty:
        raise ValueError(
            f"No data found for studies={studies!r}, extension={extension!r} "
            f"under path='{path}' / user='{user}'. "
            "Check that the path, user, study IDs, and extension are correct "
            "and that the data has been downloaded with fetch_TPRDB_tables."
        )

    if verbose:
        print(f"Total '{extension}' data rows: {df.shape[0]}, columns: {df.shape[1]}")
    return df
