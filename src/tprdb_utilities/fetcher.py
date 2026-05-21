import glob
import io
import os
import time
import zipfile

import requests


def fetch_TPRDB_tables(
    path, StudyID, extension, public, username=None, token=None, verbose=0
):
    """
    Download TPR-DB data tables from the CRITT TPR-DB API and save them
    locally in a directory structure that mirrors the TPR-DB server layout.

    Makes one HTTP GET request per extension to the CRITT TPR-DB REST API,
    receives a ``.zip`` archive, and extracts its contents directly into the
    appropriate ``Tables/`` subdirectory.  The resulting file structure is
    identical to the layout expected by ``read_TPRDB_tables``, so the two
    functions are designed to be used in sequence.

    **File structure created**::

        <path>/
        └── tprdb-mothership-clone/
            ├── TPRDB/                  ← public studies
            │   └── <StudyID>/
            │       └── Tables/
            │           ├── session1.<ext>
            │           └── ...
            └── <username>/             ← private studies (when public=False)
                └── <StudyID>/
                    └── Tables/
                        ├── session1.<ext>
                        └── ...

    Parameters
    ----------
    path : str
        Root directory in which the ``tprdb-mothership-clone`` folder will
        be created (or appended to if it already exists).  After downloading,
        pass ``os.path.join(path, "tprdb-mothership-clone")`` as the ``path``
        argument to ``read_TPRDB_tables`` — or simply copy the value from
        the summary printed by this function.
    StudyID : str
        Identifier of the study to download, e.g. ``"DG21"``.  Must match a
        study registered in the TPR-DB exactly (case-sensitive).
    extension : list of str
        One or more table-type extensions to download, e.g.
        ``["kd", "ss", "st"]``.  Valid values include ``"ss"``, ``"sg"``,
        ``"st"``, ``"tt"``, ``"kd"``, ``"fd"``, ``"au"``, ``"pu"``,
        ``"hof"``, and ``"pol"``.  One API request is made per extension;
        extensions with files already present locally are skipped.
    public : bool
        Whether the requested study is publicly accessible.

        ``True``
            No credentials required.  Files are saved under
            ``tprdb-mothership-clone/TPRDB/<StudyID>/Tables/``.

        ``False``
            Requires ``username`` and ``token``.  Files are saved under
            ``tprdb-mothership-clone/<username>/<StudyID>/Tables/``.

    username : str, optional
        Your TPR-DB web application username.  **Required when**
        ``public=False``.  Must match your registered username exactly
        (case-sensitive).  Also determines the folder name used for private
        study data, so it must be consistent across calls.
    token : str, optional
        Your TPR-DB API key (Bearer token).  **Required when**
        ``public=False``.  Obtain this from your TPR-DB account settings.
    verbose : int, optional
        Verbosity level.  Default ``0``.

        ``1`` or higher
            Print the name of each file extracted from the zip archive for
            every downloaded extension.

    Returns
    -------
    None
        This function saves files to disk and always prints a summary to
        stdout.  It does not return data; use ``read_TPRDB_tables`` to load
        the downloaded files into a DataFrame.

    Raises
    ------
    ValueError
        If ``public=False`` and ``username`` or ``token`` is not provided.
    requests.HTTPError
        If the API returns a non-2xx HTTP status code.  The error message
        includes the status code and response body for diagnosis.

    Notes
    -----
    A summary is always printed after all extensions have been processed,
    regardless of the ``verbose`` setting.  The summary includes ready-to-use
    argument values for ``read_TPRDB_tables`` so they can be copied directly
    into your next call.

    If files matching a given extension already exist in the ``Tables/``
    directory, the API request for that extension is skipped entirely.

    Examples
    --------
    **Downloading a public study:**

    >>> from tprdb_utilities import fetch_TPRDB_tables
    >>> fetch_TPRDB_tables(
    ...     path="/path/to/local/data",
    ...     StudyID="DG21",
    ...     extension=["kd", "ss"],
    ...     public=True,
    ... )

    **Downloading a private study:**

    >>> from tprdb_utilities import fetch_TPRDB_tables
    >>> fetch_TPRDB_tables(
    ...     path="/path/to/local/data",
    ...     StudyID="MYSTUDY",
    ...     extension=["kd"],
    ...     public=False,
    ...     username="myTPRDBusername",
    ...     token="my-api-token",
    ... )
    """
    if not public and (username is None or token is None):
        raise ValueError(
            "username and token are required when public=False. "
            "Provide your TPR-DB web app username (case-sensitive) and API token."
        )

    folder_name = "TPRDB" if public else username
    clone_root = os.path.join(path, "tprdb-mothership-clone")
    target_dir = os.path.join(clone_root, folder_name, StudyID, "Tables")
    os.makedirs(target_dir, exist_ok=True)

    # Strip any leading dots so extensions are consistently bare (e.g. "kd" not ".kd")
    clean_extensions = [ext.lstrip(".") for ext in extension]

    results = []  # list of (ext, status_str, elapsed_str)

    for ext in clean_extensions:
        # Skip if files for this extension are already present
        existing = glob.glob(os.path.join(target_dir, f"*{ext}"))
        if existing:
            results.append((ext, "Skipped (already present)", "--"))
            continue

        url = (
            "https://critt.as.kent.edu/tpr/api/tables/"
            f"?studyID={StudyID}&extension={ext}&public={str(public).lower()}"
        )
        headers = {"Authorization": f"Bearer {token}"} if not public else {}

        t0 = time.perf_counter()
        response = requests.get(url, headers=headers)
        if not response.ok:
            raise requests.HTTPError(
                f"HTTP {response.status_code} for extension '{ext}': {response.text}"
            )

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            members = zf.namelist()
            for name in members:
                zf.extract(name, target_dir)
            if verbose:
                for name in members:
                    print(f"  Extracted: {name}")

        elapsed = f"{time.perf_counter() - t0:.2f}s"
        results.append((ext, "Downloaded", elapsed))

    # --- Always-printed summary ---
    col_w = max(max((len(r[0]) for r in results), default=0), len("Extension"))
    status_w = max(max((len(r[1]) for r in results), default=0), len("Status"))

    print("=== fetch_TPRDB_tables Summary ===")
    print(f"StudyID  : {StudyID}")
    print(f"Clone dir: {clone_root}")
    print(f"User dir : {folder_name}")
    print()
    print(f"{'Extension':<{col_w}}  {'Status':<{status_w}}  Time")
    print(f"{'-' * col_w}  {'-' * status_w}  ------")
    for ext, status, elapsed in results:
        print(f"{ext:<{col_w}}  {status:<{status_w}}  {elapsed}")
    print()
    print("To read these files with read_TPRDB_tables:")
    print(f'  path      = "{clone_root}"')
    print(f'  user      = "{folder_name}"')
    print(f'  studies   = ["{StudyID}"]')
