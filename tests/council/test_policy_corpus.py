"""Policy regression corpus: every entry must be rejected with its code."""

from __future__ import annotations

import json
from pathlib import Path

from wifi_council.config import CouncilConfig
from wifi_council.policy import PolicyArbiter

CORPUS = Path(__file__).with_name("policy_corpus.json")


def test_policy_corpus_rejects_every_case() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    arbiter = PolicyArbiter(CouncilConfig())
    for case in corpus["cases"]:
        problems = arbiter.scan_text(case["text"])
        codes = [code for code, _detail in problems]
        assert case["reason_code"] in codes, (
            f"expected {case['reason_code']} for {case['text']!r}, got {codes}"
        )


def test_policy_corpus_allows_negated_proxy_language() -> None:
    """Correct proxy wording must never be flagged by the corpus rules."""
    arbiter = PolicyArbiter(CouncilConfig())
    allowed = [
        "非影像、非人数、非米制距离",
        "相对纵深代理,不提供米制距离",
        "遮挡/空间占用代理,不是真实墙体密度或人数",
        "动态扰动与 moving 状态一致",
    ]
    for text in allowed:
        assert arbiter.scan_text(text) == [], f"false positive: {text!r}"
