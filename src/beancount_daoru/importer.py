"""Main importer module for converting extracted records to Beancount entries.

This module provides the core importer functionality that bridges extracted
financial records with the Beancount accounting system. It handles conversion
of records to Beancount transactions, account mapping, currency conversion,
and integration with the Beangulp framework.
"""

import datetime
from collections.abc import Iterable, Iterator, Mapping
from decimal import Decimal
from functools import lru_cache
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from re import Pattern
from typing import NamedTuple, Protocol

import beancount
import beangulp
from beangulp.extract import DUPLICATE
from typing_extensions import TypedDict, Unpack, override

from beancount_daoru.reader import Reader


class Extra(NamedTuple):
    """Extra transaction metadata.

    Additional metadata associated with a financial transaction that doesn't
    fit into the standard fields of a transaction. These fields provide
    additional context for categorization, reconciliation, and reporting.

    Attributes:
        time: Time of the transaction.
        dc: Debit/Credit indicator (e.g., "收入" for income, "支出" for expense).
        type: Transaction type or category.
        payee_account: Account information of the counterparty.
        status: Status of the transaction (e.g., successful, pending, failed).
        place: Location or place of the transaction.
        remarks: Additional remarks or notes about the transaction.
    """

    time: datetime.time | None = None
    dc: str | None = None
    type: str | None = None
    payee_account: str | None = None
    status: str | None = None
    place: str | None = None
    remarks: str | None = None


class Posting(NamedTuple):
    """A posting in a Beancount transaction.

    Represents a single leg of a transaction with an amount, account, and optional
    currency information. In double-entry bookkeeping, a transaction typically
    consists of two or more postings whose amounts sum to zero.

    Attributes:
        amount: The monetary amount of the posting.
        account: The account affected by this posting.
        currency: The currency of the amount (optional, may be inferred from context).
    """

    amount: Decimal
    account: str | None = None
    currency: str | None = None


class Transaction(NamedTuple):
    """A financial transaction with Beancount-compatible structure.

    Represents a complete financial transaction with date, payee, narration,
    and one or more postings. This structure serves as an intermediate
    representation between source data formats and Beancount entries.

    Attributes:
        date: Date of the transaction.
        extra: Additional metadata about the transaction.
        payee: The entity the transaction is with (e.g., vendor, recipient).
        narration: Description or memo of the transaction.
        postings: The postings that make up this transaction.
        balance: Optional balance information for account reconciliation.
    """

    date: datetime.date
    extra: Extra
    payee: str | None = None
    narration: str | None = None
    postings: Iterable[Posting] = ()
    balance: Posting | None = None


class Metadata(NamedTuple):
    """Metadata extracted from a financial document.

    Contains information about the source document such as account identifier
    and statement period. This metadata is used to properly categorize and
    process transactions from the document.

    Attributes:
        account: Account identifier extracted from the document.
        date: Date associated with the document (often statement date).
        currency: Default currency for transactions in the document.
    """

    account: str | None
    date: datetime.date | None
    currency: str | None = None


class ParserError(Exception):
    """Exception raised when parsing fails."""

    def __init__(self, *fields: str) -> None:
        """Initialize ParserError exception.

        Args:
            *fields: Tuple of unsupported field names that caused the parsing failure.
        """
        msg = f"unsupported value combination of fields: {fields!r}"
        super().__init__(msg)


