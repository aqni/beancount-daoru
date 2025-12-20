import beangulp

from beancount_daoru import (
    AlipayImporter,
    JDImporter,
    MeituanImporter,
    PathToName,
    ReorderByImporterName,
    WechatImporter,
)

CONFIG = [
    AlipayImporter(
        account_mapping={
            "xx@gmail.com": {
                None: "Assets:Payment:Alipay",
                "": "Assets:Payment:Alipay:Balance",
                "余额": "Assets:Payment:Alipay:Balance",
                "余额宝": "Assets:Payment:Alipay:YuEBao",
                "交通银行信用卡(7449)": "Liabilities:Bank:CN:BOC:1875:Credit",
            }
        },
        currency_mapping={
            None: "CNY",
        },
    ),
    JDImporter(
        account_mapping={
            "jd_55370d18d5bb4": {
                None: "Assets:Payment:JD",
                "钱包余额": "Assets:Payment:JD:Balance",
                "先享后付": "Liabilities:Payment:JD:FirstPay",
                "微信支付": "Equity:Transfers:JD",
                "微信-招商银行信用卡": "Equity:Transfers:JD",
                "中国银行信用卡(1875)": "Liabilities:Bank:CN:BOC:1875:Credit",
                "中国银行信用卡(1341)": "Liabilities:Bank:CN:BOC:1341:Credit",
                "交通银行信用卡(0354)": "Liabilities:Bank:CN:BOC:0354:Credit",
            },
        },
        currency_mapping={
            None: "CNY",
        },
    ),
    MeituanImporter(
        account_mapping={
            "SJT714453696": {
                None: "Assets:Payment:Meituan",
                "美团余额": "Assets:Payment:Meituan:Balance",
                "美团月付": "Liabilities:Payment:Meituan:Monthly",
                "中国银行信用卡(1875)": "Liabilities:Bank:CN:BOC:1875:Credit",
                "中国银行信用卡(1341)": "Liabilities:Bank:CN:BOC:1341:Credit",
                "中国银行储蓄卡(3147)": "Equity:Transfers:WeChat:BOC",
                "微信支付": "Equity:Transfers:Meituan:WeChat",
            },
        },
        currency_mapping={
            "¥": "CNY",
        },
    ),
    WechatImporter(
        account_mapping={
            "测试": {
                None: "Assets:Payment:Wechat",
                "零钱": "Assets:Payment:WeChat:Balance",
                "/": "Assets:Payment:WeChat:Balance",
                "零钱通": "Assets:Payment:WeChat:MiniFund",
                "中国银行(1234)": "Equity:Transfers:WeChat:BOC",
                "中国银行": "Equity:Transfers:WeChat:BOC",
                "工商银行(9876)": "Equity:Transfers:WeChat:ICBC",
                "工商银行": "Equity:Transfers:WeChat:ICBC",
                "工商银行储蓄卡(9876)": "Equity:Transfers:WeChat:ICBC",
                "零钱提现服务费": "Expenses:WeChat:Service",
            }
        },
        currency_mapping={
            "¥": "CNY",
        },
    ),
]

HOOKS = [
    PathToName(),
    ReorderByImporterName(),
]


if __name__ == "__main__":
    ingest = beangulp.Ingest(CONFIG, HOOKS)
    ingest()
