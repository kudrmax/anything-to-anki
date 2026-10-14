from __future__ import annotations

import json
import logging
import zlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert

from backend.domain.entities.token_data import TokenData
from backend.domain.ports.parse_cache import ParseCache
from backend.infrastructure.persistence.models import DocumentParseModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Rows deleted per statement: far below SQLite's limit of bound parameters.
DELETE_CHUNK_SIZE = 500

type _TokenRow = list[int | str | bool | list[int]]


class SqlaParseCache(ParseCache):
    """Parses in `document_parses`: tokens as a JSON list of their fields, zlib-compressed.
    A document keeps only the parse of the newest version; an unreadable parse is a miss.

    Every call is its own short transaction, so an analysis holds no lock on the database.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, document_hash: str, analyzer_version: str) -> list[TokenData] | None:
        with self._session_factory() as session:
            stored = session.get(DocumentParseModel, (document_hash, analyzer_version))
            data = stored.tokens if stored is not None else None
        if data is None:
            return None
        try:
            return [_token(row) for row in json.loads(zlib.decompress(data))]
        except (zlib.error, ValueError):
            logger.warning(
                "Parse cache: unreadable parse dropped (document_hash=%s, version=%s)",
                document_hash, analyzer_version, exc_info=True,
            )
            self._drop(document_hash, analyzer_version)
            return None

    def _drop(self, document_hash: str, analyzer_version: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(DocumentParseModel).where(
                DocumentParseModel.document_hash == document_hash,
                DocumentParseModel.analyzer_version == analyzer_version,
            ))
            session.commit()

    def put(self, document_hash: str, analyzer_version: str, tokens: list[TokenData]) -> None:
        data = zlib.compress(
            json.dumps([_row(token) for token in tokens], separators=(",", ":")).encode(),
        )
        with self._session_factory() as session:
            session.execute(delete(DocumentParseModel).where(
                DocumentParseModel.document_hash == document_hash,
                DocumentParseModel.analyzer_version != analyzer_version,
            ))
            session.execute(
                insert(DocumentParseModel)
                .values(
                    document_hash=document_hash,
                    analyzer_version=analyzer_version,
                    tokens=data,
                    created_at=datetime.now(tz=UTC),
                )
                .on_conflict_do_nothing()
            )
            session.commit()

    def keep_only(self, document_hashes: set[str]) -> int:
        with self._session_factory() as session:
            stale = sorted(
                set(session.scalars(select(DocumentParseModel.document_hash).distinct()))
                - document_hashes
            )
            for start in range(0, len(stale), DELETE_CHUNK_SIZE):
                session.execute(
                    delete(DocumentParseModel).where(
                        DocumentParseModel.document_hash.in_(
                            stale[start : start + DELETE_CHUNK_SIZE],
                        ),
                    )
                )
            session.commit()
        return len(stale)


def _row(token: TokenData) -> _TokenRow:
    return [
        token.index,
        token.text,
        token.lemma,
        token.pos,
        token.tag,
        token.head_index,
        list(token.children_indices),
        token.is_punct,
        token.is_stop,
        token.is_alpha,
        token.is_propn,
        token.sent_index,
        token.dep,
        token.whitespace_after,
        token.char_start,
    ]


# Any: a row of decoded JSON — its fields are written by _row in this order and types.
def _token(row: list[Any]) -> TokenData:
    return TokenData(
        index=row[0],
        text=row[1],
        lemma=row[2],
        pos=row[3],
        tag=row[4],
        head_index=row[5],
        children_indices=tuple(row[6]),
        is_punct=row[7],
        is_stop=row[8],
        is_alpha=row[9],
        is_propn=row[10],
        sent_index=row[11],
        dep=row[12],
        whitespace_after=row[13],
        char_start=row[14],
    )
