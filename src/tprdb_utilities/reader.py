import os
import glob

import pandas as pd


def read_TPRDB_tables(studies, extension, mothership, path=None, user="TPRDB", verbose=0):
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
        File extension identifying the table type, e.g. ``"kd"``, ``"ss"``,
        ``"sg"``, ``"st"``, ``"tt"``, ``"fd"``, ``"au"``, ``"pu"``,
        ``"hof"``, or ``"pol"``.  A leading dot is not required.
    mothership : bool
        **Required.**  Controls how the root path is resolved.

        ``True``
            You are running this function directly on the **CRITT TPR-DB
            server** (the "mothership").  The path is automatically set to
            ``/data/critt/tprdb/`` and the ``path`` argument is ignored.
            The ``user`` argument still applies (default ``"TPRDB"`` for
            the public corpus).

        ``False``
            You are working from a **local clone** of the TPR-DB structure,
            either assembled manually or downloaded via
            ``fetch_TPRDB_tables``.  You *must* supply the ``path``
            argument pointing to the root of that clone (i.e. the
            ``tprdb-mothership-clone`` directory created by
            ``fetch_TPRDB_tables``).

    path : str, optional
        Root directory of the local TPR-DB clone.  **Required when**
        ``mothership=False``; ignored when ``mothership=True``.
        This should be the ``tprdb-mothership-clone`` folder — i.e. the
        full path *including* the ``tprdb-mothership-clone`` segment — that
        was created by ``fetch_TPRDB_tables``.
    user : str, optional
        Name of the user sub-folder directly under ``path``.  Default is
        ``"TPRDB"``, which corresponds to the public corpus.  When working
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
        inferred automatically.  Returns an empty DataFrame if no matching
        files are found.

    Raises
    ------
    ValueError
        If ``mothership=False`` and ``path`` is not provided.

    Notes
    -----
    Files are expected to be tab-separated values (TSV).  Each file
    corresponds to one recording session.

    The ``extension`` argument is matched as a file-name suffix, so passing
    ``"kd"`` will match any file whose name ends with ``"kd"``
    (e.g. ``"P01_DG21_EN-DE.kd"``).

    Examples
    --------
    **Use case 1 — Running on the CRITT TPR-DB server (mothership=True):**

    Users with direct access to the CRITT server do not need to specify a
    path; it is resolved automatically.

    >>> from tprdb_utilities import read_TPRDB_tables
    >>> df = read_TPRDB_tables(
    ...     studies=["DG21", "AR22"],
    ...     extension="kd",
    ...     mothership=True,
    ... )

    **Use case 2 — Reading from a local clone (mothership=False):**

    Data must have been previously downloaded with ``fetch_TPRDB_tables``
    (or arranged manually in the identical directory structure).  Use the
    ``path`` and ``user`` values printed by ``fetch_TPRDB_tables`` at the
    end of its summary output.

    >>> from tprdb_utilities import read_TPRDB_tables
    >>> df = read_TPRDB_tables(
    ...     studies=["DG21"],
    ...     extension="kd",
    ...     mothership=False,
    ...     path="/path/to/tprdb-mothership-clone",
    ...     user="TPRDB",
    ... )
    """
    if mothership:
        path = "/data/critt/tprdb/"
    elif path is None:
        raise ValueError(
            "path is required when mothership=False. "
            "Provide the full path to your local TPR-DB clone root — "
            "this is the 'tprdb-mothership-clone' directory created by "
            "fetch_TPRDB_tables. Example: "
            "path='/your/local/data/tprdb-mothership-clone'"
        )

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

    if verbose:
        print(f"Total '{extension}' data rows: {df.shape[0]}, columns: {df.shape[1]}")
    return df
