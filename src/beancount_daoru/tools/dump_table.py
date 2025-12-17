"""Tool to dynamically collect readers from importers."""

import importlib
import pkgutil
from collections.abc import Iterator

from beancount_daoru import importers
from beancount_daoru.importer import Importer
from beancount_daoru.reader import Reader
from beancount_daoru.readers.pdf_table import Reader as PDFReader


def _collect_readers() -> Iterator[Reader]:
    for _, name, _ in pkgutil.iter_modules(
        importers.__path__, prefix=f"{importers.__name__}."
    ):
        module = importlib.import_module(name)
        cls = module.Importer
        if not issubclass(cls, Importer):
            msg = f"{cls} is not a subclass of {Importer}"
            raise TypeError(msg)
        yield cls.create_reader()


PRESET_READERS = [*_collect_readers(), PDFReader()]

for reader in PRESET_READERS:
    recreated = type(reader)() # 验证类可反序列化的
    print(recreated)

# 提供一个命令行工具用来将已知文件dump成json文件
# 集成测试比较两种路径结果一致来验证 dump 和 loader 的正确性
# - pdf --- dump ---> json --- dummy reader ---> dict
# - pdf --- reader ---> dict
# 只需要一对（pdf,json）即可， dict 作为临时变量就可
# 这里在同一个文件实现一个 dump 和 loader
