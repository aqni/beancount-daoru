import git

from tests.examples.conftest import (
    EXAMPLES_DIR,
    run_python_subprocess,
)

EXAMPLE_DIR = EXAMPLES_DIR / "classifier"
IMPORT_SCRIPT = EXAMPLE_DIR / "import.py"
IMPORTED_FILE = EXAMPLE_DIR / "imported.beancount"


def test_extract(git_repo: git.Repo) -> None:
    run_python_subprocess(
        IMPORT_SCRIPT,
        "extract",
        EXAMPLE_DIR,
        "-o",
        IMPORTED_FILE,
        cwd=EXAMPLE_DIR,
    )

    diff = git_repo.git.diff(IMPORTED_FILE)  # pyright: ignore[reportAny]
    assert not diff, f"diff found\n{diff}\n"
