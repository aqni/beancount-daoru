"""Beancount importers for Chinese financial institutions.

This package provides importers for various Chinese financial institutions and
payment platforms, allowing users to easily convert their financial records
into Beancount format for accounting purposes.
"""

from beancount_daoru.hooks.path_to_name import Hook as PathToName
from beancount_daoru.hooks.reorder_by_importer_name import Hook as ReorderByImporterName
from beancount_daoru.importers.alipay import Importer as AlipayImporter
from beancount_daoru.importers.boc import Importer as BOCImporter
from beancount_daoru.importers.bocom import Importer as BOCOMImporter
from beancount_daoru.importers.jd import Importer as JDImporter
from beancount_daoru.importers.meituan import Importer as MeituanImporter
from beancount_daoru.importers.wechat import Importer as WechatImporter

__all__ = [
    "AlipayImporter",
    "BOCImporter",
    "BOCOMImporter",
    "JDImporter",
    "MeituanImporter",
    "PathToName",
    "ReorderByImporterName",
    "WechatImporter",
]

# Optional components - will only be available if dependencies are installed
try:
    from beancount_daoru.hooks.predict_missing_posting import (
        Hook as PredictMissingPosting,
    )

    __all__ += ["PredictMissingPosting"]
except ImportError:
    pass
