# 示例：仅导入

这是一个基础的导入示例，演示如何使用 beancount-daoru 工具将账单文件导入到 Beancount 中。

```plaintext
import_only/
├── documents/     # 归档的账单文件
├── downloads/     # 待导入的账单文件
├── ledger/        # 导入结果目录
│   └── imported.beancount  # 导入的交易记录
├── import.py      # 导入配置脚本
└── README.md      # 说明文档
```

## 使用 beangulp 命令导入

> [!WARNING]
> 在 Windows 上，建议设置环境变量使 Python 全局使用 UTF-8，能够避免很多编码问题。
>
> ```powershell
> $env:PYTHONUTF8 = "1"
> ```

### 查看是否能够识别账单文件

```shell
python import.py identify downloads
```

此命令会扫描 `downloads` 目录中的文件，并显示哪些文件可以被识别和导入。

### 提取交易数据到指定文件中

```shell
python import.py extract downloads -o ledger/imported.beancount
```

此命令会将 `downloads` 目录中所有可识别的账单文件转换为 Beancount 格式的交易记录，
并保存到 `ledger/imported.beancount` 文件中。

### 文件归档

```shell
python import.py archive downloads -o documents
```

此命令会将已成功导入的账单文件从 `downloads` 移动到 `documents` 目录中，
避免重复导入。
