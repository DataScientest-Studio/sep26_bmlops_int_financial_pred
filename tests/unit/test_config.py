"""Unit tests of reading the settings."""

import pytest

from forecasting.config import Security, load_settings

INDEX_ENTRY = "[[indices]]\nsymbol = 'TEST.INDX'\nexchange = 'XNYS'\n"
VALID_DAILY_UPDATE = {
    "weekdays": "[1, 2, 3, 4, 5]",
    "timezone": '"America/New_York"',
    "start_after": '"16:00"',
    "load_limit_minutes": "30",
    "final_delay_minutes": "25",
}


def _use_securities_file(monkeypatch, tmp_path, content: str) -> None:
    """Write a securities file into an empty folder and have the settings read it."""
    securities_file = tmp_path / "securities.toml"
    securities_file.write_text(content)
    monkeypatch.setattr("forecasting.config.SECURITIES_FILE", securities_file)


def _use_daily_update_file(monkeypatch, tmp_path, **changed) -> None:
    """Write a daily update file with some values changed and read it as settings."""
    values = VALID_DAILY_UPDATE | changed
    daily_update_file = tmp_path / "daily_update.toml"
    daily_update_file.write_text("".join(f"{k} = {v}\n" for k, v in values.items()))
    monkeypatch.setattr("forecasting.config.DAILY_UPDATE_FILE", daily_update_file)


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


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("final_delay_minutes", "24", "final_delay_minutes"),  # below the range
        ("final_delay_minutes", "61", "final_delay_minutes"),  # above the range
        ("final_delay_minutes", "25.5", "final_delay_minutes"),  # not an integer
        ("load_limit_minutes", "19", "load_limit_minutes"),  # below the range
        ("load_limit_minutes", "61", "load_limit_minutes"),  # above the range
        ("weekdays", "[0, 1, 2, 3, 4]", "weekdays"),  # Sunday written as 0
        ("weekdays", '"12345"', "weekdays"),  # text, not a list
        ("weekdays", "[]", "weekdays"),  # no day
        ("weekdays", "[1, 1, 2]", "weekdays"),  # a day twice
        ("start_after", '"23:40"', "start_after"),  # starts after midnight
    ],
)
def test_daily_update_file_refuses_a_value_outside_its_range(
    monkeypatch, tmp_path, key, value, expected
):
    """A value of the daily update file outside its range is refused."""
    _use_daily_update_file(monkeypatch, tmp_path, **{key: value})
    with pytest.raises(ValueError, match=expected):
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


def test_history_start_in_the_future_is_refused(monkeypatch, tmp_path):
    """A first day of history after today is refused."""
    _use_securities_file(
        monkeypatch,
        tmp_path,
        "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n" + INDEX_ENTRY,
    )
    monkeypatch.setenv("HISTORY_START", "9999-12-31")
    with pytest.raises(ValueError, match="HISTORY_START"):
        load_settings()


def test_code_version_defaults_to_unknown(monkeypatch):
    """Without CODE_VERSION in the environment, the code version is unknown."""
    monkeypatch.delenv("CODE_VERSION", raising=False)
    assert load_settings().code_version == "unknown"


def test_code_version_reads_the_environment(monkeypatch):
    """When CODE_VERSION is set, the settings report that commit."""
    monkeypatch.setenv("CODE_VERSION", "b64fa1e")
    assert load_settings().code_version == "b64fa1e"
