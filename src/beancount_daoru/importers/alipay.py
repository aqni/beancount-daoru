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

from beancount_daoru import importer
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


class _Reader(excel.Reader):
    def __init__(self) -> None:
        super().__init__(header=24, encoding="gbk")
        self.regex = r"支付宝交易明细\(\d{8}-\d{8}\)\.csv"

    @override
    def identify(self, file: importer.Path) -> bool:
        return re.fullmatch(self.regex, file.name) is not None


class _Parser(importer.Parser):
    _validator = TypeAdapter(Record)
    _account_pattern = re.compile(r"支付宝账户：(\S+)")  # noqa: RUF001
    _date_pattern = re.compile(
        r"终止时间：\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}]"  # noqa: RUF001
    )

    @property
    @override
    def reversed(self) -> bool:
        return True

    @override
    def extract_metadata(self, texts: Iterator[str]) -> importer.Metadata:
        account_matches, date_matches = search_patterns(
            texts, self._account_pattern, self._date_pattern
        )
        return importer.Metadata(
            account=next(account_matches).group(1),
            date=date.fromisoformat(next(date_matches).group(1)),
        )

    @override
    def parse(self, record: dict[str, str]) -> importer.Transaction:
        validated = self._validator.validate_python(record)
        postings = ()
        if amount := self._parse_amount(validated):
            postings = (
                importer.Posting(
                    account=validated["收/付款方式"],
                    amount=amount,
                ),
            )
        return importer.Transaction(
            date=validated["交易时间"].date(),
            extra=importer.Extra(
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

    def _parse_amount(self, validated: Record) -> Decimal | None:  # noqa: PLR0911
        dc_key = "收/支"
        status_key = "交易状态"
        desc_key = "商品说明"
        amount = validated["金额"]
        match (validated[dc_key], validated[status_key]):
            case ("支出", "交易成功" | "等待确认收货" | "交易关闭"):
                return -amount
            case ("收入" | "不计收支", "交易关闭"):
                return None
            case ("收入", "交易成功") | ("不计收支", "退款成功"):
                return amount
            case ("不计收支", "交易成功"):
                match validated[desc_key]:
                    case "提现-实时提现":
                        return amount
                    case "余额宝-更换货基转入":
                        return amount
                    case (
                        "余额宝-单次转入"
                        | "余额宝-安心自动充-自动攒入"
                        | "余额宝-自动转入"
                    ):
                        return -amount
                    case str(x) if x.startswith("余额宝-") and x.endswith("-收益发放"):
                        return amount
                    case _:
                        raise importer.ParserError(dc_key, status_key, desc_key)
            case _:
                raise importer.ParserError(dc_key, status_key)


class Importer(importer.Importer):
    """Importer for Alipay bill files.

    Converts Alipay transaction records into Beancount entries using the Alipay
    parser implementation.
    """

    @override
    @classmethod
    def create_reader(cls) -> _Reader:
        return _Reader()

    @override
    @classmethod
    def create_parser(cls) -> _Parser:
        return _Parser()

    def __init__(self, **kwargs: Unpack[importer.ImporterKwargs]) -> None:
        """Initialize the Alipay importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(**kwargs)
