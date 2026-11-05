"""Unit tests of reading the settings."""

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
