"""Hook for reordering entries by importer name.

This module provides a hook implementation that sorts imported entries
by their importer's name in ascending order.
"""

from beancount import Directives
from typing_extensions import override

from beancount_daoru.hook import Hook as BaseHook
from beancount_daoru.hook import Imported


class Hook(BaseHook):
    """Hook that reorders entries by importer name.

    This hook sorts the imported entries based on the importer's name,
    allowing for consistent ordering of entries from different importers.
    """

    @override
    def __call__(
        self, imported: list[Imported], existing: Directives
    ) -> list[Imported]:
        return sorted(imported, key=lambda x: x[3].name)
