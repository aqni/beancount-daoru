"""Bank of Communications (BCM) importer implementation.

This module provides an importer for Bank of Communications bill files that converts
Bank of Communications transactions into Beancount entries.
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
    ParserError,
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
    return v.replace("\n", "") or None


DecimalField = Annotated[Decimal, BeforeValidator(_amount_validator)]
StrField = Annotated[str | None, AfterValidator(_validate_str)]


Record = TypedDict(
    "Record",
    {
        "Trans Date\n交易日期": date,
        "Trans Time\n交易时间": time,
        "Trading Type\n交易类型": StrField,
        "Dc Flg\n借贷": StrField,
        "Trans Amt\n交易金额": DecimalField,
        "Balance\n余额": DecimalField,
        "Payment Receipt\nAccount\n对方账号": StrField,
        "Payment Receipt\nAccount Name\n对方户名": StrField,
        "Trading Place\n交易地点": StrField,
        "Abstract\n摘要": StrField,
    },
)


class Parser(BaseParser):
    """Parser for Bank of Communications transaction records.

    Implements the Parser protocol to convert Bank of Communications transaction records
    into Beancount-compatible structures. Handles BoCom-specific fields and
    logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"账号/卡号Account/Card No:\s*(\d{19})\s*")
    __date_pattern = re.compile(r"查询止日Query Ending Date:\s*(\d{4}-\d{2}-\d{2})\s*")
    __currency_pattern = re.compile(r"币种Currency:\s*(\w+)\s*")

    @property
    @override
    def reversed(self) -> bool:
        return True

    @override
    def extract_metadata(self, texts: Iterator[str]) -> Metadata:
        account_matches, date_matches, currency_matches = search_patterns(
            texts, self.__account_pattern, self.__date_pattern, self.__currency_pattern
        )
        return Metadata(
            account=next(account_matches).group(1),
            date=date.fromisoformat(next(date_matches).group(1)),
            currency=next(currency_matches).group(1),
        )

    @override
    def parse(self, record: dict[str, str]) -> Transaction:
        validated = self.__validator.validate_python(record)
        return Transaction(
            date=validated["Trans Date\n交易日期"],
            extra=Extra(
                time=validated["Trans Time\n交易时间"],
                dc=validated["Dc Flg\n借贷"],
                type=validated["Trading Type\n交易类型"],
                payee_account=validated["Payment Receipt\nAccount\n对方账号"],
                place=validated["Trading Place\n交易地点"],
            ),
            payee=validated["Payment Receipt\nAccount Name\n对方户名"],
            narration=validated["Abstract\n摘要"],
            postings=(
                Posting(
                    amount=self._parse_amount(validated),
                ),
            ),
            balance=Posting(
                amount=validated["Balance\n余额"],
            ),
        )

    def _parse_amount(self, validated: Record) -> Decimal:
        dc_key = "Dc Flg\n借贷"
        match validated[dc_key]:
            case "借 Dr":
                return -validated["Trans Amt\n交易金额"]
            case "贷 Cr":
                return validated["Trans Amt\n交易金额"]
            case _:
                raise ParserError(dc_key)


class Importer(BaseImporter):
    """Importer for Bank of Communications bill files.

    Converts Bank of Communications transaction records into Beancount entries using
    the Bank of Communications parser implementation.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the Bank of Communications importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"交通银行交易流水\(申请时间[^)]*\).pdf"),
            pdf_table.Reader(table_bbox=(0, 148, 842, 491)),
            Parser(),
            **kwargs,
        )
