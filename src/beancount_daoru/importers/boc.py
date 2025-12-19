"""Bank of China (BOC) importer implementation.

This module provides an importer for Bank of China bill files that converts
Bank of China transactions into Beancount entries.
"""

import re
from collections.abc import Iterator
from datetime import date, time
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, TypeAdapter
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
from beancount_daoru.readers import pdf_table
from beancount_daoru.utils import search_patterns


def _amount_validator(v: str) -> Decimal:
    return Decimal(v.replace(",", ""))


def _validate_str(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.replace("\n", "")
    if all(x == "-" for x in v):
        return None
    return v


DecimalField = Annotated[Decimal, BeforeValidator(_amount_validator)]
StrField = Annotated[str | None, AfterValidator(_validate_str)]


Record = TypedDict(
    "Record",
    {
        "记账日期": date,
        "记账时间": time,
        "币别": str,
        "金额": DecimalField,
        "余额": DecimalField,
        "交易名称": StrField,
        "渠道": StrField,
        "附言": StrField,
        "对方账户名": StrField,
        "对方卡号/账号": StrField,
    },
)


class Parser(BaseParser):
    """Parser for Bank of China transaction records.

    Implements the Parser protocol to convert Bank of China transaction records
    into Beancount-compatible structures. Handles BOC-specific fields and
    logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"借记卡号：\s+(\d{19})\s+")  # noqa: RUF001
    __date_pattern = re.compile(
        r"交易区间：\s*\d{4}-\d{2}-\d{2}\s*至\s*(\d{4}-\d{2}-\d{2})"  # noqa: RUF001
    )

    @property
    @override
    def reversed(self) -> bool:
        return True

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
            date=validated["记账日期"],
            extra=Extra(
                time=validated["记账时间"],
                type=validated["交易名称"],
                payee_account=validated["对方卡号/账号"],
                place=validated["渠道"],
            ),
            payee=validated["对方账户名"],
            narration=validated["附言"],
            postings=(
                Posting(
                    amount=validated["金额"],
                    currency=validated["币别"],
                ),
            ),
            balance=Posting(
                amount=validated["余额"],
                currency=validated["币别"],
            ),
        )


class Importer(BaseImporter):
    """Importer for Bank of China bill files.

    Converts Bank of China transaction records into Beancount entries using
    the Bank of China parser implementation.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the Bank of China importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"交易流水明细\d{14}\.pdf"),
            pdf_table.Reader(table_bbox=(0, 125, 842, 420)),
            Parser(),
            **kwargs,
        )
