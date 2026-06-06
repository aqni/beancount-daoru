"""Classifier hook for Beangulp.

This module provides a mechanism to automatically classify imported transactions
by applying custom rules to append matching postings.
"""

import datetime
from collections.abc import Generator
from typing import Protocol, final

from beancount.core.data import Account, Directive, Directives, Posting, Transaction
from beangulp import Importer
from typing_extensions import TypedDict, Unpack, override

from beancount_daoru.hook import Hook, Imported


class RuleContext(TypedDict):
    """Contextual information provided to a rule during evaluation.

    Attributes:
        filename: The path of the file being imported.
        account: The root account associated with the importer.
        importer: The active Beangulp importer instance.
        existing: A list of existing Beancount directives.
    """

    filename: str
    account: Account
    importer: Importer
    existing: Directives


class Rule(Protocol):
    """Protocol defining a standard classification rule.

    A rule evaluates a transaction and its context, and yields new postings
    to be added to that transaction.
    """

    def __call__(
        self, txn: Transaction, **ctx: Unpack[RuleContext]
    ) -> Generator[Posting, None, None]:
        """Evaluates a transaction and yields generated postings.

        Args:
            txn: The transaction currently being evaluated.
            **ctx: Contextual information regarding the import process,
                including the filename, base account, active importer,
                and existing directives.

        Yields:
            Posting: New postings to be appended to the transaction.
        """
        ...


class SimpleRule(Protocol):
    """Protocol defining a simplified classification rule.

    A simple rule evaluates only the transaction itself and returns either
    an account string (to which a new posting should be made) or None.
    """

    def __call__(self, txn: Transaction) -> Account | None:
        """Evaluates a transaction to determine a matching account.

        Args:
            txn: The transaction currently being evaluated.

        Returns:
            The account string (e.g., "Expenses:Food") if the transaction
            matches the rule's criteria, or None if the rule does not apply.
        """
        ...


class Classifier(Hook):
    """Hook for classifying transactions and appending postings during import.

    This hook maintains a registry of rules. When applied, it iterates through
    extracted transactions and evaluates them against the registered rules to
    automatically generate and append missing postings (e.g., categorizing an
    expense).
    """

    def __init__(self) -> None:
        """Initializes an empty rule registry for the classifier."""
        super().__init__()
        self._rules: list[Rule] = []

    @override
    def __call__(
        self, imported: list[Imported], existing: Directives
    ) -> list[Imported]:
        """Executes the classifier hook across a batch of imported files.

        Args:
            imported: A list of previously extracted import data.
            existing: Existing directives in the user's ledger.

        Returns:
            A new list of imported data with the classification rules applied
            to the directives.
        """
        return [
            (
                filename,
                self.apply(filename, directives, account, importer, existing),
                account,
                importer,
            )
            for filename, directives, account, importer in imported
        ]

    def wrap(self, importer: Importer) -> Importer:
        """Wraps an existing Beangulp importer with this classifier.

        Args:
            importer: The Beangulp importer to wrap.

        Returns:
            An _ImporterWrapper instance that intercepts the `extract` method
            to automatically apply classification rules.
        """
        return _ImporterWrapper(importer, self)

    def apply(
        self,
        filename: str,
        directives: Directives,
        account: Account,
        importer: Importer,
        existing: Directives,
    ) -> list[Directive]:
        """Applies registered rules to a list of extracted directives.

        Iterates through the directives. For each transaction, it evaluates
        the registered rules in order, appending any generated postings to the
        transaction.

        Args:
            filename: The name of the file being processed.
            directives: The directives extracted by the importer.
            account: The base account for the importer.
            importer: The Beangulp importer instance.
            existing: Existing directives for deduplication/context.

        Returns:
            A new list of directives with updated postings for matched transactions.
        """
        result: list[Directive] = []

        for directive in directives:
            if isinstance(directive, Transaction):
                new_postings = list(directive.postings)
                for rule in self._rules:
                    if not self._test_postings(new_postings):
                        break
                    postings_from_rule = list(
                        rule(
                            directive,
                            filename=filename,
                            account=account,
                            importer=importer,
                            existing=existing,
                        )
                    )
                    new_postings.extend(postings_from_rule)
                result.append(directive._replace(postings=new_postings))
            else:
                result.append(directive)
        return result

    def _test_postings(self, postings: list[Posting]) -> bool:
        """Determines if rule evaluation should continue for a transaction.

        Args:
            postings: The current list of postings for the transaction.

        Returns:
            True if the transaction only has a single posting (implying it is
            unbalanced and needs classification), False otherwise.
        """
        return len(postings) == 1

    def rule(self, rule: Rule) -> Rule:
        """Decorator to register a standard Rule.

        Args:
            rule: A callable matching the Rule protocol.

        Returns:
            The original rule, added to the classifier's registry.
        """
        self._rules.append(rule)
        return rule

    def simple_rule(self, simple_rule: SimpleRule) -> SimpleRule:
        """Decorator to register a SimpleRule.

        Automatically wraps the simple rule into a standard Rule that generates
        a single parameterless Posting for the returned account.

        Args:
            simple_rule: A callable matching the SimpleRule protocol.

        Returns:
            The original simple_rule.
        """

        def rule(
            txn: Transaction,
            **ctx: Unpack[RuleContext],  # noqa: ARG001 # pyright: ignore[reportUnusedParameter]
        ) -> Generator[Posting, None, None]:
            account = simple_rule(txn)
            if account is not None:
                yield Posting(
                    account=account,
                    units=None,
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None,
                )

        self._rules.append(rule)
        return simple_rule


@final
class _ImporterWrapper(Importer):
    """An internal wrapper for a Beangulp Importer that applies a classifier.

    This class proxies all standard importer methods to the underlying importer,
    but intercepts `extract` to pass the extracted directives through the
    classifier's `apply` method.
    """

    def __init__(self, importer: Importer, classifier: Classifier) -> None:
        """Initializes the wrapper with a base importer and a classifier.

        Args:
            importer: The Beangulp importer to be wrapped.
            classifier: The Classifier instance to apply during extraction.
        """
        self._importer = importer
        self._classifier = classifier

    @property
    @override
    def name(self) -> str:
        return self._importer.name

    @override
    def identify(self, filepath: str) -> bool:
        return self._importer.identify(filepath)

    @override
    def account(self, filepath: str) -> Account:
        return self._importer.account(filepath)

    @override
    def date(self, filepath: str) -> datetime.date | None:
        return self._importer.date(filepath)

    @override
    def filename(self, filepath: str) -> str | None:
        return self._importer.filename(filepath)

    @override
    def extract(self, filepath: str, existing: Directives) -> Directives:
        """Extracts directives using the base importer, then applies classification.

        Args:
            filepath: The path of the file being extracted.
            existing: Previously existing directives in the ledger.

        Returns:
            A list of directives modified by the classifier's rules.
        """
        entries = self._importer.extract(filepath, existing)
        return self._classifier.apply(
            filepath,
            entries,
            self.account(filepath),
            self._importer,
            existing,
        )

    @override
    def deduplicate(self, entries: Directives, existing: Directives) -> None:
        return self._importer.deduplicate(entries, existing)

    @override
    def sort(self, entries: Directives, reverse: bool = False) -> None:
        return self._importer.sort(entries, reverse)
