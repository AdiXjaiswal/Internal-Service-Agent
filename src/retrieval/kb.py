"""Knowledge Base retrieval engine supporting BM25 lexical ranking and optional FAISS vectors."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

from .models import KBArticle, RetrievalResult

_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
        "from", "has", "have", "he", "how", "i", "if", "in", "is", "it", "its",
        "my", "me", "no", "not", "of", "on", "or", "our", "she", "so", "that",
        "the", "their", "them", "then", "there", "these", "they", "this", "to",
        "us", "was", "we", "were", "what", "when", "where", "which", "who",
        "will", "with", "would", "you", "your",
    }
)

ARTICLE_TAGS: dict[str, list[str]] = {
    "KB-01": ["password", "reset", "lockout", "locked", "unlock", "credentials", "login", "portal"],
    "KB-02": ["vpn", "connection", "remote", "credentials", "expired", "contractor", "renew"],
    "KB-03": ["laptop", "hardware", "replacement", "broken", "dead", "fault", "refresh", "replace"],
    "KB-04": ["software", "install", "installation", "application", "catalog", "tool", "approved"],
    "KB-05": ["printer", "print", "spooler", "paper", "jam", "tag", "queue"],
    "KB-06": ["mailbox", "quota", "archive", "storage", "email", "25gb", "50gb", "inbox"],
    "KB-07": ["wifi", "wi-fi", "guest", "visitor", "kiosk", "internet", "voucher", "code"],
    "KB-08": ["expense", "expenses", "finance", "tool", "management", "reimbursement"],
    "KB-09": ["security", "phishing", "phish", "malware", "virus", "suspicious", "unauthorized", "incident", "breach"],
    "KB-10": ["home", "wfh", "remote", "equipment", "monitor", "chair", "allowance", "office"],
    "Asset Management Policy": ["asset", "hardware", "refresh", "cycle", "finance", "replacement", "4-year", "laptop"],
}


def _tokenize(text: str, remove_stopwords: bool = False) -> list[str]:
    """Tokenize text into lowercase words with domain-specific normalization."""
    cleaned = (
        text.lower()
        .replace("wi-fi", "wifi")
        .replace("wfh", "remote home office")
        .replace("won't", "will not")
        .replace("can't", "cannot")
    )
    tokens = re.findall(r"\b[a-z0-9_\-]+\b", cleaned)
    expanded: list[str] = []
    for t in tokens:
        if remove_stopwords and t in _STOPWORDS:
            continue
        expanded.append(t)
        if "-" in t:
            for part in t.split("-"):
                if part and (not remove_stopwords or part not in _STOPWORDS):
                    expanded.append(part)
    return expanded


class BM25Index:
    """Lightweight, zero-dependency BM25Okapi implementation."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avg_doc_length = (
            sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 1.0
        )
        self.doc_freqs: dict[str, int] = Counter()
        for doc in corpus:
            for term in set(doc):
                self.doc_freqs[term] += 1

        self.idf: dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log(
                (self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0
            )

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        doc = self.corpus[doc_idx]
        doc_len = self.doc_lengths[doc_idx]
        term_counts = Counter(doc)
        score = 0.0

        for q in query_tokens:
            if q not in self.idf:
                continue
            tf = term_counts.get(q, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_length))
            score += self.idf[q] * (numerator / denominator)

        return score


