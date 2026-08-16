# Contributing to beancount-daoru

Thank you for your interest in contributing to `beancount-daoru`!

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package and environment management. Follow the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Install all dependencies (including optional features and dev tools):

```shell
uv sync --all-extras
```

## Quality Checks & Testing

Local workflows mirror the automated jobs defined in the [CI workflow](.github/workflows/ci.yml).

## Release Process

Release builds and PyPI publishing are automated via the [release workflow](.github/workflows/release.yml).
