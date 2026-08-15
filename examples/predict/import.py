import os
from pathlib import Path
from textwrap import dedent

import beangulp
import vcr

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

_predict_cache_dir = os.environ.get("PREDICT_CACHE_DIR", None)

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
        cache_dir=Path(_predict_cache_dir) if _predict_cache_dir else None,
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


@vcr.use_cassette(
    os.environ.get("VCR_PATH", ".cassettes/default.yml"),
    record_mode=vcr.record_mode.RecordMode.ONCE,
    match_on=["path", "method", "query", "body"],
    drop_unused_requests=True,
)  # pyright: ignore[reportUntypedFunctionDecorator]
def main() -> None:
    ingest = beangulp.Ingest(CONFIG, HOOKS)
    ingest()


if __name__ == "__main__":
    main()