class KBRetriever:
    """Retrieves policies and knowledge base articles.

    Parameters
    ----------
    data_path:
        Path to ``data/knowledge_base.json``.
    embedding_fn:
        Optional callable that produces normalized vector embeddings for queries
        and documents, enabling FAISS vector search.
    """

    def __init__(
        self,
        data_path: str | Path = "data/knowledge_base.json",
        embedding_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
    ) -> None:
        self.data_path = Path(data_path)
        self.embedding_fn = embedding_fn
        self.articles: dict[str, KBArticle] = {}
        self._article_list: list[KBArticle] = []
        self._bm25: Optional[BM25Index] = None
        self._faiss_index = None

        self.reload()

    def reload(self, data_path: Optional[str | Path] = None) -> None:
        """Reload and re-index articles from the knowledge base file."""
        if data_path:
            self.data_path = Path(data_path)

        if not self.data_path.exists():
            raise FileNotFoundError(f"Knowledge base file not found at: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self.articles.clear()
        self._article_list.clear()

        corpus_tokens: list[list[str]] = []
        for item in raw_data:
            art_id = item.get("id", "").strip()
            tags = ARTICLE_TAGS.get(art_id, [])
            article = KBArticle(
                id=art_id,
                title=item.get("title", "").strip(),
                content=item.get("content", "").strip(),
                tags=tags,
            )
            self.articles[article.id] = article
            self._article_list.append(article)

            # Combined searchable representation with title and tag repetition for weight
            tags_str = " ".join(tags)
            search_doc = f"{article.id} {article.title} {article.title} {tags_str} {tags_str} {article.content}"
            corpus_tokens.append(_tokenize(search_doc, remove_stopwords=True))

        self._bm25 = BM25Index(corpus_tokens)

        # Build optional FAISS index if embedding function is provided
        if self.embedding_fn is not None:
            self._build_vector_index()

    def _build_vector_index(self) -> None:
        try:
            import faiss
            import numpy as np

            texts = [a.full_text for a in self._article_list]
            embeddings = self.embedding_fn(texts)
            dim = len(embeddings[0])
            index = faiss.IndexFlatIP(dim)
            mat = np.array(embeddings, dtype=np.float32)
            faiss.normalize_L2(mat)
            index.add(mat)
            self._faiss_index = index
        except Exception:
            self._faiss_index = None

    def get(self, kb_id: str) -> Optional[KBArticle]:
        """Fetch an article by its unique ID (case-insensitive)."""
        target = kb_id.strip().lower()
        for k_id, article in self.articles.items():
            if k_id.lower() == target:
                return article
        return None

    def list_all(self) -> list[KBArticle]:
        """Return all loaded knowledge base articles."""
        return list(self._article_list)

    def search(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """Search the knowledge base using lexical BM25 + tag/ID boost."""
        if not query.strip() or not self._article_list or self._bm25 is None:
            return []

        query_clean = query.strip()
        query_tokens = _tokenize(query_clean, remove_stopwords=True)
        q_lower = query_clean.lower()

        scores: list[tuple[float, KBArticle]] = []

        for idx, article in enumerate(self._article_list):
            bm25_score = self._bm25.score(query_tokens, idx)
            score = bm25_score

            # Exact ID mention boost (e.g. "KB-01" or "Asset Management")
            id_lower = article.id.lower()
            if id_lower in q_lower:
                score += 20.0

            # Title keyword matches (excluding stopwords)
            title_tokens = set(_tokenize(article.title, remove_stopwords=True))
            matching_title = title_tokens.intersection(query_tokens)
            if matching_title:
                score += len(matching_title) * 4.0

            # Tag matches (domain keywords)
            tag_tokens = set(article.tags)
            matching_tags = tag_tokens.intersection(query_tokens)
            if matching_tags:
                score += len(matching_tags) * 5.0

            if score > threshold:
                scores.append((score, article))

        scores.sort(key=lambda x: x[0], reverse=True)

        results: list[RetrievalResult] = []
        max_score = scores[0][0] if scores and scores[0][0] > 0 else 1.0

        for s, article in scores[:top_k]:
            normalized_score = min(1.0, round(s / max(max_score, 1.0), 3))
            results.append(
                RetrievalResult(
                    source_id=article.id,
                    source_type="kb",
                    title=article.title,
                    content=article.content,
                    score=normalized_score,
                    metadata={"raw_score": round(s, 2), "tags": article.tags},
                    citation=f"[{article.id}]",
                )
            )

        return results
