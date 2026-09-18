"""Unit and integration tests for the retrieval layer using standard unittest."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.retrieval import (
    KBArticle,
    KBRetriever,
    RetrievalResult,
    TicketRetriever,
    UnifiedRetriever,
)
from src.storage.store import Store


class TestRetrievalLayer(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_app.db"
        self.store = Store(db_path=self.db_path, seed=True)
        self.kb_retriever = KBRetriever(data_path="data/knowledge_base.json")
        self.ticket_retriever = TicketRetriever(store=self.store)
        self.unified_retriever = UnifiedRetriever(
            kb_retriever=self.kb_retriever, ticket_retriever=self.ticket_retriever
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    # ----------------------------------------------------------------------- #
    # KBRetriever Tests
    # ----------------------------------------------------------------------- #
    def test_load_all_articles(self) -> None:
        articles = self.kb_retriever.list_all()
        self.assertEqual(len(articles), 11)
        ids = {a.id for a in articles}
        self.assertIn("KB-01", ids)
        self.assertIn("KB-07", ids)
        self.assertIn("KB-09", ids)
        self.assertIn("Asset Management Policy", ids)

    def test_get_by_id(self) -> None:
        kb01 = self.kb_retriever.get("kb-01")
        self.assertIsNotNone(kb01)
        self.assertEqual(kb01.id, "KB-01")
        self.assertIn("Password", kb01.title)

        asset = self.kb_retriever.get("Asset Management Policy")
        self.assertIsNotNone(asset)
        self.assertIn("4-year refresh cycle", asset.content)

    def test_get_nonexistent_id(self) -> None:
        self.assertIsNone(self.kb_retriever.get("KB-999"))

    def test_domain_queries_match_correct_policies(self) -> None:
        cases = [
            ("I forgot my password and cannot log in, account locked out", "KB-01"),
            ("Can I get Wi-Fi access for a guest visiting our office tomorrow?", "KB-07"),
            ("Suspicious phishing email asking for employee login", "KB-09"),
            ("Need to install non-catalog software tool", "KB-04"),
            ("My VPN credentials expired and stopped connecting", "KB-02"),
            ("Printer on floor 3 is stuck with a paper jam", "KB-05"),
            ("Default mailbox quota is full, need more storage space", "KB-06"),
            ("Working from home 4 days a week, need monitor and chair", "KB-10"),
            ("Expense tool login access", "KB-08"),
            ("Laptop is 3.5 years old and completely dead", "KB-03"),
        ]
        for query, expected_id in cases:
            with self.subTest(query=query, expected_id=expected_id):
                results = self.kb_retriever.search(query, top_k=3)
                self.assertGreater(len(results), 0)
                top_ids = [r.source_id for r in results]
                self.assertIn(expected_id, top_ids)
                self.assertEqual(results[0].source_id, expected_id)
                self.assertEqual(results[0].citation, f"[{expected_id}]")
                self.assertGreater(results[0].score, 0.0)

    def test_empty_query(self) -> None:
        self.assertEqual(self.kb_retriever.search(""), [])
        self.assertEqual(self.kb_retriever.search("   "), [])

    # ----------------------------------------------------------------------- #
    # TicketRetriever Tests
    # ----------------------------------------------------------------------- #
    def test_ticket_retriever_seeded(self) -> None:
        t = self.ticket_retriever.get("TK-1042")
        self.assertIsNotNone(t)
        self.assertEqual(t.source_id, "TK-1042")
        self.assertIn("VPN", t.title)
        self.assertTrue(t.is_closed)
        self.assertFalse(t.is_active)

    def test_active_vs_closed_filtering(self) -> None:
        active_results = self.ticket_retriever.search("laptop", top_k=10, active_only=True)
        for r in active_results:
            self.assertTrue(r.is_active)
            self.assertFalse(r.is_closed)

    def test_search_by_employee_name(self) -> None:
        results = self.ticket_retriever.search("R. Verma", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].source_id, "TK-1042")

    def test_list_precedents(self) -> None:
        precedents = self.ticket_retriever.list_precedents(top_k=5)
        self.assertGreater(len(precedents), 0)
        for p in precedents:
            self.assertTrue(p.is_closed)

    # ----------------------------------------------------------------------- #
    # UnifiedRetriever Tests
    # ----------------------------------------------------------------------- #
    def test_combined_search(self) -> None:
        query = "My VPN credentials expired"
        results = self.unified_retriever.search(query, kb_k=2, ticket_k=2)
        self.assertGreaterEqual(len(results), 2)

        kb_ids = [r.source_id for r in results if r.is_kb]
        ticket_ids = [r.source_id for r in results if r.is_ticket]

        self.assertIn("KB-02", kb_ids)
        self.assertIn("TK-1042", ticket_ids)

    def test_get_by_id(self) -> None:
        kb = self.unified_retriever.get_by_id("KB-07")
        self.assertIsNotNone(kb)
        self.assertEqual(kb.source_id, "KB-07")
        self.assertTrue(kb.is_kb)

        tk = self.unified_retriever.get_by_id("TK-1048")
        self.assertIsNotNone(tk)
        self.assertEqual(tk.source_id, "TK-1048")
        self.assertTrue(tk.is_ticket)

    def test_format_context(self) -> None:
        results = self.unified_retriever.search("Phishing email reported", kb_k=1, ticket_k=1)
        formatted = self.unified_retriever.format_context(results)

        self.assertIn("### Applicable Knowledge Base Policies", formatted)
        self.assertIn("[KB-09]", formatted)
        self.assertIn("### Relevant Ticket History & Precedents", formatted)
        self.assertIn("[TK-1048]", formatted)

    def test_format_context_empty(self) -> None:
        self.assertIn("No relevant", self.unified_retriever.format_context([]))


if __name__ == "__main__":
    unittest.main()
