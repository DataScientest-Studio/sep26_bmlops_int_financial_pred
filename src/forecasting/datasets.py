"""Version records of the datasets training uses, kept with DVC."""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from forecasting.config import Settings


def dataset_version(settings: Settings, symbol: str, rows: pd.DataFrame) -> str:
    """Record the rows a training run uses and return their version id.

    The rows are written as given, without row numbers, to `<symbol>.csv` in the
    dataset folder and recorded with DVC, which keeps a copy of each distinct
    content in its cache under the id. The same rows always get the same id.

    @relation(REQ-DAT-006, scope=function)
    @relation(REQ-CON-003, scope=function)

    Args:
        settings: Settings of this deployment; `dataset_dir` is the folder.
        symbol: Ticker of the security, for example "AAPL.US".
        rows: The rows training uses.

    Returns:
        DVC's fingerprint of the rows (MD5 of the written file).

    Raises:
        RuntimeError: If DVC fails; the message carries DVC's error output.
    """
    folder = settings.dataset_dir
    if not (folder / ".dvc").exists():
        _run_dvc(folder, "init", "--no-scm")
    path = folder / f"{symbol}.csv"
    rows.to_csv(path, index=False)
    _run_dvc(folder, "add", path.name)
    record = yaml.safe_load(Path(f"{path}.dvc").read_text())

    return record["outs"][0]["md5"]


def _run_dvc(folder: Path, *arguments: str) -> None:
    """Run one DVC command in the dataset folder.

    Raises:
        RuntimeError: If DVC exits with an error; the message carries DVC's error
            output.
    """
    command = [sys.executable, "-m", "dvc", *arguments]
    # DVC sends a usage report to its makers after every command unless this variable
    # is set; DVC then stays offline.
    environment = {**os.environ, "DVC_NO_ANALYTICS": "1"}
    run = subprocess.run(
        command, cwd=folder, env=environment, capture_output=True, text=True
    )
    if run.returncode != 0:
        raise RuntimeError(f"dvc {arguments[0]} failed: {run.stderr.strip()}")
