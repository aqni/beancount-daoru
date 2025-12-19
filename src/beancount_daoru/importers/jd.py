"""JD.com importer implementation.

This module provides an importer for JD.com bill files that converts
JD.com transactions into Beancount entries.
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

_STATUS_PATTERN = re.compile(r"\(.*\)")


def _validate_amount(v: str) -> str:
    return _STATUS_PATTERN.sub("", v)


def _empty_to_none(v: object | None) -> object:
    if v == "":
        return None
    return v


DecimalField = Annotated[Decimal, BeforeValidator(_validate_amount)]
StrField = Annotated[str | None, AfterValidator(_empty_to_none)]


Record = TypedDict(
    "Record",
    {
        "交易时间": datetime,
        "商户名称": StrField,
        "交易说明": StrField,
        "金额": DecimalField,
        "收/付款方式": str,
        "交易状态": StrField,
        "收/支": StrField,
        "交易分类": StrField,
        "备注": StrField,
    },
)


class Parser(BaseParser):
    """Parser for JD transaction records.

    Implements the Parser protocol to convert JD transaction records
    into Beancount-compatible structures. Handles JD-specific fields and
    logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"京东账号名：(\S+)")  # noqa: RUF001
    __date_pattern = re.compile(r"日期区间：\d{4}-\d{2}-\d{2} 至 (\d{4}-\d{2}-\d{2})")  # noqa: RUF001

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
            date=validated["交易时间"].date(),
            extra=Extra(
                time=validated["交易时间"].time(),
                dc=validated["收/支"],
                status=validated["交易状态"],
                type=validated["交易分类"],
                remarks=validated["备注"],
            ),
            payee=validated["商户名称"],
            narration=validated["交易说明"],
            postings=(
                Posting(
                    account=validated["收/付款方式"],
                    amount=self._parse_amount(validated),
                ),
            ),
        )

    def _parse_amount(self, validated: Record) -> Decimal:
        dc_key = "收/支"
        status_key = "交易状态"
        match (validated[dc_key], validated[status_key]):
            case ("支出" | "不计收支", "交易成功"):
                return -validated["金额"]
            case ("不计收支", "退款成功"):
                return validated["金额"]
            case _:
                raise ParserError(dc_key, status_key)


class Importer(BaseImporter):
    """Importer for JD.com bill files.

    Converts JD.com transaction records into Beancount entries using
    the JD.com extractor and builder implementations.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the JD.com importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"京东交易流水\(申请时间[^)]*\)_\d+\.csv"),
            excel.Reader(header=21, encoding="utf-8-sig"),
            Parser(),
            **kwargs,
        )
