"""Hook system for post-processing imported Beancount entries.

This module defines the hook interface that allows post-processing of imported
entries, enabling features like account prediction, path normalization, and
other transformations before final output.
"""

from typing import Protocol

from beancount import Account, Directives
from beangulp import Importer

Filename = str
Imported = tuple[Filename, Directives, Account, Importer]


class Hook(Protocol):
    """Protocol defining the interface for import hooks.

    Hooks are called after initial import but before final output,
    allowing customization of the imported entries.
    """

    def __call__(
        self, imported: list[Imported], existing: Directives
    ) -> list[Imported]:
        """Process imported entries.

        Args:
            imported: List of imported entries.
            existing: Existing Beancount entries.

        Returns:
            Processed list of imported entries.
        """
        ...
