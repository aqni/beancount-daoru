"""Hook for converting file paths to relative paths.

This module provides a hook implementation that converts absolute file paths
to relative paths based on a specified base directory.
"""

from pathlib import Path

from beancount import Directives
from typing_extensions import override

from beancount_daoru import hook


class Hook(hook.Hook):
    """Hook that converts absolute file paths to relative paths.

    This hook transforms the file paths in imported entries to be relative
    to a specified base directory, which can be useful for portability.
    """

    def __init__(self, path: Path, /) -> None:
        """Initialize the path conversion hook.

        Args:
            path: Base path to calculate relative paths from.
        """
        self.base_path = Path(path)

    @override
    def __call__(
        self, imported: list[hook.Imported], existing: Directives
    ) -> list[hook.Imported]:
        return [self._transform(imported) for imported in imported]

    def _transform(self, imported: hook.Imported) -> hook.Imported:
        filename, directives, account, importer = imported
        relative_filename = Path(filename).relative_to(self.base_path)
        return str(relative_filename), directives, account, importer
