from textwrap import dedent

import beangulp

from beancount_daoru import (
    AlipayImporter,
    PathToName,
    PredictMissingPosting,
)

CONFIG = [
    AlipayImporter(
        account_mapping={
            "1234567890": {
                None: "Assets:Payment:Alipay",
                "余额宝": "Assets:Payment:Alipay:YuEBao",
                "余额宝收益": "Income:Investment:Fund:YuEBao",
            },
        },
        currency_mapping={
            None: "CNY",
        },
    ),
]

HOOKS = [
    PredictMissingPosting(
        chat_model_settings={
            "name": "Qwen3-4B-Instruct-2507",
            "base_url": "http://127.0.0.1:9527/v1",
            "api_key": "api-key-not-set",
            "temperature": 0,  # for test
        },
        embed_model_settings={
            "name": "embeddinggemma-300m",
            "base_url": "http://127.0.0.1:1314/v1",
            "api_key": "api-key-not-set",
        },
        extra_system_prompt=(
            dedent(
                """
                特殊规则:
                - 退款 (包括退货) 必须作为负支出处理,切勿将退款分类为收入
                - 对于难以用现有标签分类的账户,视为信息不足
                """
            ).strip()
        ),
    ),
    PathToName(),
]


if __name__ == "__main__":
    ingest = beangulp.Ingest(CONFIG, HOOKS)
    ingest()
