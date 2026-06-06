from collections.abc import Generator

import beangulp
from beancount import Account, Posting, Transaction
from typing_extensions import Unpack

from beancount_daoru import (
    AlipayImporter,
    Classifier,
    PathToName,
    RuleContext,
)

alipay_importer = AlipayImporter(
    account_mapping={
        "1234567890": {
            None: "Assets:Payment:Alipay",
            "余额宝": "Assets:Payment:Alipay:YuEBao",
        },
    },
    currency_mapping={
        None: "CNY",
    },
)

alipay_classifier = Classifier()
alipay_importer = alipay_classifier.wrap(alipay_importer)


@alipay_classifier.simple_rule
def communication_card(txn: Transaction) -> Account | None:
    match txn.payee:
        case "北京市政交通一卡通":
            return "Expenses:Transportation:Public"
        case _:
            return None


@alipay_classifier.rule
def yuebao_interest(
    txn: Transaction, **ctx: Unpack[RuleContext]
) -> Generator[Posting | None, None, None]:
    if not isinstance(txn.narration, str):
        return
    if not isinstance(ctx["importer"], AlipayImporter):
        return
    if txn.narration.startswith("余额宝-") and txn.narration.endswith("-收益发放"):
        yield Posting(
            account="Income:Investment:Fund:YuEBao",
            units=None,
            cost=None,
            price=None,
            flag=None,
            meta=None,
        )


CONFIG = [
    alipay_importer,
]

HOOKS = [
    PathToName(),
]


if __name__ == "__main__":
    ingest = beangulp.Ingest(CONFIG, HOOKS)
    ingest()
