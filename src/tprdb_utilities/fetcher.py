import glob
import io
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests


def _get_study_summary_timestamp(study_dir):
    """Return the ``last_generated_datatables`` value from the StudySummary XML
    in *study_dir*, or ``None`` if the file is absent or unparseable."""
    for xml_path in glob.glob(os.path.join(study_dir, "*.xml")):
        try:
            root = ET.parse(xml_path).getroot()
            element = (
                root
                if root.tag == "StudySummary"
                else root.find(".//StudySummary")
            )
            if element is not None:
                ts = element.get("last_generated_datatables")
                if ts:
                    return ts
        except ET.ParseError:
            continue
    return None


def fetch_TPRDB_tables(
    path, studies, extensions, public, username=None, token=None, verbose=0
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
            ├── PUBLIC/                 ← public studies
            │   └── <StudyID>/
            │       ├── studySummary.xml
            │       └── Tables/
            │           ├── session1.<ext>
            │           └── ...
            └── <username>/             ← private studies (when public=False)
                └── <StudyID>/
                    ├── studySummary.xml
                    └── Tables/
                        ├── session1.<ext>
                        └── ...

    Parameters
    ----------
    path : str
        Root directory in which the ``tprdb-mothership-clone`` folder will
        be created (or appended to if it already exists).  The path is
        expanded and resolved before use, so ``"~"``/``"~/..."`` (home
        directory), ``"."``/``"./..."`` and ``".."``/``"../..."`` (relative
        to the current working directory), and absolute paths all work the
        same way on Linux, macOS, and Windows — including inside Jupyter
        notebooks, where no shell expansion takes place.  On Windows, write
        backslash paths as raw strings (``r"C:\\Users\\me\\data"``) or use
        forward slashes (``"C:/Users/me/data"``).  After downloading, pass
        the ``path`` value printed in the summary as the ``path`` argument
        to ``read_TPRDB_tables``.
    studies : list of str
        List of study identifiers to download, e.g. ``["DG21", "SG12"]``.  Must match
        studies registered in the TPR-DB exactly (case-sensitive).
    extensions : list of str
        One or more table-type extensions to download, e.g.
        ``["kd", "ss", "st"]``.  Valid values include ``"ag"``, ``"au"``, ``"ex"``, ``"fd"``,
        ``"fu"``, ``"hc"``, ``"hs"``, ``"kd"``, ``"ku"``, ``"pu"``, ``"sg"``, ``"ss"``,
        ``"st"``, and ``"tt"``.  One API request is made per extension;
        extensions already present locally are re-checked against the server
        using a conditional request (see Notes).
    public : bool
        Whether the requested study is publicly accessible.

        ``True``
            No credentials required.  Files are saved under
            ``tprdb-mothership-clone/PUBLIC/<StudyID>/Tables/``.

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
    directory, the request is still made but includes the
    ``X-Client-Tables-Timestamp`` header populated from the
    ``last_generated_datatables`` attribute of the ``StudySummary`` XML stored
    in the ``<StudyID>/`` directory (one level above ``Tables/``).  When the
    server returns ``304 Not Modified`` the local files are already up to date
    and no extraction is performed.  A ``200`` response replaces the existing
    files with fresh archive contents.

    The ``StudySummary`` XML bundled in every zip response is always written
    to ``<StudyID>/`` rather than ``Tables/``; all other files go into
    ``Tables/`` as usual.

    Examples
    --------
    **Downloading a public study:**

    >>> from tprdb_utilities import fetch_TPRDB_tables
    >>> fetch_TPRDB_tables(
    ...     path="/path/to/local/data",
    ...     studies=["DG21"],
    ...     extensions=["kd", "ss"],
    ...     public=True,
    ... )

    **Downloading a private study:**

    >>> from tprdb_utilities import fetch_TPRDB_tables
    >>> fetch_TPRDB_tables(
    ...     path="/path/to/local/data",
    ...     studies=["MYSTUDY"],
    ...     extensions=["kd"],
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
    


    folder_name = "PUBLIC" if public else str(username)
    clone_root = str((Path(path).expanduser() / "tprdb-mothership-clone").resolve())

    # Strip any leading dots so extensions are consistently bare (e.g. "kd" not ".kd")
    # Computed once — same for every study
    clean_extensions = [ext.lstrip(".") for ext in extensions]

    all_results: dict[str, list[tuple[str, str, str]]] = {}  # StudyID -> [(ext, status, elapsed)]

    for StudyID in studies:
        target_dir = os.path.join(clone_root, folder_name, StudyID, "Tables")
        os.makedirs(target_dir, exist_ok=True)
        study_dir = os.path.dirname(target_dir)
        results = []

        for ext in clean_extensions:
            existing = glob.glob(os.path.join(target_dir, f"*{ext}"))

            url = (
                "https://critt.as.kent.edu/tpr/api/tables/"
                f"?studyID={StudyID}&extension={ext}&public={str(public).lower()}"
            )
            headers = {"Authorization": f"Bearer {token}"} if not public else {}

            if existing:
                timestamp = _get_study_summary_timestamp(study_dir)
                if timestamp:
                    headers["X-Client-Tables-Timestamp"] = timestamp

            t0 = time.perf_counter()
            # ↓ show status before the blocking request
            print(f"\r  {StudyID} [{ext}]: Fetching...", end="", flush=True)

            # ---- ye request (the most important part) ----
            response = requests.get(url, headers=headers)

            # clear the status line so summary prints cleanly
            print(f"\r  {StudyID} [{ext}]: Done fetching (^_^)", flush=True)

            if response.status_code == 304:
                results.append((ext, "Up to date (304)", f"{time.perf_counter() - t0:.2f}s"))
                continue

            if not response.ok:
                print() # move to new line before raising
                raise requests.HTTPError(
                    f"HTTP {response.status_code} for extension '{ext}': {response.text}"
                )

            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                members = zf.namelist()
                for name in members:
                    dest = study_dir if name.lower().endswith(".xml") else target_dir
                    zf.extract(name, dest)

            elapsed = f"{time.perf_counter() - t0:.2f}s"
            results.append((ext, "Updated" if existing else "Downloaded", elapsed))

        all_results[StudyID] = results

    # --- Always-printed summary ---
    print("\n=== fetch_TPRDB_tables Summary ===")
    print(f"Clone dir: {clone_root}")
    print(f"User dir : {folder_name}")
    print()

    for StudyID, results in all_results.items():
        col_w = max(max((len(r[0]) for r in results), default=0), len("Extension"))
        status_w = max(max((len(r[1]) for r in results), default=0), len("Status"))

        print(f"StudyID: {StudyID}")
        print(f"{'Extension':<{col_w}}  {'Status':<{status_w}}  Time")
        print(f"{'-' * col_w}  {'-' * status_w}  ------")
        for ext, status, elapsed in results:
            print(f"{ext:<{col_w}}  {status:<{status_w}}  {elapsed}")
        print()

    print("To read these files into a DataFrame with read_TPRDB_tables:")
    print(f'  path      = "{clone_root}"')
    print(f'  user      = "{folder_name}"')
    print(f'  studies   = {list(all_results.keys())}')