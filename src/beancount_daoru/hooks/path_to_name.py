"""Hook for converting file paths to file names.

This module provides a hook implementation that converts file paths
to file names only, discarding directory information.
"""

from pathlib import Path

from beancount import Directives
from typing_extensions import override

from beancount_daoru import hook


class Hook(hook.Hook):
    """Hook that converts file paths to file names.

    This hook transforms the file paths in imported entries to only contain
    the file name part, removing any directory path information.
    """

    @override
    def __call__(
        self, imported: list[hook.Imported], existing: Directives
    ) -> list[hook.Imported]:
        return [
            (Path(filename).name, directives, account, importer)
            for filename, directives, account, importer in imported
        ]
