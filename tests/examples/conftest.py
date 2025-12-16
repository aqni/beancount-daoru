import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import git
import pytest

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.fixture(scope="session")
def git_repo() -> Generator[git.Repo]:
    repo = git.Repo(EXAMPLES_DIR, search_parent_directories=True)
    with repo.config_writer() as config:
        config.set_value("core", "quotepath", "false")
        yield repo


def run_python_subprocess(
    *args: str | Path,
    cwd: Path,
) -> subprocess.CompletedProcess:
    cmd = [sys.executable]
    for arg in args:
        if isinstance(arg, Path):
            cmd.append(str(arg.relative_to(cwd)))
        else:
            cmd.append(arg)

    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            env=os.environ.copy() | {"PYTHONUTF8": "1"},
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"{e}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")
