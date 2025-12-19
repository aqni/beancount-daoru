"""Excel document reader implementation.

This module provides functionality to read Excel and CSV files using pyexcel,
handling various encodings and formats commonly used by Chinese financial platforms.
"""

from collections.abc import Iterator
from pathlib import Path

import pyexcel
from typing_extensions import TypedDict, Unpack, override

from beancount_daoru.reader import Reader as BaseReader


class _ReaderKwargs(TypedDict, total=False):
    encoding: str


class Reader(BaseReader):
    """Reader for Excel and CSV files.

    Uses pyexcel to read various spreadsheet formats, handling encoding
    and format variations commonly found in Chinese financial documents.
    """

    def __init__(
        self,
        /,
        header: int,
        **kwargs: Unpack[_ReaderKwargs],
    ) -> None:
        """Initialize the Excel reader.

        Args:
            header: Number of header rows to skip before data.
            kwargs: Additional keyword arguments passed to pyexcel.
        """
        self.__header = header
        self.__kwargs = kwargs

    @override
    def read_captions(self, file: Path) -> Iterator[str]:
        for row in pyexcel.get_array(  # pyright: ignore[reportUnknownVariableType]
            file_name=file,
            row_limit=self.__header,
            auto_detect_int=False,
            auto_detect_float=False,
            auto_detect_datetime=False,
            skip_empty_rows=True,
            **self.__kwargs,
        ):
            yield from row

    @override
    def read_records(self, file: Path) -> Iterator[dict[str, str]]:
        for row in pyexcel.iget_records(  # pyright: ignore[reportUnknownVariableType]
            file_name=file,
            start_row=self.__header,
            auto_detect_int=False,
            auto_detect_float=False,
            auto_detect_datetime=False,
            skip_empty_rows=True,
            **self.__kwargs,
        ):
            yield {
                self.__convert(key): self.__convert(value)  # pyright: ignore[reportUnknownArgumentType]
                for key, value in row.items()  # pyright: ignore[reportUnknownVariableType]
            }

    def __convert(self, value: object) -> str:
        return "" if value is None else str(value).strip()
