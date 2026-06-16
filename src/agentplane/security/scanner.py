from __future__ import annotations

import re

from agentplane.core.context import PolicyContext
from agentplane.core.rule import BlockingRule, NonBlockingRule, RuleResult

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"<script|javascript:", re.IGNORECASE),
    re.compile(r"\[\[(?:system|user|assistant)\]\]", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior)\s+", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+", re.IGNORECASE),
    re.compile(r"pretend\s+(?:you\s+are|to\s+be)", re.IGNORECASE),
]

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("phone", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


class InjectionScanRule(BlockingRule):
    """Block if prompt injection patterns are detected in query or tool inputs."""

    name = "injection_scan"

    def __init__(self, on_detection: str = "block", priority: int = 300) -> None:
        self.on_detection = on_detection
        self.priority = priority

    async def evaluate(self, ctx: PolicyContext) -> RuleResult:
        targets: list[str] = []
        if ctx.tool_inputs:
            targets.extend(str(v) for v in ctx.tool_inputs.values())
        if ctx.llm_response:
            targets.append(ctx.llm_response)
        if ctx.metadata.get("query"):
            targets.append(str(ctx.metadata["query"]))

        for text in targets:
            for pattern in INJECTION_PATTERNS:
                if pattern.search(text):
                    reason = f"prompt injection detected: {pattern.pattern[:50]!r}"
                    if self.on_detection == "escalate":
                        return RuleResult.escalate(2, reason)
                    return RuleResult.block(reason)
        return RuleResult.allow()


class PIIScanRule(NonBlockingRule):
    """Non-blocking PII detection — logs detected PII types without blocking."""

    name = "pii_scan"

    def __init__(self, fields: list[str] | None = None) -> None:
        self.fields = fields

    async def evaluate(self, ctx: PolicyContext) -> None:
        import logging
        log = logging.getLogger("agentplane.security.pii")
        targets: list[tuple[str, str]] = []
        for k, v in ctx.tool_inputs.items():
            targets.append((k, str(v)))
        if ctx.llm_response:
            targets.append(("llm_response", ctx.llm_response))

        for field, text in targets:
            if self.fields and field not in self.fields:
                continue
            for pii_type, pattern in PII_PATTERNS:
                if pattern.search(text):
                    log.warning(
                        "agentplane.pii detected agent=%s tenant=%s field=%s type=%s",
                        ctx.agent_id, ctx.tenant_id, field, pii_type,
                    )
