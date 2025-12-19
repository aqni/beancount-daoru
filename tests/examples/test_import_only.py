import git

from tests.examples.conftest import (
    EXAMPLES_DIR,
    run_python_subprocess,
)

EXAMPLE_DIR = EXAMPLES_DIR / "import_only"
DOWNLOADS_DIR = EXAMPLE_DIR / "downloads"
DOCUMENTS_DIR = EXAMPLE_DIR / "documents"
IMPORTERS_DIR = EXAMPLE_DIR / "importers"
LEDGER_DIR = EXAMPLE_DIR / "ledger"
IMPORT_SCRIPT = EXAMPLE_DIR / "import.py"
IMPORTED_FILE = LEDGER_DIR / "imported.beancount"


def test_extract(git_repo: git.Repo) -> None:
    IMPORTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    run_python_subprocess(
        IMPORT_SCRIPT,
        "extract",
        DOWNLOADS_DIR,
        "-o",
        IMPORTED_FILE,
        cwd=EXAMPLE_DIR,
    )

    diff = git_repo.git.diff(IMPORTED_FILE)  # pyright: ignore[reportAny]
    assert not diff, f"diff found\n{diff}\n"


def test_archive(git_repo: git.Repo) -> None:
    try:
        run_python_subprocess(
            IMPORT_SCRIPT,
            "archive",
            DOWNLOADS_DIR,
            "-o",
            DOCUMENTS_DIR,
            "--overwrite",
            cwd=EXAMPLE_DIR,
        )

        modification = git_repo.git.diff("--name-status", DOCUMENTS_DIR)  # pyright: ignore[reportAny]
        assert not modification, f"modification found\n{modification}\n"

        new_files = git_repo.git.ls_files("--others", DOCUMENTS_DIR)  # pyright: ignore[reportAny]
        assert not new_files, f"unexpected files found\n{new_files}\n"

    finally:
        git_repo.git.restore("--worktree", DOWNLOADS_DIR)  # pyright: ignore[reportAny]
