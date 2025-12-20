"""Alipay importer implementation.

This module provides an importer for Alipay bill files that converts
Alipay transactions into Beancount entries.
"""

import re
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, TypeAdapter
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


StrField = Annotated[str | None, AfterValidator(_validate_str)]


Record = TypedDict(
    "Record",
    {
        "交易时间": datetime,
        "交易分类": StrField,
        "交易对方": StrField,
        "对方账号": StrField,
        "商品说明": StrField,
        "收/支": StrField,
        "金额": Decimal,
        "收/付款方式": str,
        "交易状态": StrField,
        "备注": StrField,
    },
)


class Parser(BaseParser):
    """Parser for Alipay transaction records.

    Implements the Parser protocol to convert Alipay transaction records
    into Beancount-compatible structures. Handles Alipay-specific fields
    and logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"支付宝账户：(\S+)")  # noqa: RUF001
    __date_pattern = re.compile(
        r"终止时间：\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}]"  # noqa: RUF001
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
        postings = ()
        if amount_and_payee := self._parse_amount(validated):
            amount, payee = amount_and_payee
            postings += (
                Posting(
                    account=validated["收/付款方式"],
                    amount=amount,
                ),
            )
            if payee is not None:
                postings += (
                    Posting(
                        account=payee,
                        amount=-amount,
                    ),
                )
        return Transaction(
            date=validated["交易时间"].date(),
            extra=Extra(
                time=validated["交易时间"].time(),
                dc=validated["收/支"],
                status=validated["交易状态"],
                payee_account=validated["对方账号"],
                type=validated["交易分类"],
                remarks=validated["备注"],
            ),
            payee=validated["交易对方"],
            narration=validated["商品说明"],
            postings=postings,
        )

    def _parse_amount(self, validated: Record) -> tuple[Decimal, str | None] | None:  # noqa: PLR0911
        dc_key = "收/支"
        status_key = "交易状态"
        desc_key = "商品说明"
        amount = validated["金额"]
        match (validated[dc_key], validated[status_key]):
            case ("支出", "交易成功" | "等待确认收货" | "交易关闭"):
                return -amount, None
            case ("收入" | "不计收支", "交易关闭"):
                return None
            case ("收入", "交易成功") | ("不计收支", "退款成功"):
                return amount, None
            case ("不计收支", "交易成功"):
                match validated[desc_key]:
                    case "提现-实时提现":
                        return amount, None
                    case "余额宝-更换货基转入":
                        return amount, None
                    case (
                        "余额宝-单次转入"
                        | "余额宝-安心自动充-自动攒入"
                        | "余额宝-自动转入"
                    ):
                        return -amount, "余额宝"
                    case str(x) if x.startswith("余额宝-") and x.endswith("-收益发放"):
                        return amount, None
                    case _:
                        raise ParserError(dc_key, status_key, desc_key)
            case _:
                raise ParserError(dc_key, status_key)


class Importer(BaseImporter):
    """Importer for Alipay bill files.

    Converts Alipay transaction records into Beancount entries using the Alipay
    parser implementation.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the Alipay importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"支付宝交易明细\(\d{8}-\d{8}\).csv"),
            excel.Reader(header=24, encoding="gbk"),
            Parser(),
            **kwargs,
        )
