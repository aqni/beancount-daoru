"""WeChat Pay importer implementation.

This module provides an importer for WeChat Pay bill files that converts
WeChat Pay transactions into Beancount entries.
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
        "交易时间": datetime,
        "交易类型": StrField,
        "交易对方": StrField,
        "商品": StrField,
        "收/支": StrField,
        "金额(元)": AmountField,
        "支付方式": str,
        "当前状态": StrField,
        "备注": StrField,
    },
)


class Parser(BaseParser):
    """Parser for WeChat Pay transaction records.

    Implements the Parser protocol to convert WeChat Pay transaction records
    into Beancount-compatible structures. Handles WeChat Pay-specific fields and
    logic for determining transaction amounts and directions.
    """

    __validator = TypeAdapter(Record)
    __account_pattern = re.compile(r"微信昵称：\[([^\]]*)\]")  # noqa: RUF001
    __date_pattern = re.compile(r"终止时间：\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}]")  # noqa: RUF001

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
                status=validated["当前状态"],
                type=validated["交易类型"],
                remarks=validated["备注"],
            ),
            payee=validated["交易对方"],
            narration=validated["商品"],
            postings=(*self._parse_postings(validated),),
        )

    def _parse_postings(self, validated: Record) -> Iterator[Posting]:
        account, amount, counter_party, other_posting = self._parse_simple_postings(
            validated
        )
        currency = validated["金额(元)"][0]

        yield Posting(
            account=account,
            amount=amount,
            currency=currency,
        )

        if counter_party is not None:
            yield Posting(
                account=counter_party,
                amount=-amount,
                currency=currency,
            )

        if other_posting is not None:
            yield other_posting

    def _parse_simple_postings(
        self, validated: Record
    ) -> tuple[str, Decimal, str | None, Posting | None]:
        dc_key = "收/支"
        type_key = "交易类型"
        status_key = "当前状态"
        remarks_key = "备注"

        method = validated["支付方式"]
        amount = validated["金额(元)"][1]

        status = validated[status_key]
        if status is not None and status.startswith("已退款"):
            status = "已退款"

        txn_type = validated[type_key]
        if txn_type is not None and txn_type.endswith("-退款"):
            txn_type = "退款"

        match (
            validated[dc_key],
            txn_type,
            status,
            validated[remarks_key],
        ):
            case (
                ("支出", "商户消费" | "分分捐" | "亲属卡交易", "支付成功" | "已退款", _)
                | ("支出", "赞赏码" | "转账", "朋友已收钱", _)
                | ("支出", "扫二维码付款", "已转账", _)
            ):
                return method, -amount, None, None
            case (
                ("收入", "其他", "已到账", _)
                | ("收入", "商户消费", "充值成功", _)
                | ("收入", "二维码收款", "已收钱", _)
                | ("收入", "微信红包", "已存入零钱", _)
                | (None, "购买理财通" | "信用卡还款", "支付成功", _)
                | ("收入", "退款", "已退款", _)
            ):
                return method, amount, None, None
            case (None, str(x), "支付成功", _) if x.startswith("转入零钱通-来自"):
                return method, -amount, "零钱通", None
            case (None, str(x), "支付成功", _) if x.startswith("零钱通转出-到"):
                return "零钱通", -amount, x[len("零钱通转出-到") :], None
            case (None, "零钱充值", "充值完成", _):
                return method, -amount, "零钱", None
            case (None, "零钱提现", "提现已到账", str(x)) if x.startswith("服务费"):
                currency_and_amount = x[len("服务费") :]
                return (
                    method,
                    -amount,
                    "零钱",
                    Posting(
                        amount=Decimal(currency_and_amount[1:]),
                        account="零钱提现服务费",
                        currency=currency_and_amount[0],
                    ),
                )
            case _:
                raise ParserError(dc_key, type_key, status_key, remarks_key)


class Importer(BaseImporter):
    """Importer for WeChat Pay bill files.

    Converts WeChat Pay transaction records into Beancount entries using
    the WeChat Pay parser implementation.
    """

    def __init__(self, **kwargs: Unpack[ImporterKwargs]) -> None:
        """Initialize the WeChat Pay importer.

        Args:
            **kwargs: Additional configuration parameters.
        """
        super().__init__(
            re.compile(r"微信支付账单流水文件\(\d{8}-\d{8}\).*\.xlsx"),
            excel.Reader(header=16),
            Parser(),
            **kwargs,
        )
