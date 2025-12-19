# 贡献指南

欢迎你对 beancount-daoru 项目感兴趣！我们非常欢迎任何形式的贡献，包括但不限于：

- 提交 Bug 报告
- 提交功能请求
- 改进文档
- 提交 Pull Request

## 开发

### 环境准备

使用 uv 进行项目管理

```shell
pip install uv
```

同步开发环境:

```shell
uv sync --all-extras
```

激活虚拟环境：

```shell
uv run python
```

或者使用:

```shell
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows
```

### 代码检查

我们在项目中使用多种工具来确保代码质量：

```shell
# 运行所有检查
uv run ruff check .

# 自动修复代码风格问题
uv run ruff format .

# 类型检查
uv run pyright
```

### 运行测试

运行所有测试：

```shell
uv run pytest
```

运行测试并生成覆盖率报告：

```shell
uv run pytest --cov=src
```

## 发布

该项目使用 GitHub Actions 自动发布到 PyPI。当推送符合 `v*.*.*` 模式的标签时，会自动触发发布流程。
