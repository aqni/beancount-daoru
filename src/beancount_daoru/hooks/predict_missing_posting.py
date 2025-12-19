"""Hook for predicting missing postings in transactions using AI.

This module provides a sophisticated hook implementation that uses machine learning
to predict missing account postings in imported transactions based on historical data
and natural language processing of transaction descriptions.
"""

import asyncio
import re
from collections.abc import Mapping
from hashlib import blake2b
from pathlib import Path
from typing import TypedDict

import numpy as np
from beancount import (
    FLAG_OKAY,
    FLAG_WARNING,
    Account,
    Close,
    Directive,
    Directives,
    Meta,
    Open,
    Posting,
    Transaction,
    format_entry,
)
from diskcache import Cache
from openai import AsyncOpenAI
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import TypeAdapter
from tqdm import tqdm
from typing_extensions import NotRequired, override
from usearch.index import Index, Matches

from beancount_daoru.hook import Hook as BaseHook
from beancount_daoru.hook import Imported


class EmbeddingModelSettings(TypedDict):
    """Settings for the embedding model.

    Attributes:
        name: Model name identifier.
        base_url: Base URL for the model API.
        api_key: API key for authentication.
    """

    name: str
    base_url: str
    api_key: str


class _Encoder:
    def __init__(
        self,
        /,
        model_settings: EmbeddingModelSettings,
        cache_dir: Path,
    ) -> None:
        self.__model_name = model_settings.get("name")
        self.__embeddings_client = AsyncOpenAI(
            base_url=model_settings.get("base_url"),
            api_key=model_settings.get("api_key"),
        ).embeddings

        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_prefix = re.sub(r"[^a-zA-Z0-9]", "_", self.__model_name)
        cache_path = cache_dir / f"{_cache_prefix}.embeddings.diskcache"
        self.__cache = Cache(cache_path)
        self.__validator = TypeAdapter(list[float])

    async def encode(self, text: str) -> list[float]:
        if text in self.__cache:
            cached = self.__cache[text]  # pyright: ignore[reportUnknownVariableType]
            return self.__validator.validate_python(cached)

        response = await self.__embeddings_client.create(
            input=text,
            model=self.__model_name,
        )
        embedding = response.data[0].embedding

        self.__cache[text] = embedding
        return embedding


class _TransactionIndex:
    def __init__(
        self,
        encoder: _Encoder,
        ndim: int,
    ) -> None:
        self.__encoder = encoder
        self.__transaction_mapping: dict[int, Transaction] = {}
        self.__embedding_index = Index(ndim=ndim)

    async def add(self, transaction: Transaction) -> None:
        description = self._create_description(transaction)
        transaction_id = self._hash(description)
        if transaction_id not in self.__embedding_index:
            embedding = await self.__encoder.encode(description)
            _ = self.__embedding_index.add(  # pyright: ignore[reportUnknownVariableType]
                keys=transaction_id,
                vectors=np.array(embedding),
            )
            self.__transaction_mapping[transaction_id] = transaction

    def _create_description(self, transaction: Transaction) -> str:
        return format_entry(transaction)

    def _hash(self, text: str) -> int:
        hasher = blake2b(digest_size=8)
        hasher.update(text.encode("utf-8"))
        return int.from_bytes(hasher.digest(), "big")

    async def search(
        self, transaction: Transaction, topk: int
    ) -> list[tuple[Transaction, float]]:
        description = self._create_description(transaction)
        query_embedding = await self.__encoder.encode(description)

        matches = self.__embedding_index.search(
            vectors=np.array(query_embedding),
            count=topk,
        )

        if not isinstance(matches, Matches):
            raise TypeError(matches)

        return [
            (self.__transaction_mapping[match.key], float(match.distance))
            for match in matches
        ]


class _HistoryIndex:
    def __init__(
        self,
        encoder: _Encoder,
        ndim: int,
    ) -> None:
        self.__encoder = encoder
        self.__ndim = ndim
        self.__data_per_account: dict[Account, tuple[Meta, _TransactionIndex]] = {}

    async def add(self, directive: Directive) -> None:
        match directive:
            case Open():
                if directive.account in self.__data_per_account:
                    msg = f"open existing account: {directive}"
                    raise ValueError(msg)
                txn_index = _TransactionIndex(
                    encoder=self.__encoder,
                    ndim=self.__ndim,
                )
                self.__data_per_account[directive.account] = (directive.meta, txn_index)
            case Close():
                if directive.account not in self.__data_per_account:
                    msg = f"close non-existing account: {directive}"
                    raise ValueError(msg)
                del self.__data_per_account[directive.account]
            case Transaction() as txn:
                if self._check_transaction(txn):
                    for posting in txn.postings:
                        if posting.account not in self.__data_per_account:
                            msg = f"transaction with non-existing account: {txn}"
                            raise ValueError(msg)
                        other_postings = [p for p in txn.postings if p is not posting]
                        missing_posting_txn = txn._replace(postings=other_postings)
                        index = self.__data_per_account[posting.account][1]
                        await index.add(missing_posting_txn)
            case _:
                pass

    def _check_transaction(self, transaction: Transaction) -> bool:
        if transaction.flag is not None and transaction.flag != FLAG_OKAY:
            return False
        if len(transaction.postings) < 2:  # noqa: PLR2004
            return False
        for posting in transaction.postings:
            if posting.flag is not None and posting.flag != FLAG_OKAY:
                return False
        return True

    @property
    def accounts(self) -> Mapping[Account, Meta]:
        """Get available accounts with their metadata.

        Returns:
            Mapping of account names to metadata.
        """
        return {account: meta for account, (meta, _) in self.__data_per_account.items()}

    async def search(
        self, transaction: Transaction, n_few_shots: int
    ) -> list[tuple[Transaction, Account, float]]:
        candidates: list[tuple[Transaction, Account, float]] = []
        for account, (_, transaction_index) in self.__data_per_account.items():
            for target_transaction, distance in await transaction_index.search(
                transaction, 1
            ):
                candidates.append((target_transaction, account, distance))

        candidates.sort(key=lambda x: x[2])
        return candidates[:n_few_shots]


