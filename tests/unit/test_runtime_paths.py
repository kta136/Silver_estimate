from silverestimate.infrastructure import paths


def test_database_path_uses_frozen_executable_directory(monkeypatch, tmp_path):
    executable = tmp_path / "SilverEstimate.exe"
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    assert paths.get_database_path() == tmp_path / "database" / "estimation.db"
