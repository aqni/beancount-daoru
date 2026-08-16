import git

from tests.examples.conftest import (
    EXAMPLES_DIR,
    assert_no_diff,
    run_python_subprocess,
)

EXAMPLE_DIR = EXAMPLES_DIR / "import_only"
DOWNLOADS_DIR = EXAMPLE_DIR / "downloads"
DOCUMENTS_DIR = EXAMPLE_DIR / "documents"
IMPORTERS_DIR = EXAMPLE_DIR / "importers"
LEDGER_DIR = EXAMPLE_DIR / "ledger"
IMPORT_SCRIPT = EXAMPLE_DIR / "import.py"
IMPORTED_FILE = LEDGER_DIR / "imported.beancount"


def test_identify() -> None:
    result = run_python_subprocess(
        IMPORT_SCRIPT,
        "identify",
        DOWNLOADS_DIR,
        cwd=EXAMPLE_DIR,
        capture_output=True,
    )
    assert not result.stderr
    for line in result.stdout.decode("utf-8").splitlines():
        if line.startswith("* "):
            assert line.endswith(" ... OK")


def test_extract(git_repo: git.Repo) -> None:
    _ = run_python_subprocess(
        IMPORT_SCRIPT,
        "extract",
        DOWNLOADS_DIR,
        "-o",
        IMPORTED_FILE,
        cwd=EXAMPLE_DIR,
    )
    assert_no_diff(git_repo, IMPORTED_FILE)


def test_archive(git_repo: git.Repo) -> None:
    try:
        _ = run_python_subprocess(
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