class ChatModelSettings(TypedDict):
    """Settings for the chat model.

    Attributes:
        name: Model name identifier.
        base_url: Base URL for the model API.
        api_key: API key for authentication.
    """

    name: str
    base_url: str
    api_key: str
    temperature: NotRequired[float]


class _ChatBot:
    def __init__(self, *, model_settings: ChatModelSettings) -> None:
        """Initialize the chat bot.

        Args:
            model_settings: Settings for the chat model.
        """
        self.__model_name = model_settings.get("name")
        self.__chat_client = AsyncOpenAI(
            base_url=model_settings.get("base_url"),
            api_key=model_settings.get("api_key"),
        ).chat.completions
        self.__temperature = model_settings.get("temperature", None)

    async def complete(
        self,
        user_prompt: str,
        /,
        system_prompt: str,
        response_format: JSONSchema,
    ) -> str:
        response = await self.__chat_client.create(
            model=self.__model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": response_format,
            },
            temperature=self.__temperature,
        )
        content = response.choices[0].message.content
        if content is None:
            msg = "content is None"
            raise ValueError(msg)
        return content


class _AccountPredictor:
    def __init__(
        self,
        /,
        chat_bot: _ChatBot,
        index: _HistoryIndex,
        extra_system_prompt: str,
    ) -> None:
        self.__chat_bot = chat_bot
        self.__index = index
        self.__extra_system_prompt = extra_system_prompt
        self.__validator = TypeAdapter[str | None](str | None)

    def _check_transaction(self, transaction: Transaction) -> bool:
        if transaction.flag is not None and transaction.flag != FLAG_OKAY:
            return False
        if len(transaction.postings) != 1:
            return False
        for posting in transaction.postings:
            if posting.flag is not None and posting.flag != FLAG_OKAY:
                return False
        return True

    @property
    def system_prompt(self) -> str:
        builder: list[str] = []

        role = (
            "ROLE: Beancount accounting expert. "
            "Your ONLY task is to predict missing accounts for transactions."
        )
        builder.append(role)

        rule = (
            "RULE: Return ONLY the exact account name if HIGH confident. "
            "Otherwise return 'NULL'. NO explanations."
        )
        builder.append(rule)
        builder.append("")

        # Beancount syntax
        builder.append("")
        builder.append("BEANCOUNT SYNTAX:")
        builder.append("YYYY-MM-DD [[Payee] Narration]")
        builder.append("  [Key: Value]")
        builder.append("  [Key: Value]")
        builder.append("  ...")
        builder.append("  Account Amount")
        builder.append("  Account Amount")
        builder.append("  ...")

        # Account structure rules
        builder.append("ACCOUNT HIERARCHY (MOST SPECIFIC FIRST):")
        builder.append("- Expenses:[Category]:[Subcategory] - For spending")
        builder.append("- Assets:[Account] - For money storage")
        builder.append("- Income:[Source] - For earnings")
        builder.append("- Liabilities:[Debt] - For debts")
        builder.append("- Equity:[Adjustment] - For net worth changes")
        builder.append("")

        # Classification logic
        builder.append("")
        builder.append("CLASSIFICATION LOGIC:")
        builder.append("- Analyze Payee, Narration and key-value Metadata for clues")
        builder.append("- Match expense types to most specific sub-account available")
        builder.append("- Prefer historical patterns over generic accounts")

        # other prompt
        if self.__extra_system_prompt:
            builder.append("")
            builder.append("ADDITIONAL INSTRUCTIONS:")
            builder.append(self.__extra_system_prompt)

        # Available accounts with metadata
        builder.append("")
        builder.append("AVAILABLE ACCOUNTS WITH DESCRIPTION:")
        for account, meta in self.__index.accounts.items():
            builder.append(f"- {account}: {meta.get('desc', 'No description')}")

        return "\n".join(builder)

    async def user_prompt(self, transaction: Transaction) -> str:
        similar_examples = await self.__index.search(transaction, 3)

        builder: list[str] = []

        builder.append("PREDICT MISSING ACCOUNT FOR THIS TRANSACTION:")
        builder.append(format_entry(transaction).strip())

        if similar_examples:
            builder.append(f"HISTORICAL MATCHES ({len(similar_examples)}):")
            for idx, (txn, account, distance) in enumerate(similar_examples, 1):
                sim = 1 / (1 + distance)
                builder.append("")
                builder.append(
                    f"Example #{idx} ({sim:.0%} match) is predictted as {account!r}:"
                )
                builder.append(format_entry(txn).strip())
        else:
            builder.append("HISTORICAL MATCHES: not found")

        return "\n".join(builder)

    @property
    def response_format(self) -> JSONSchema:
        return {
            "name": "predictted account or null",
            "strict": True,
            "schema": {
                "type": ["string", "null"],
                "enum": [*list(self.__index.accounts.keys()), None],
            },
        }

    async def predict(self, transaction: Transaction) -> Account | None:
        if not self._check_transaction(transaction):
            return None
        user_prompt = await self.user_prompt(transaction)
        response = await self.__chat_bot.complete(
            user_prompt,
            system_prompt=self.system_prompt,
            response_format=self.response_format,
        )

        return self.__validator.validate_json(response)


