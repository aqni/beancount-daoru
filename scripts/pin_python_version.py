import re
import tomllib
from pathlib import Path

PYPROJECT_FILE = Path("pyproject.toml")
PYTHON_VERSION_FILE = Path(".python-version")
MINIMUM_VERSION_PATTERN = re.compile(r"(?:>=|==)\s*([0-9]+(?:\.[0-9]+)*)")


def get_requires_python_spec(pyproject_path: Path) -> str | None:
    if not pyproject_path.exists():
        return None
    pyproject_data = tomllib.loads(pyproject_path.read_text("utf-8"))
    return pyproject_data.get("project", {}).get("requires-python")


def extract_minimum_version(version_spec: str) -> str | None:
    match = MINIMUM_VERSION_PATTERN.search(version_spec)
    return match.group(1) if match else None


def read_existing_version(version_file: Path) -> str | None:
    if not version_file.exists():
        return None
    return version_file.read_text("utf-8").strip()


def pin_python_version() -> None:
    requires_python_spec = get_requires_python_spec(PYPROJECT_FILE)
    if not requires_python_spec:
        return

    minimum_version = extract_minimum_version(requires_python_spec)
    if not minimum_version:
        return

    existing_version = read_existing_version(PYTHON_VERSION_FILE)
    if existing_version == minimum_version:
        return

    PYTHON_VERSION_FILE.write_text(f"{minimum_version}\n", encoding="utf-8")


if __name__ == "__main__":
    pin_python_version()
