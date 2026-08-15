
import git
import pytest

from tests.examples.conftest import (
    EXAMPLES_DIR,
    assert_no_diff,
    run_python_subprocess,
)

EXAMPLE_DIR = EXAMPLES_DIR / "predict"
DOWNLOADS_DIR = EXAMPLE_DIR / "downloads"
LEDGER_DIR = EXAMPLE_DIR / "ledger"
PREDICT_SCRIPTS = EXAMPLE_DIR / "import.py"
ACCOUNTS_FILE = LEDGER_DIR / "accounts.beancount"
EXISTING_FILE = LEDGER_DIR / "existing.beancount"
ZERO_SHOT_PREDICTED_FILE = LEDGER_DIR / "zero_shot_predicted.beancount"
FEW_SHOT_PREDICTED_FILE = LEDGER_DIR / "few_shot_predicted.beancount"
VCR_PATH_ENV = "VCR_PATH"
ZERO_SHOT_VCR_FILE = EXAMPLE_DIR / ".cassettes" / "zero_shot.yml"
FEW_SHOT_VCR_FILE = EXAMPLE_DIR / ".cassettes" / "few_shot.yml"
PREDICT_CACHE_DIR_ENV = "PREDICT_CACHE_DIR"



def test_zero_shot(git_repo: git.Repo, tmp_path_factory: pytest.TempPathFactory) -> None:
    run_python_subprocess(
        PREDICT_SCRIPTS,
        "extract",
        DOWNLOADS_DIR,
        "-e",
        ACCOUNTS_FILE,
        "-o",
        ZERO_SHOT_PREDICTED_FILE,
        cwd=EXAMPLE_DIR,
        env={
            VCR_PATH_ENV: str(ZERO_SHOT_VCR_FILE),
            PREDICT_CACHE_DIR_ENV: str(tmp_path_factory.mktemp("zero_shot_cache")),
        },
    )
    assert_no_diff(git_repo, ZERO_SHOT_PREDICTED_FILE)
    assert_no_diff(git_repo, ZERO_SHOT_VCR_FILE)


def test_few_shot(git_repo: git.Repo, tmp_path_factory: pytest.TempPathFactory) -> None:
    run_python_subprocess(
        PREDICT_SCRIPTS,
        "extract",
        DOWNLOADS_DIR,
        "-e",
        EXISTING_FILE,
        "-o",
        FEW_SHOT_PREDICTED_FILE,
        cwd=EXAMPLE_DIR,
        env={
            VCR_PATH_ENV: str(FEW_SHOT_VCR_FILE),
            PREDICT_CACHE_DIR_ENV: str(tmp_path_factory.mktemp("few_shot_cache")),
        },
    )
    assert_no_diff(git_repo, FEW_SHOT_PREDICTED_FILE)
    assert_no_diff(git_repo, FEW_SHOT_VCR_FILE)
