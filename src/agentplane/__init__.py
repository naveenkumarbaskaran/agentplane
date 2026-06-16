from agentplane.audit.trail import AuditTrail
from agentplane.core.context import PolicyContext
from agentplane.core.exceptions import (
    AgentplaneError,
    EscalationError,
    PolicyBlocked,
    PolicyConflict,
    PolicyDegraded,
    PolicyNotFound,
    PolicyVersionError,
    SyncError,
)
from agentplane.core.policy import Policy
from agentplane.core.rule import BlockingRule, NonBlockingRule, RuleResult, RuleVerdict
from agentplane.core.selector import Selector
from agentplane.degradation.modes import DegradationConfig, DegradationMode
from agentplane.engine.engine import PolicyEngine
from agentplane.engine.plugboard import AgentSlot, PlugBoard
from agentplane.escalation.actions import HITL, Alert, Block, Degrade
from agentplane.escalation.chain import EscalationChain, EscalationLevel
from agentplane.rules.blocking import (
    AllowlistRule,
    CostBudgetRule,
    DenylistRule,
    RateRule,
    RedactRule,
    RequireTenantRule,
    TokenBudgetRule,
)
from agentplane.rules.nonblocking import (
    AlertRule,
    AuditRule,
    CostTrackingRule,
    MetricsRule,
)
from agentplane.store.memory import InMemoryPolicyStore
from agentplane.store.sqlite import SqlitePolicyStore
from agentplane.versioning.manager import VersionManager

__version__ = "0.1.0"

__all__ = [
    # Core
    "Policy", "Selector", "PolicyContext",
    "BlockingRule", "NonBlockingRule", "RuleResult", "RuleVerdict",
    # Engine
    "PolicyEngine", "PlugBoard", "AgentSlot",
    # Blocking rules
    "AllowlistRule", "DenylistRule", "RedactRule", "RateRule",
    "RequireTenantRule", "TokenBudgetRule", "CostBudgetRule",
    # Non-blocking rules
    "AuditRule", "AlertRule", "CostTrackingRule", "MetricsRule",
    # Escalation
    "EscalationChain", "EscalationLevel", "Block", "Degrade", "Alert", "HITL",
    # Degradation
    "DegradationMode", "DegradationConfig",
    # Versioning
    "VersionManager",
    # Audit
    "AuditTrail",
    # Store
    "InMemoryPolicyStore", "SqlitePolicyStore",
    # Exceptions
    "AgentplaneError", "PolicyBlocked", "PolicyDegraded", "PolicyConflict",
    "PolicyNotFound", "PolicyVersionError", "EscalationError", "SyncError",
    # Version
    "__version__",
    # Service
    "create_app",
]

try:
    from agentplane.service.app import create_app
except ImportError:
    pass
