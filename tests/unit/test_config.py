"""Unit tests of reading the settings."""

from forecasting.config import Security, load_settings


def test_settings_list_the_configured_indices(monkeypatch, tmp_path):
    """REQ-DAT-001: the settings name each market index of the securities file."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "securities.toml").write_text(
        "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n"
        "[[indices]]\nsymbol = 'TEST.INDX'\nexchange = 'XNYS'\n"
    )
    monkeypatch.chdir(tmp_path)
    settings = load_settings()
    assert settings.indices == (Security("TEST.INDX", "XNYS"),)
    assert settings.securities == (Security("TEST.US", "XNYS"),)
