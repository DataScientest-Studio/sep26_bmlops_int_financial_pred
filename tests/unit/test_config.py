"""Unit tests of reading the settings."""

import pytest

from forecasting.config import Security, load_settings

INDEX_ENTRY = "[[indices]]\nsymbol = 'TEST.INDX'\nexchange = 'XNYS'\n"


def _use_securities_file(monkeypatch, tmp_path, content: str) -> None:
    """Write a securities file into an empty folder and have the settings read it."""
    securities_file = tmp_path / "securities.toml"
    securities_file.write_text(content)
    monkeypatch.setattr("forecasting.config.SECURITIES_FILE", securities_file)


def test_settings_list_the_configured_indices(monkeypatch, tmp_path):
    """The settings name each market index of the securities file."""
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
    ],
)
def test_securities_file_refuses_a_value_that_is_no_text(
    monkeypatch, tmp_path, symbol, exchange
):
    """A symbol or exchange that is no text or empty is refused."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        f"[[securities]]\nsymbol = {symbol}\nexchange = {exchange}\n\n" + INDEX_ENTRY,
    )
    with pytest.raises(ValueError, match="must be a non-empty text"):
        load_settings()


def test_history_start_before_the_calendar_is_refused(monkeypatch, tmp_path):
    """A first day of history before the calendar's first day is refused."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n" + INDEX_ENTRY,
    )
    monkeypatch.setenv("HISTORY_START", "1979-12-31")
    with pytest.raises(ValueError, match="HISTORY_START"):
        load_settings()


def test_one_evaluation_day_is_accepted(monkeypatch, tmp_path):
    """An EVALUATION_DAYS of 1 is accepted."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n" + INDEX_ENTRY,
    )
    monkeypatch.setenv("EVALUATION_DAYS", "1")
    assert load_settings().evaluation_days == 1


def test_no_evaluation_days_is_refused(monkeypatch, tmp_path):
    """An EVALUATION_DAYS below 1 is refused."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n" + INDEX_ENTRY,
    )
    monkeypatch.setenv("EVALUATION_DAYS", "0")
    with pytest.raises(ValueError):
        load_settings()


def test_code_version_defaults_to_unknown(monkeypatch):
    """Without CODE_VERSION in the environment, the code version is unknown."""
    monkeypatch.delenv("CODE_VERSION", raising=False)
    assert load_settings().code_version == "unknown"


def test_code_version_reads_the_environment(monkeypatch):
    """When CODE_VERSION is set, the settings report that commit."""
    monkeypatch.setenv("CODE_VERSION", "b64fa1e")
    assert load_settings().code_version == "b64fa1e"
