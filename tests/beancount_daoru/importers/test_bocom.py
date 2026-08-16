import datetime
from decimal import Decimal

import pytest

from beancount_daoru.importer import Extra, Metadata, ParserError, Posting, Transaction
from beancount_daoru.importers.bocom import Parser


@pytest.fixture(scope="module")
def parser() -> Parser:
    return Parser()


def test_extract_metadata(parser: Parser) -> None:
    caption = (
        "交通银行个人客户交易清单\n"
        "Bocom Personal Account Details\n"
        "  支持交通银行手机银行扫码验真\n"
        "账号/卡号Account/Card No: 6222612345678901234 "
        "打印时间Printing Time: 2020-12-31 12:00:00 "
        "柜员Search Teller: EBB0001\n"
        "户名Account Name: 李四 "
        "查询止日Query Ending Date: 2020-01-31 "
        "查询起日Query Starting Date: 2020-01-01\n"
        "币种Currency: 人民币 CNY\n"
        "其他查询条件Query Conditions： 无\n"
        "第 1 / 13 页"
    )
    metadata = parser.extract_metadata(
        filename="交通银行交易流水(申请时间2026年08月15日23时10分20秒).pdf",
        texts=iter([caption]),
    )
    assert metadata == Metadata(
        account="6222612345678901234",
        date=datetime.date(2020, 1, 31),
        currency="人民币",
    )


TEST_PARAMS_LIST = [
    (
        {
            "序号\nSerial": "1",
            "交易日期\nTrans Date": "2020-01-01",
            "交易时间\nTrans Time": "10:00:00",
            "交易类型\nTrading Type": "存款利息",
            "借贷状态\nDc Flg": "C",
            "交易金额\nTrans Amt": "1.00",
            "余额\nBalance": "1000.00",
            "对方账号\nPayment Receipt": "123456789012345\n123",
            "对方户名\nPayment Receipt": "应付个人活期储蓄存款\n利息",
            "交易地点\nTrading Place": "批处理",
            "摘要\nAbstract": "",
        },
        Transaction(
            date=datetime.date(2020, 1, 1),
            extra=Extra(
                time=datetime.time(10, 0, 0),
                dc="C",
                type="存款利息",
                payee_account="123456789012345123",
                place="批处理",
            ),
            payee="应付个人活期储蓄存款利息",
            postings=(
                Posting(
                    amount=Decimal("1.00"),
                ),
            ),
            balance=Posting(
                amount=Decimal("1000.00"),
            ),
        ),
    ),
    (
        {
            "序号\nSerial": "2",
            "交易日期\nTrans Date": "2020-01-02",
            "交易时间\nTrans Time": "11:00:00",
            "交易类型\nTrading Type": "网上支付",
            "借贷状态\nDc Flg": "D",
            "交易金额\nTrans Amt": "10.00",
            "余额\nBalance": "990.00",
            "对方账号\nPayment Receipt": "123456789",
            "对方户名\nPayment Receipt": ("支付宝（中国）网络技\n术有限公司"),
            "交易地点\nTrading Place": "支付宝（中国）网络技\n术有限公司",
            "摘要\nAbstract": (
                "网上支付 其他商家\n消费 订单编号\n20200102110123456\n"
                "123456789012345\n柒一拾壹（天津\n）商业有限公 交易\n流水号\n"
                "20200102123456789\n12345678901234"
            ),
        },
        Transaction(
            date=datetime.date(2020, 1, 2),
            payee="支付宝（中国）网络技术有限公司",
            narration=(
                "网上支付 其他商家消费 订单编号20200102110123456123456789012345"
                "柒一拾壹（天津）商业有限公 交易流水号2020010212345678912345678901234"
            ),
            extra=Extra(
                time=datetime.time(11, 0, 0),
                dc="D",
                type="网上支付",
                payee_account="123456789",
                place="支付宝（中国）网络技术有限公司",
            ),
            postings=(
                Posting(
                    amount=Decimal("-10.00"),
                ),
            ),
            balance=Posting(
                amount=Decimal("990.00"),
            ),
        ),
    ),
]


@pytest.mark.parametrize(("record", "transaction"), TEST_PARAMS_LIST)
def test_build(
    parser: Parser, record: dict[str, str], transaction: Transaction
) -> None:
    assert parser.parse(record) == transaction


ERROR_PARAMS_LIST = [
    (
        {
            "序号\nSerial": "3",
            "交易日期\nTrans Date": "2020-01-03",
            "交易时间\nTrans Time": "12:00:00",
            "交易类型\nTrading Type": "其他交易",
            "借贷状态\nDc Flg": "",
            "交易金额\nTrans Amt": "5.00",
            "余额\nBalance": "985.00",
            "对方账号\nPayment Receipt": "123456789012345",
            "对方户名\nPayment Receipt": "支付宝-消费",
            "交易地点\nTrading Place": "支付宝-消费",
            "摘要\nAbstract": (
                "网上支付 生活服务\n消费 订单编号\n1234567890123456\n"
                "支付宝-消费 交易\n流水号\n1234567890123456"
            ),
        },
        r"unsupported value combination of fields: ('借贷状态\nDc Flg',)",
    ),
]


@pytest.mark.parametrize(("record", "message"), ERROR_PARAMS_LIST)
def test_parse_error(parser: Parser, record: dict[str, str], message: str) -> None:
    with pytest.raises(ParserError) as excinfo:
        _ = parser.parse(record)
    assert str(excinfo.value) == message
