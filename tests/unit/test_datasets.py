"""Unit tests of the dataset versions."""

from dataclasses import replace

from forecasting.datasets import dataset_version
from tests.fakes import SECURITIES, price_history


def test_dataset_version_keeps_a_copy_of_the_rows(example_settings, tmp_path):
    """The copy kept under a version id holds the rows it was made from."""
    settings = replace(example_settings, dataset_dir=tmp_path)
    security = SECURITIES[0]
    rows = price_history(security.exchange, "2025-01-02", "2025-03-31", seed=1)
    version = dataset_version(settings, security.symbol, rows)
    dataset_version(settings, security.symbol, rows.iloc[:-1])
    # DVC files each copy under the first two characters of its id, then the rest.
    folder, name = version[:2], version[2:]
    copy = settings.dataset_dir / ".dvc" / "cache" / "files" / "md5" / folder / name
    assert copy.read_text() == rows.to_csv(index=False)