class Hook(BaseHook):
    """Hook that predicts missing accounts in transactions.

    Uses llm to analyze transaction context and historical patterns
    to predict the most appropriate account for missing postings.

    This hook implements a sophisticated approach to automatically classify
    transaction postings using Large Language Models (LLMs) and similarity search.
    The underlying technique involves:

    1. **Embedding Vectorization**: Using an embedding model to convert transaction
       descriptions into vector representations that capture semantic meaning.

    2. **Similarity Retrieval**: Performing similarity search in the existing ledger
       to find historically similar transactions based on their vector representations.

    3. **LLM Classification**: Leveraging a large language model to make intelligent
       classification decisions by combining historical transaction patterns with
       contextual information from the current transaction.

    4. **Caching Mechanism**: Caching vectors on disk to save computational overhead
       from repeated calculations, improving performance for subsequent runs.
    """

    def __init__(
        self,
        *,
        chat_model_settings: ChatModelSettings,
        embed_model_settings: EmbeddingModelSettings,
        cache_dir: Path | None = None,
        extra_system_prompt: str = "",
    ) -> None:
        """Initialize the account prediction hook.

        Args:
            chat_model_settings: Settings for the chat model.
            embed_model_settings: Settings for the embedding model.
            cache_dir: Path to cache indices and embeddings.
            extra_system_prompt: Additional instructions for the LLM.
        """
        if cache_dir is None:
            cache_dir = Path(Path.cwd(), ".cache", *__name__.split("."))
        self.__chat_bot = _ChatBot(model_settings=chat_model_settings)
        self.__encoder = _Encoder(
            model_settings=embed_model_settings,
            cache_dir=cache_dir,
        )
        self.__extra_system_prompt = extra_system_prompt

    @override
    def __call__(
        self, imported: list[Imported], existing: Directives
    ) -> list[Imported]:
        return asyncio.run(self._transform(imported, existing))

    async def _transform(
        self, imported: list[Imported], existing: Directives
    ) -> list[Imported]:
        measurement_embedding = await self.__encoder.encode("for test")

        index = _HistoryIndex(
            encoder=self.__encoder,
            ndim=len(measurement_embedding),
        )

        for directive in tqdm(
            existing,
            desc="indexing existing directives",
            leave=False,
        ):
            await index.add(directive)

        predictor = _AccountPredictor(
            chat_bot=self.__chat_bot,
            index=index,
            extra_system_prompt=self.__extra_system_prompt,
        )

        result: list[Imported] = []
        for filename, directives, account, importer in tqdm(
            imported,
            desc="predicting imported files",
            leave=False,
        ):
            processed = await self._process_one_file(directives, predictor)
            result.append((filename, processed, account, importer))
        return result

    async def _process_one_file(
        self, directives: Directives, predictor: _AccountPredictor
    ) -> Directives:
        tasks = [
            self._process_with_index(index, directive, predictor)
            for index, directive in enumerate(directives)
        ]

        results_with_index: list[tuple[int, Directive]] = []
        for future in tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc="predicting imported directives of current file",
            leave=False,
        ):
            index, processed_directive = await future
            results_with_index.append((index, processed_directive))

        results_with_index.sort(key=lambda x: x[0])
        return [x[1] for x in results_with_index]

    async def _process_with_index(
        self, index: int, directive: Directive, predictor: _AccountPredictor
    ) -> tuple[int, Directive]:
        result = await self._process_directive(directive, predictor)
        return index, result

    async def _process_directive(
        self, directive: Directive, predictor: _AccountPredictor
    ) -> Directive:
        if not isinstance(directive, Transaction):
            return directive

        predicted_account = await predictor.predict(directive)
        if predicted_account is None:
            return directive

        return directive._replace(
            postings=[
                *directive.postings,
                Posting(predicted_account, None, None, None, FLAG_WARNING, None),
            ]
        )
