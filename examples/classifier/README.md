# 示例：导入并手动分类

这是一个高级导入示例，演示如何使用自定义函数对账单进行手动分类。

```plaintext
predict/                
├── import.py           # 导入配置脚本
├── imported.beancount  # 导入配置脚本
├── README.md           # 说明文档
└── ...                 # 待导入账单
```

## 使用 beangulp 命令导入

提取到指定文件中

```shell
python import.py extract . -o imported.beancount
```
