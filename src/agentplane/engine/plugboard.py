from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("agentplane.plug")


@dataclass
class AgentSlot:
    """A registered agent slot — can be plugged (active) or unplugged (locked out)."""

    agent_id: str
    tenant_id: str | None = None
    plugged: bool = True
    unplugged_at: float | None = None
    unplugged_reason: str = ""
    unplugged_by: str = ""
    tags: dict[str, str] = field(default_factory=dict)


class PlugBoard:
    """Runtime plug/unplug control for agents.

    When an agent is unplugged, ALL policy evaluations for that agent
    immediately raise PolicyBlocked — no rules are evaluated, no tools
    can be called, no access of any kind is permitted until re-plugged.

    This is a hard kill switch, not a graceful degradation. Use it when:
    - An agent runs out of budget and you want to cut all access
    - A security incident requires immediate lockout
    - An agent behaves anomalously and needs to be isolated
    - You want to take an agent offline without a redeploy

    Usage::

        board = PlugBoard()
        engine = PolicyEngine(plug_board=board)

        board.plug("billing-agent")          # active — normal operation
        board.unplug("billing-agent",        # hard lockout — all access cut
                     reason="budget exhausted",
                     by="ops-team")

        board.is_plugged("billing-agent")    # False
        board.plug("billing-agent")          # restore access
    """

    def __init__(self) -> None:
        self._slots: dict[str, AgentSlot] = {}

    def register(
        self,
        agent_id: str,
        tenant_id: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> AgentSlot:
        slot = AgentSlot(agent_id=agent_id, tenant_id=tenant_id, tags=tags or {})
        self._slots[agent_id] = slot
        logger.info("agentplane.plug registered agent=%s tenant=%s", agent_id, tenant_id)
        return slot

    def plug(self, agent_id: str) -> None:
        """Restore full access for an agent."""
        slot = self._slots.get(agent_id)
        if slot is None:
            slot = self.register(agent_id)
        slot.plugged = True
        slot.unplugged_at = None
        slot.unplugged_reason = ""
        slot.unplugged_by = ""
        logger.info("agentplane.plug plugged agent=%s", agent_id)

    def unplug(
        self,
        agent_id: str,
        reason: str = "",
        by: str = "",
    ) -> None:
        """Hard lockout — cut all access for an agent immediately."""
        slot = self._slots.get(agent_id)
        if slot is None:
            slot = self.register(agent_id)
        slot.plugged = False
        slot.unplugged_at = time.time()
        slot.unplugged_reason = reason
        slot.unplugged_by = by
        logger.warning(
            "agentplane.plug UNPLUGGED agent=%s reason=%r by=%s",
            agent_id, reason, by,
        )

    def is_plugged(self, agent_id: str) -> bool:
        slot = self._slots.get(agent_id)
        if slot is None:
            return True
        return slot.plugged

    def get_slot(self, agent_id: str) -> AgentSlot | None:
        return self._slots.get(agent_id)

    def unplug_all(self, tenant_id: str, reason: str = "", by: str = "") -> list[str]:
        """Unplug all agents for a given tenant — tenant-wide lockout."""
        unplugged = []
        for slot in self._slots.values():
            if slot.tenant_id == tenant_id and slot.plugged:
                self.unplug(slot.agent_id, reason=reason, by=by)
                unplugged.append(slot.agent_id)
        logger.warning(
            "agentplane.plug TENANT_LOCKOUT tenant=%s agents=%d reason=%r",
            tenant_id, len(unplugged), reason,
        )
        return unplugged

    def list_unplugged(self) -> list[AgentSlot]:
        return [s for s in self._slots.values() if not s.plugged]

    def list_all(self) -> list[AgentSlot]:
        return list(self._slots.values())
