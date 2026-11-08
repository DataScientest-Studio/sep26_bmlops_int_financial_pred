"""Unit tests of reading the settings."""

from forecasting.config import Security, load_settings

INDEX_ENTRY = "[[indices]]\nsymbol = 'TEST.INDX'\nexchange = 'XNYS'\n"
SECURITY_ENTRY = "[[securities]]\nsymbol = 'TEST.US'\nexchange = 'XNYS'\n\n"


def _use_securities_file(monkeypatch, tmp_path, content: str) -> None:
    """Write a securities file into an empty folder and have the settings read it."""
    securities_file = tmp_path / "securities.toml"
    securities_file.write_text(content)
    monkeypatch.setattr("forecasting.config.SECURITIES_FILE", securities_file)


def test_settings_list_the_configured_indices(monkeypatch, tmp_path):
    """The settings name each market index of the securities file."""
    _use_securities_file(monkeypatch, tmp_path, SECURITY_ENTRY + INDEX_ENTRY)
    settings = load_settings()
    assert settings.indices == (Security("TEST.INDX", "XNYS"),)
    assert settings.securities == (Security("TEST.US", "XNYS"),)


def _start_without_code_version(monkeypatch, tmp_path) -> None:
    """Write a valid securities file and leave both code version variables unset."""
    _use_securities_file(monkeypatch, tmp_path, SECURITY_ENTRY + INDEX_ENTRY)
    monkeypatch.delenv("CODE_COMMIT", raising=False)
    monkeypatch.delenv("CODE_HAS_UNCOMMITTED_CHANGES", raising=False)


def test_settings_report_a_build_with_uncommitted_changes(monkeypatch, tmp_path):
    """REQ-MOD-004: settings name the commit of a build with uncommitted changes."""
    _start_without_code_version(monkeypatch, tmp_path)
    monkeypatch.setenv("CODE_COMMIT", "0123456789abcdef0123456789abcdef01234567")
    monkeypatch.setenv("CODE_HAS_UNCOMMITTED_CHANGES", "true")
    settings = load_settings()
    assert settings.code_commit == "0123456789abcdef0123456789abcdef01234567"
    assert settings.code_has_uncommitted_changes is True


def test_settings_report_a_build_without_uncommitted_changes(monkeypatch, tmp_path):
    """REQ-MOD-004: settings name the commit of a build without uncommitted changes."""
    _start_without_code_version(monkeypatch, tmp_path)
    monkeypatch.setenv("CODE_COMMIT", "0123456789abcdef0123456789abcdef01234567")
    monkeypatch.setenv("CODE_HAS_UNCOMMITTED_CHANGES", "false")
    settings = load_settings()
    assert settings.code_commit == "0123456789abcdef0123456789abcdef01234567"
    assert settings.code_has_uncommitted_changes is False


def test_settings_report_an_unknown_commit_by_default(monkeypatch, tmp_path):
    """REQ-MOD-004: an unset commit and unset uncommitted changes are unknown."""
    _start_without_code_version(monkeypatch, tmp_path)
    settings = load_settings()
    assert settings.code_commit == "unknown"
    assert settings.code_has_uncommitted_changes is None
