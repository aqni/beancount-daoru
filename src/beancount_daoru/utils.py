"""Utility functions for the beancount_daoru package.

This module contains various utility functions that are used across different
parts of the beancount_daoru package to perform common operations.
"""

import itertools
import re
from collections.abc import Iterator


def search_patterns(
    texts: Iterator[str], *patterns: re.Pattern[str]
) -> tuple[Iterator[re.Match[str]], ...]:
    """Search for multiple regex patterns in text iterator.

    This function efficiently searches for multiple regex patterns in an iterator
    of text strings by creating separate copies of the iterator for each pattern,
    avoiding the need to traverse the iterator multiple times.

    Args:
        texts: An iterator of text strings to search in.
        *patterns: Variable number of compiled regex patterns to search for.

    Returns:
        A tuple of iterators, each containing matches for the corresponding pattern.
        The order of iterators matches the order of patterns provided.
    """

    def _find_all(
        text_iter: Iterator[str], pattern: re.Pattern[str]
    ) -> Iterator[re.Match[str]]:
        for text in text_iter:
            yield from pattern.finditer(text)

    text_iters = itertools.tee(texts, len(patterns))
    return tuple(
        _find_all(text_iter, pattern)
        for text_iter, pattern in zip(text_iters, patterns, strict=False)
    )
