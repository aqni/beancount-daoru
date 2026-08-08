import shutil
import sys
import warnings
from collections.abc import Generator
from pathlib import Path

import git
import pytest
from typing_extensions import override
from xprocess import ProcessStarter, XProcess

from tests.examples.conftest import (
    EXAMPLES_DIR,
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


def start_llama_server(  # noqa: PLR0913
    *,
    xprocess: XProcess,
    model_hf: str,
    model_alias: str,
    port: int,
    ctx_size: int,
    is_embedding: bool = False,
) -> Generator[None]:
    hf_model_repo_id, model_suffix = model_hf.split(":")

    class Starter(ProcessStarter):
        @property
        @override
        def args(self) -> list[str]:  # pyright: ignore[reportIncompatibleMethodOverride]
            return [
                sys.executable,
                "-m",
                "llama_cpp.server",
                f"--port={port}",
                f"--hf_model_repo_id={hf_model_repo_id}",
                f"--model=*{model_suffix}.gguf",
                f"--n_ctx={ctx_size}",
                f"--model_alias={model_alias}",
                f"--embedding={is_embedding}",
            ]

        @property
        @override
        def pattern(self) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
            """The pattern to match when the process has started."""
            return "Application startup complete"

        max_read_lines: int = sys.maxsize

    server_name = f"llama-cpp-python-{port}-{model_alias}"
    _ = xprocess.ensure(server_name, Starter, persist_logs=False)  # pyright: ignore[reportUnknownVariableType]
    yield
    _ = xprocess.getinfo(server_name).terminate()


@pytest.fixture(scope="session")
def embedding_server(xprocess: XProcess) -> Generator[None]:
    yield from start_llama_server(
        xprocess=xprocess,
        model_hf="unsloth/embeddinggemma-300m-GGUF:Q4_0",
        model_alias="embeddinggemma-300m",
        port=1314,
        is_embedding=True,
        ctx_size=1024,
    )


@pytest.fixture(scope="session")
def chat_completion_server(xprocess: XProcess) -> Generator[None]:
    yield from start_llama_server(
        xprocess=xprocess,
        model_hf="unsloth/Qwen3-4B-Instruct-2507-GGUF:UD-Q4_K_XL",
        model_alias="Qwen3-4B-Instruct-2507",
        port=9527,
        ctx_size=8 * 1024,
    )


def __check_diff_with_tolerance(
    git_repo: git.Repo, file_path: Path, /, max_lines: int
) -> None:
    diff: str = git_repo.git.diff(file_path)  # pyright: ignore[reportAny]
    if diff:
        lines = diff.split("\n")
        changes = [
            line
            for line in lines
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        ]
        if len(changes) > max_lines:
            pytest.fail(diff)
        else:
            warnings.warn(diff, stacklevel=2)


@pytest.mark.usefixtures("embedding_server", "chat_completion_server")
def test_zero_shot(git_repo: git.Repo) -> None:
    ZERO_SHOT_PREDICTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    run_python_subprocess(
        PREDICT_SCRIPTS,
        "extract",
        DOWNLOADS_DIR,
        "-e",
        ACCOUNTS_FILE,
        "-o",
        ZERO_SHOT_PREDICTED_FILE,
        cwd=EXAMPLE_DIR,
    )

    __check_diff_with_tolerance(git_repo, ZERO_SHOT_PREDICTED_FILE, max_lines=4)


@pytest.mark.usefixtures("embedding_server", "chat_completion_server")
def test_few_shot(git_repo: git.Repo) -> None:
    FEW_SHOT_PREDICTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    run_python_subprocess(
        PREDICT_SCRIPTS,
        "extract",
        DOWNLOADS_DIR,
        "-e",
        EXISTING_FILE,
        "-o",
        FEW_SHOT_PREDICTED_FILE,
        cwd=EXAMPLE_DIR,
    )

    __check_diff_with_tolerance(git_repo, FEW_SHOT_PREDICTED_FILE, max_lines=0)
