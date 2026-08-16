"""Pinduoduo importer implementation.

This module provides an importer for Pinduoduo order export CSV files that converts
Pinduoduo transactions into Beancount entries.
"""

import re
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import TypeAdapter
from typing_extensions import TypedDict, Unpack, override

from beancount_daoru.importer import (
    Extra,
    ImporterKwargs,
    Metadata,
    Posting,
    Transaction,
)
from beancount_daoru.importer import Importer as BaseImporter
from beancount_daoru.importer import Parser as BaseParser
from beancount_daoru.readers import excel

Record = TypedDict(  # noqa: UP013
    "Record",
    {
        "订单金额": Decimal,
        "店铺": str,
        "商品": str,
        "订单状态": str,
        "支付方式": str,
        "下单时间": datetime,
    },
)

_FILE_NAME_PATTERN = re.compile(r"拼多多订单_(\d+)_\d{6}_(\d{6})\.csv")


class Parser(BaseParser):
    """Parser for Pinduoduo order records."""

    __validator = TypeAdapter(Record)

    @property
    @override
    def reversed(self) -> bool:
        return True

    @override
    def extract_metadata(self, filename: str, texts: Iterator[str]) -> Metadata:
        match = _FILE_NAME_PATTERN.fullmatch(filename)
        if match is None:
            msg = f"unsupported file name: {filename!r}"
            raise ValueError(msg)

        account, end_date = match.groups()
        return Metadata(
            account=account,
            date=date.fromisoformat(f"20{end_date}") - timedelta(days=1),
        )

    @override
    def parse(self, record: dict[str, str]) -> Transaction:
        validated = self.__validator.validate_python(record)
        return Transaction(
            date=validated["下单时间"].date(),
            extra=Extra(
                time=validated["下单时间"].time(),
                status=validated["订单状态"],
            ),
            payee=validated["店铺"],
            narration=validated["商品"],
            postings=(
                Posting(
                    amount=validated["订单金额"],
                    account=validated["支付方式"],
                ),
            ),
        )


class Importer(BaseImporter):
    """Importer for Pinduoduo order export CSV files."""

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the Pinduoduo importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            _FILE_NAME_PATTERN,
            excel.Reader(header=0),
            Parser(),
            **kwargs,
        )
