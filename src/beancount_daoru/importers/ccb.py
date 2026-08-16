"""China Construction Bank (CCB) importer implementation.

This module provides an importer for China Construction Bank bill files that converts
China Construction Bank transactions into Beancount entries.
"""

import re
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Annotated, NamedTuple

from pydantic import BeforeValidator, TypeAdapter
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
from beancount_daoru.utils import search_patterns


class _AccountAndName(NamedTuple):
    id: str | None
    name: str | None


def _parse_account(v: str) -> _AccountAndName:
    if v is None or v.strip() == "":
        return _AccountAndName(None, None)
    account_id, account_name = v.split("/")
    return _AccountAndName(account_id, account_name)


DecimalField = Annotated[Decimal, BeforeValidator(lambda v: v.replace(",", ""))]


Record = TypedDict(
    "Record",
    {
        "摘要": str,
        "币别": str,
        "交易日期": Annotated[date, BeforeValidator(date.fromisoformat)],
        "交易金额": DecimalField,
        "账户余额": DecimalField,
        "交易地点/附言": str,
        "对方账号与户名": Annotated[_AccountAndName, BeforeValidator(_parse_account)],
    },
)


class Parser(BaseParser):
    """Parser for China Construction Bank transaction records.

    Implements the Parser protocol to convert China Construction Bank transaction
    records into Beancount-compatible structures. Handles CCB-specific fields and
    logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"卡号/账号:(\d{19})")
    __date_pattern = re.compile(r"结束日期:(\d{8})")

    @override
    def extract_metadata(self, texts: Iterator[str]) -> Metadata:
        account_matches, date_matches = search_patterns(
            texts, self.__account_pattern, self.__date_pattern
        )
        return Metadata(
            account=next(account_matches).group(1),
            date=date.fromisoformat(next(date_matches).group(1)),
        )

    @override
    def parse(self, record: dict[str, str]) -> Transaction:
        validated = self.__validator.validate_python(record)
        return Transaction(
            date=validated["交易日期"],
            extra=Extra(
                type=validated["摘要"],
                payee_account=validated["对方账号与户名"].id,
            ),
            payee=validated["对方账号与户名"].name,
            narration=validated["交易地点/附言"],
            postings=(
                Posting(
                    amount=validated["交易金额"],
                    currency=validated["币别"],
                ),
            ),
            balance=Posting(
                amount=validated["账户余额"],
                currency=validated["币别"],
            ),
        )


class Importer(BaseImporter):
    """Importer for China Construction Bank bill files.

    Converts China Construction Bank transaction records into Beancount entries using
    the China Construction Bank parser implementation.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the China Construction Bank importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"hqmx_\d{14}\.xls"),
            excel.Reader(header=3),
            Parser(),
            **kwargs,
        )
