"""Base module for reading financial documents.

This module defines the base Reader class that provides a common interface
for reading various document formats (PDF, Excel, etc.) and converting them
into structured data that can be processed by extractors.
"""

from abc import abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol


class Reader(Protocol):
    """Abstract base class for document readers.

    Readers are responsible for parsing raw document files (PDF, Excel, etc.)
    into structured dictionaries that can be validated and converted to typed records.
    """

    @abstractmethod
    def identify(self, file: Path) -> bool:
        """Check if the reader can handle the given file.

        Args:
            file: Path to the file to check.

        Returns:
            True if the reader can handle the file, False otherwise.
        """
        ...

    @abstractmethod
    def read_captions(
        self,
        file: Path,
    ) -> Iterator[str]:
        """Read caption/header text from the file.

        Args:
            file: Path to the file to read.

        Yields:
            Strings of caption text.
        """
        ...

    @abstractmethod
    def read_records(self, file: Path) -> Iterator[dict[str, str]]:
        """Read records as dictionaries from the file.

        Args:
            file: Path to the file to read.

        Yields:
            Dictionaries representing individual records.
        """
        ...