class Parser(Protocol):
    """Interface for parsing financial transaction records.

    Defines the protocol that all parser implementations must follow to convert
    source transaction records into Beancount-compatible structures. Each specific
    importer (Alipay, WeChat, etc.) must implement this protocol.
    """

    @property
    def reversed(self) -> bool:
        """Indicates if the source records are in reverse chronological order.

        Returns:
            True if records are in reverse chronological order, False otherwise.
        """
        return False

    def extract_metadata(self, texts: Iterator[str]) -> Metadata:
        """Extract metadata from text iterator.

        Parses the input text to extract document-level metadata such as account
        identifier and statement date. This information is used to properly
        categorize and process transactions from the document.

        Args:
            texts: Iterator over lines of text from the source document.

        Returns:
            Metadata object containing extracted information.
        """
        ...

    def parse(self, record: dict[str, str]) -> Transaction:
        """Parse a single transaction record into a Beancount-compatible structure.

        Converts a dictionary representation of a single transaction record from
        the source format into a standardized Transaction object that can be
        processed into Beancount entries.

        Args:
            record: Dictionary representing a single transaction record with
                keys and values as they appear in the source document.

        Raises:
            ParserError: If the record contains unsupported value combinations.

        Returns:
            Transaction object with the parsed data in a Beancount-compatible format.
        """
        ...


class ImporterKwargs(TypedDict):
    """Configuration parameters for the Importer class.

    Attributes:
        account_mapping: Nested dict mapping source account info and transaction types
            to Beancount accounts. Structure:
            - 1st-level key: Source account name (e.g., payment app user account)
            - 2nd-level key: Payment method (e.g., "余额", "花呗")
            - Special key None: Default archival folder account for the source

    Example:
                {
                    "user@example.com": {
                        None: "Assets:Alipay",  # Archival folder account
                        "余额": "Assets:Alipay:Balance",
                        "花呗": "Liabilities:Huabei"
                    }
                }
            `account_mapping["user@example.com"][None]` maps to the "Assets/Alipay"
            folder used for archival purposes.

        currency_mapping: Mapping of source currency identifiers to Beancount currency
            codes (e.g., {"RMB": "CNY", "USD": "USD"}).
    """

    account_mapping: Mapping[str | None, Mapping[str | None, beancount.Account]]
    currency_mapping: Mapping[str | None, beancount.Currency]


