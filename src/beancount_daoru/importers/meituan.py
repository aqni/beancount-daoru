"""Meituan importer implementation.

This module provides an importer for Meituan bill files that converts
Meituan transactions into Beancount entries.
"""

import re
from collections.abc import Iterator
from datetime import date, datetime
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
from beancount_daoru.readers import excel
from beancount_daoru.utils import search_patterns


def _validate_str(v: str | None) -> str | None:
    if v is None:
        return None
    if v in ("", "/"):
        return None
    return v


def _split_amount(v: str) -> tuple[str, str]:
    return v[0], v[1:]


AmountField = Annotated[tuple[str, Decimal], BeforeValidator(_split_amount)]
StrField = Annotated[str | None, AfterValidator(_validate_str)]


Record = TypedDict(
    "Record",
    {
        "交易成功时间": datetime,
        "交易类型": StrField,
        "订单标题": StrField,
        "收/支": StrField,
        "实付金额": AmountField,
        "支付方式": str,
        "备注": StrField,
    },
)


class Parser(BaseParser):
    """Parser for Meituan transaction records.

    Implements the Parser protocol to convert Meituan transaction records
    into Beancount-compatible structures. Handles Meituan-specific fields and
    logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"美团用户名：\[([^\]]*)\]")  # noqa: RUF001
    __date_pattern = re.compile(r"终止时间：\[(\d{4}-\d{2}-\d{2})\]")  # noqa: RUF001

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
            date=validated["交易成功时间"].date(),
            extra=Extra(
                time=validated["交易成功时间"].time(),
                dc=validated["收/支"],
                type=validated["交易类型"],
                remarks=validated["备注"],
            ),
            payee="美团",
            narration=validated["订单标题"],
            postings=(*self._parse_postings(validated),),
        )

    def _parse_postings(self, validated: Record) -> Iterator[Posting]:
        amount = self._parse_amount(validated)
        currency = validated["实付金额"][0]

        yield Posting(
            account=validated["支付方式"],
            amount=amount,
            currency=currency,
        )

        counter_party = self._parse_counter_party(validated)
        if counter_party is not None:
            yield Posting(
                account=counter_party,
                amount=-amount,
                currency=currency,
            )

    def _parse_amount(self, validated: Record) -> Decimal:
        dc_key = "收/支"

        match validated[dc_key]:
            case "支出":
                return -validated["实付金额"][1]
            case "收入":
                return validated["实付金额"][1]
            case _:
                raise ParserError(dc_key)

    def _parse_counter_party(self, validated: Record) -> str | None:
        type_key = "交易类型"
        narration_key = "订单标题"

        match (validated[type_key], validated[narration_key]):
            case ("还款", str(x)) if x.startswith("【美团月付】主动还款"):
                return "美团月付"
            case ("支付" | "退款", _):
                return None
            case _:
                raise ParserError(type_key, narration_key)


class Importer(BaseImporter):
    """Importer for Meituan bill files.

    Converts Meituan transaction records into Beancount entries using
    the Meituan extractor and builder implementations.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the Meituan importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"美团账单\(\d{8}-\d{8}\)\.csv"),
            excel.Reader(header=19, encoding="utf-8-sig"),
            Parser(),
            **kwargs,
        )
