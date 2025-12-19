# 示例：导入并分类

这是一个高级导入示例，演示如何使用 LLM（大语言模型）对账单进行智能分类。

```plaintext
predict/
├── downloads/     # 待导入的账单文件
├── ledger/        # 导入结果目录
│   ├── accounts.beancount         # 账户定义文件（从现有账户中进行预测）
│   ├── existing.beancount         # 现有的交易记录（用于Zero-shot 预测）
│   ├── few_shot_predicted.beancount  # Few-shot 预测结果
│   └── zero_shot_predicted.beancount # Zero-shot 预测结果
├── import.py      # 导入配置脚本
└── README.md      # 说明文档
```

## 使用 llama.cpp 部署开源模型

在 Windows 11 上可通过 winget 安装 llama.cpp，默认支持 vulkan 加速。其他安装方式可参考 [llama.cpp 的安装文档](https://github.com/ggml-org/llama.cpp?tab=readme-ov-file#quick-start)。

```powershell
winget install llama.cpp
```

分别部署用于 Embedding 和 Chat 的模型，例子中使用最轻量的模型。

```shell
llama-server -hf 'unsloth/embeddinggemma-300m-GGUF:Q4_0' --port 1314 \
  --embedding 
llama-server -hf 'unsloth/Qwen3-4B-Instruct-2507-GGUF:IQ4_NL' --port 9527
```

> [!TIP]
> 如果网络不通，可设置环境变量从 ModelScope 下载模型
>
> ```powershell
> $env:MODEL_ENDPOINT="https://www.modelscope.cn"
> ```

通过 openai 的 v1/models 接口查询 llama.cpp 识别到的模型名称（未必与文件名一致）

```powershell
curl http://127.0.0.1:1314/v1/models
curl http://127.0.0.1:9527/v1/models
```

## 使用 beangulp 命令导入

提取到指定文件中

```shell
python import.py extract downloads -o ledger/predicted.beancount -e ledger/existing.beancount
```
