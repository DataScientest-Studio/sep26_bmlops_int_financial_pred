"""Unit tests of reading the settings."""

import pytest

from forecasting.config import Security, load_settings

INDEX_ENTRY = "[[indices]]\nsymbol = 'TEST.INDX'\nexchange = 'XNYS'\n"


def _use_securities_file(monkeypatch, tmp_path, content: str) -> None:
    """Write a securities file into an empty folder and work from there."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "securities.toml").write_text(content)
    monkeypatch.chdir(tmp_path)


def test_settings_list_the_configured_indices(monkeypatch, tmp_path):
    """REQ-DAT-001: the settings name each market index of the securities file."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n" + INDEX_ENTRY,
    )
    settings = load_settings()
    assert settings.indices == (Security("TEST.INDX", "XNYS"),)
    assert settings.securities == (Security("TEST.US", "XNYS"),)


@pytest.mark.parametrize(
    ("symbol", "exchange"),
    [
        ("123", "'XNYS'"),  # a number
        ("''", "'XNYS'"),  # empty
        ("'TEST.US'", "2026-01-02"),  # a date
    ],
)
def test_securities_file_refuses_a_value_that_is_no_text(
    monkeypatch, tmp_path, symbol, exchange
):
    """REQ-DAT-001: a symbol or exchange that is no text or empty is refused."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        f"[[securities]]\nsymbol = {symbol}\nexchange = {exchange}\n\n" + INDEX_ENTRY,
    )
    with pytest.raises(ValueError):
        load_settings()