class Importer(beangulp.Importer):
    """Main importer class that integrates with Beangulp.

    This class implements the Beangulp Importer interface and orchestrates
    the conversion of financial documents to Beancount entries.
    """

    def __init__(
        self,
        filename: Pattern[str],
        reader: Reader,
        parser: Parser,
        /,
        **kwargs: Unpack[ImporterKwargs],
    ) -> None:
        """Initialize the Importer.

        Sets up the importer with filename pattern matching, reader for extracting
        records from files, parser for converting records to transactions, and
        mappings for account and currency translation.

        Args:
            filename: Pattern to match against filenames for identification.
            reader: Reader instance for extracting records from files.
            parser: Parser instance for converting records to transactions.
            **kwargs: Additional configuration including account and currency mappings.
        """
        self.__filename_pattern = filename
        self.__reader = reader
        self.__parser = parser
        self.__account_mappings = kwargs["account_mapping"]
        self.__currency_mapping = kwargs["currency_mapping"]

    @override
    def identify(self, filepath: str) -> bool:
        return self.__filename_pattern.fullmatch(Path(filepath).name) is not None

    @override
    def account(self, filepath: str) -> str:
        return self._analyse_account(self._cached_metadata(filepath))

    @override
    def date(self, filepath: str) -> datetime.date | None:
        return self._cached_metadata(filepath).date

    @override
    def filename(self, filepath: str) -> str:
        return Path(filepath).name

    @override
    def extract(
        self,
        filepath: str,
        existing: beancount.Directives,
    ) -> beancount.Directives:
        metadata = self._cached_metadata(filepath)
        directives: list[beancount.Directive] = []
        for index, record in enumerate(self.__reader.read_records(Path(filepath))):
            directives.extend(self._extract_record(filepath, index, metadata, record))
        return directives

    @override
    def deduplicate(
        self, entries: beancount.Directives, existing: beancount.Directives
    ) -> None:
        balances = sorted(
            (e for e in entries if isinstance(e, beancount.Balance)),
            key=attrgetter("date"),
        )
        max_balance_per_date = {
            date: max(group, key=lambda e: self._lineno_key(e.meta["lineno"]))  # pyright: ignore[reportAny]
            for date, group in groupby(balances, key=attrgetter("date"))  # pyright: ignore[reportAny]
        }

        for balance in balances:
            if (target := max_balance_per_date[balance.date]) != balance:
                balance.meta[DUPLICATE] = target

    @override
    def sort(self, entries: beancount.Directives, reverse: bool = False) -> None:
        def sort_key(entry: beancount.Directive) -> tuple[int, int]:
            lineno = entry.meta["lineno"]  # pyright: ignore[reportAny]
            return (
                self._lineno_key(lineno),  # pyright: ignore[reportAny]
                0 if isinstance(entry, beancount.Transaction) else 1,
            )

        entries.sort(key=sort_key, reverse=reverse)

    def _lineno_key(self, lineno: int) -> int:
        return -lineno if self.__parser.reversed else lineno

    @lru_cache(maxsize=1)  # noqa: B019
    def _cached_metadata(self, filepath: str) -> Metadata:
        return self.__parser.extract_metadata(
            self.__reader.read_captions(Path(filepath))
        )

    def _extract_record(
        self,
        filepath: str,
        lineno: int,
        metadata: Metadata,
        record: dict[str, str],
    ) -> Iterator[beancount.Directive]:
        try:
            transaction = self.__parser.parse(record)
        except ParserError as e:
            yield beancount.Transaction(
                meta=self._build_meta(
                    filepath,
                    lineno,
                    record,
                    error=f"{e} @ {record!r}",
                ),
                date=datetime.date(1970, 1, 1),
                flag=beancount.FLAG_WARNING,
                payee=None,
                narration=None,
                tags=frozenset(),
                links=frozenset(),
                postings=[],
            )
            return

        yield beancount.Transaction(
            meta=self._build_meta(
                filepath,
                lineno,
                record,
                **transaction.extra._asdict(),  # pyright: ignore[reportAny]
            ),
            date=transaction.date,
            flag=beancount.FLAG_OKAY,
            payee=transaction.payee,
            narration=transaction.narration,
            tags=frozenset(),
            links=frozenset(),
            postings=[
                beancount.Posting(
                    account=self._analyse_account(metadata, posting),
                    units=self._analyse_amount(metadata, posting),
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None,
                )
                for posting in transaction.postings
            ],
        )

        if transaction.balance is not None:
            yield beancount.Balance(
                meta=self._build_meta(filepath, lineno, record),
                date=transaction.date + datetime.timedelta(days=1),
                account=self._analyse_account(metadata, transaction.balance),
                amount=self._analyse_amount(metadata, transaction.balance),
                tolerance=None,
                diff_amount=None,
            )

    def _build_meta(
        self,
        filepath: str,
        lineno: int,
        record: dict[str, str],
        **meta: object | None,
    ) -> dict[str, str]:
        return beancount.new_metadata(
            self.filename(filepath),
            lineno,
            kvlist={
                key: str(value)
                for key, value in {
                    "__source__": str(record),
                    **meta,
                }.items()
                if value is not None
            },
        )

    def _analyse_account(
        self,
        metadata: Metadata,
        posting: Posting | None = None,
    ) -> beancount.Account:
        if metadata.account not in self.__account_mappings:
            msg = f"account is not mapped: {metadata.account!r}"
            raise KeyError(msg)
        account_submapping = self.__account_mappings[metadata.account]

        posting_account = posting.account if posting is not None else None
        if posting_account not in account_submapping:
            msg = f"account of {metadata.account!r} is not mapped: {posting_account!r}"
            raise KeyError(msg)
        return account_submapping[posting_account]

    def _analyse_amount(self, metadata: Metadata, posting: Posting) -> beancount.Amount:
        currency_name = posting.currency
        if currency_name is None:
            currency_name = metadata.currency

        if currency_name not in self.__currency_mapping:
            msg = f"currency name '{currency_name}' is not mapped"
            raise KeyError(msg)
        currency = self.__currency_mapping[currency_name]
        return beancount.Amount(number=posting.amount, currency=currency)
