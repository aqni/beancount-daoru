"""PDF table reader implementation.

This module provides functionality to read tabular data from PDF files using pdfplumber,
handling the layout and text extraction complexities of Chinese financial documents.
"""

from collections.abc import Iterator
from pathlib import Path

import pdfplumber
from typing_extensions import override

from beancount_daoru.reader import Reader as BaseReader

BBox = tuple[int | float, int | float, int | float, int | float]


class Reader(BaseReader):
    """Reader for PDF files containing tabular data.

    Uses pdfplumber to extract tables from PDF documents, focusing on specific
    bounding boxes to isolate transaction tables from other content.
    """

    def __init__(
        self,
        /,
        table_bbox: BBox,
    ) -> None:
        """Initialize the PDF table reader.

        Args:
            table_bbox: Bounding box (x0, y0, x1, y1) defining the table area.
        """
        self.__table_bbox = table_bbox

    @override
    def read_captions(self, file: Path) -> Iterator[str]:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                yield page.outside_bbox(self.__table_bbox).extract_text_simple()

    @override
    def read_records(self, file: Path) -> Iterator[dict[str, str]]:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                table = page.within_bbox(self.__table_bbox).extract_table()
                if table:
                    header = [value or "" for value in table[0]]
                    for row in table[1:]:
                        yield {
                            field: (value or "").strip()
                            for field, value in zip(header, row, strict=True)
                        }
