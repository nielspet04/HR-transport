from pathlib import Path


def test_backend_package_is_importable() -> None:
    import app

    assert app.__doc__


def test_hr_data_directories_are_gitignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "data/input/*" in gitignore
    assert "data/output/*" in gitignore
    assert "*.xlsx" in gitignore
    assert "data/**/*.json" in gitignore
