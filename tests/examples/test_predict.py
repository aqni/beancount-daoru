import shutil
from collections.abc import Generator

import git
import httpx
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


def start_llama_server(
    *,
    xprocess: XProcess,
    model_hf: str,
    model_alias: str,
    port: int,
    is_embedding: bool = False,
) -> Generator[None]:
    exec_name = "llama-server"
    if shutil.which(exec_name) is None:
        pytest.skip(f"{exec_name!r} not in PATH")

    cmd_args = [
        exec_name,
        "-hf",
        model_hf,
        "--port",
        port,
        "--alias",
        model_alias,
        "--no-webui",
        "--seed",
        "42",
    ]
    if is_embedding:
        cmd_args.append("--embedding")

    class Starter(ProcessStarter):
        args = cmd_args  # pyright: ignore[reportIncompatibleMethodOverride, reportAssignmentType]
        timeout = 300  # aim to wait for downloading model weights

        @override
        def startup_check(self) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
            try:
                return httpx.get(f"http://localhost:{port}/health").is_success
            except (httpx.TimeoutException, httpx.ConnectError):
                return False

    server_name = f"{exec_name}-{port}-{model_alias}"
    xprocess.ensure(server_name, Starter, persist_logs=False)
    yield
    xprocess.getinfo(server_name).terminate()


@pytest.fixture(scope="session")
def embedding_server(xprocess: XProcess) -> Generator[None]:
    yield from start_llama_server(
        xprocess=xprocess,
        model_hf="unsloth/embeddinggemma-300m-GGUF:Q4_0",
        model_alias="embeddinggemma-300m",
        port=1314,
        is_embedding=True,
    )


@pytest.fixture(scope="session")
def chat_completion_server(xprocess: XProcess) -> Generator[None]:
    yield from start_llama_server(
        xprocess=xprocess,
        model_hf="unsloth/Qwen3-4B-Instruct-2507-GGUF:IQ4_NL",
        model_alias="Qwen3-4B-Instruct-2507",
        port=9527,
    )


@pytest.mark.usefixtures("embedding_server", "chat_completion_server")
def test_zero_shot(git_repo: git.Repo) -> None:
    ZERO_SHOT_PREDICTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = run_python_subprocess(
        PREDICT_SCRIPTS,
        "extract",
        DOWNLOADS_DIR,
        "-e",
        ACCOUNTS_FILE,
        "-o",
        ZERO_SHOT_PREDICTED_FILE,
        cwd=EXAMPLE_DIR,
    )

    assert "ERROR" not in result.stderr
    assert result.stdout == ""

    diff = git_repo.git.diff(ZERO_SHOT_PREDICTED_FILE)
    assert not diff, f"diff found\n{diff}\n"


@pytest.mark.usefixtures("embedding_server", "chat_completion_server")
def test_few_shot(git_repo: git.Repo) -> None:
    FEW_SHOT_PREDICTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = run_python_subprocess(
        PREDICT_SCRIPTS,
        "extract",
        DOWNLOADS_DIR,
        "-e",
        EXISTING_FILE,
        "-o",
        FEW_SHOT_PREDICTED_FILE,
        cwd=EXAMPLE_DIR,
    )

    assert "ERROR" not in result.stderr
    assert result.stdout == ""

    diff = git_repo.git.diff(FEW_SHOT_PREDICTED_FILE)
    assert not diff, f"diff found\n{diff}\n"
