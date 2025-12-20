# beancount-daoru

一个专为中文用户设计的 Beancount 账单导入工具，让复式记账更高效。

*项目仍在开发中，API 可能会发生变化，欢迎反馈或建议。*

## 功能

亮点：

- **多源账单覆盖**：支持主流支付平台，以及部分银行账单

- **原生格式解析**：直接导入 PDF/CSV/XLSX 原始账单，无需手动转换

- **LLM 智能分类**：集成大语言模型自动预测交易分类

- **官方生态兼容**：适配 [Beangulp](https://github.com/beancount/beangulp)导入流程，
  支持 [Fava](https://github.com/beancount/fava) 可视化导入

- **灵活账户映射**：支持多账户区分，自定义币种配置

当前支持的账单源：

| 源 | 导出方式 | 格式 |
| --- | --- | --- |
| 支付宝 | APP导出，全部勾选，发送到邮箱 | csv |
| 微信 | APP导出，全部勾选，发送到邮箱 | xlsx |
| 京东 | APP导出，全部勾选，发送到邮箱 | csv |
| 美团 | APP导出，全部勾选，发送到邮箱 | csv |
| 中国银行 | APP导出，全部勾选，APP内下载 | pdf |
| 交通银行 | APP导出，全部勾选，发送到邮箱 | pdf |

## 使用

### 安装

```shell
pip install beancount-daoru
```

如果需要使用 LLM 功能，需要安装额外依赖：

```shell
pip install beancount-daoru[llm]
```

### 简单用例

最简单的使用方式是创建一个导入配置脚本，例如 `import.py`：

```python
import beangulp
from beancount_daoru import AlipayImporter

CONFIG = [
    AlipayImporter(
        account_mapping={
            "your-alipay-account-name": {
                None: "Assets:Alipay",
                "余额": "Assets:Alipay:Balance",
                "余额宝": "Assets:Alipay:YuEBao",
                "中国银行(xxxx)": "Assets:Bank:BOC",
            }
        },
        currency_mapping={
            None: "CNY",
        },
    ),
]

if __name__ == "__main__":
    ingest = beangulp.Ingest(CONFIG)
    ingest()
```

然后运行 beangulp 命令识别、导入并归档账单文件，例如：

```shell
# 识别账单文件
python import.py identify /path/to/your/bills/dir
# 导入账单文件
python import.py extract /path/to/your/bills/dir -o output.beancount
# 归档账单文件
python import.py archive /path/to/your/bills/dir -o /path/to/your/archive/dir
```

另一种方法是在 Fava 中进行可视化导入，需要在主账本中添加`import-config` 和 `import-dirs` 这两个配置，具体参阅
[Fava 帮助文档](https://fava.pythonanywhere.com/example-beancount-file/help/import)。

**工具通过文件名识别账单，导入时务必保留账单原始文件名**。
更多使用用例可参考源码中示例。

## 延伸

### 相关项目

国内项目：

- [double-entry-generator](https://github.com/deb-sig/double-entry-generator):
  基于规则将各种账单格式转换为 Beancount 或 Ledger 格式
  - [BeanBridge](https://github.com/fatsheep2/beanBridge):
    double-entry-generator 的 Web 前端实现
  - [bill-parser](https://github.com/deb-sig/bill-file-converter):
    将非 Excel 账单文件（PDF/EML 等）转换为 CSV 格式
- [beancount-gs](https://github.com/BaoXuebin/beancount-gs):
  基于 beancount 提供个人记账财务管理的 RESTful API 服务（包含前端页面）
- [Beancount-Trans](https://github.com/dhr2333/Beancount-Trans):
  一款（自托管）智能账单转换平台，帮助用户轻松将日常账单（如支付宝、微信支付、银行账单等）转换为专业记账格式，并提供完整的财务报表服务。
- [china_bean_importers](https://github.com/jiegec/china_bean_importers):
  Beancount 导入脚本，不支持 Beancount 3
- [beancount-homemade-importers](https://github.com/heyeshuang/beancount-homemade-importers)：
  一些在中国用的Beancount导入设置
- [beancount_cc_importers](https://pypi.org/project/beancount_cc_importers):
  Simple importers for personal usage

国外项目：

- [smart_importer](https://github.com/beancount/smart_importer)：
  beancount 官方提供的基于机器学习的分类预测器
- [Beancount Red's Importers](https://github.com/redstreet/beancount_reds_importers):
  Simple ingesting tools for Beancount. More importantly, a framework to allow
  you to easily write your own importers.
- [Beanborg](https://github.com/luciano-fiandesio/beanborg)：
  Automatic AI-powered transactions categorizer for Beancount.
- [BeanHub Import](https://github.com/LaunchPlatform/beanhub-import):
  a simple, declarative, smart, and easy-to-use library for importing extracted
  transactions from beanhub-extract.
- [beanquery-mcp](https://github.com/vanto/beanquery-mcp):
  Beancount MCP Server is an experimental implementation that utilizes the Model
  Context Protocol (MCP) to enable AI assistants to query and analyze Beancount
  ledger files using Beancount Query Language (BQL) and the beanquery tool.

不活跃项目：

- [bento](https://github.com/p-zany/bento):
  A personal finance management system built with Beancount and Fava, providing
  automated transaction imports and classification.
- [Beancount-CSVImporter](https://github.com/sphish/Beancount-CSVImporter):
  CSVImporter for beancount, mainly used to import transaction records of Alipay
  and WeChat
- [BeancountSample](https://github.com/lidongchao/BeancountSample):
  BeancountSample
- [beancount_importer](https://github.com/chryoung/beancount_importer):
  a GUI tool for importing Alipay/Wechat bill to beancount file
- [beancollect](https://github.com/Xuanwo/beancollect):
  为 beancount 开发的账单导入工具

### 推荐阅读

基础：

- [Awesome Beancount](https://awesome-beancount.com/):
  A curated list of resources for Beancount
- [Beancout.io 帮助中心](https://beancount.io/zh/docs/help-center):
  提供 beancount 商业服务的团队维护的使用指南
- [The Beancount Ecosystem: A Comprehensive Analysis](https://beancount.io/blog/2025/04/15/beancount-ecosystem)

使用分享：

- [Beancount复式记账：接地气的Why and How](https://blog.zsxsoft.com/post/41):
  "看你的文章像是在看beancount的中文综述，很棒！"
- [『Beancount指南』复式记账](https://fermi.ink/posts/2023/05/31/01/) :
  一篇深入全面的使用心得
- [wzyboy 的博客](https://bing.com/search?q=beancount+site:wzyboy.im):
  比较早期的安利文，后续探讨了证券投资场景
- [BYVoid 的博客](https://byvoid.com/zhs/tags/beancount/):
  比较全面的介绍，关于 Beancount 经典系列文章
- [YiShanhe 的博客](https://yishanhe.net/tags/beancount/):
  对房产、RSU、ESPP的建模进行了探讨
- [EinVerne 的博客](https://blog.einverne.info/categories.html#Beancount):
  全面的介绍，尤其是对各类账单导入进行了分享
- [KAAAsS 的博客](https://blog.kaaass.net/archives/category/continuous/复式记账指北):
  探讨了基于 Telegram Bot 的自动记账方案
- [double-entry-generator "账户映射"文档](https://deb-sig.github.io/double-entry-generator/configuration/accounts.html):
  double-entry-generator 作者提供的账户分类最佳实践

自动化探讨：

- [用于支付宝和微信账单的Beancount Importer](https://zhuanlan.zhihu.com/p/103705480)
  ——一篇自己实现 Importer 的心得
- [使用 Beancount 进行记账并自动记录一卡通消费](https://lug.ustc.edu.cn/planet/2020/08/keeping-account-with-beancount/)：
  ——分享了编写 Importer 自动记录一卡通消费的心得
- [关于账单重复的处理方案](https://github.com/deb-sig/double-entry-generator/discussions/162)：
  账单自动导入场景中，关于账单重复情况处理方案的讨论

- [Essential Beancount plugins and import automation for 2025](https://beancount.io/forum/t/essential-beancount-plugins-and-import-automation-for-2025/76)
  ——一篇2025年的关于插件和自动导入的综述与讨论
- [The Five-Minute Ledger Update](https://reds-rants.netlify.app/personal-finance/the-five-minute-ledger-update/)：
  利用自动化工具减少记账时间的讨论

LLM 研究：

- [Beancount.io - 使用 LLM 实现自动化并增强 Beancount 的簿记功能](https://beancount.io/zh/docs/Solutions/using-llms-to-automate-and-enhance-bookkeeping-with-beancount)
- [Large Language Models for Code Generation of Plain Text Accounting with
  Domain Specific Languages](https://github.com/JuFrei/LLMs-for-Plain-Text-Accounting)
- [Evaluating Financial Literacy of Large Language Models through
  DomainSpecific Languages for Plain Text Accounting](https://aclanthology.org/2025.finnlp-1.6/)
- [FinLFQA: Evaluating Attributed Text Generation of LLMs in Financial Long-Form
  Question Answering](https://arxiv.org/abs/2510.06426)
