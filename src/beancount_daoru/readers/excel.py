"""Excel document reader implementation.

This module provides functionality to read Excel and CSV files using pyexcel,
handling various encodings and formats commonly used by Chinese financial platforms.
"""

from collections.abc import Iterator
from pathlib import Path

import pyexcel
from typing_extensions import override

from beancount_daoru import reader


class Reader(reader.Reader):
    """Reader for Excel and CSV files.

    Uses pyexcel to read various spreadsheet formats, handling encoding
    and format variations commonly found in Chinese financial documents.
    """

    def __init__(
        self,
        /,
        header: int,
        encoding: str | None = None,
    ) -> None:
        """Initialize the Excel reader.

        Args:
            header: Number of header rows to skip before data.
            encoding: Text encoding to use when reading the file.
        """
        self.header = header
        self.encoding = encoding

    @override
    def read_captions(self, file: Path) -> Iterator[str]:
        for row in pyexcel.get_array(
            file_name=file,
            encoding=self.encoding,
            row_limit=self.header,
            auto_detect_int=False,
            auto_detect_float=False,
            auto_detect_datetime=False,
        ):
            yield from row

    @override
    def read_records(self, file: Path) -> Iterator[dict[str, str]]:
        for row in pyexcel.iget_records(
            file_name=file,
            encoding=self.encoding,
            start_row=self.header,
            auto_detect_int=False,
            auto_detect_float=False,
            auto_detect_datetime=False,
            skip_empty_rows=True,
        ):
            yield {
                self.__convert(key): self.__convert(value) for key, value in row.items()
            }

    def __convert(self, value: object) -> str:
        return "" if value is None else str(value).strip()
