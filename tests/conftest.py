import os, sys, types
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Shim `openrappter.agents.basic_agent.BasicAgent` exactly like the brainstem kernel
# does, so a drop-in agent file imports cleanly in tests.
class BasicAgent:
    def __init__(self, name=None, metadata=None):
        if name is not None: self.name = name
        if metadata is not None: self.metadata = metadata
    def perform(self, **kwargs): return "Not implemented."
    def system_context(self): return None
    def to_tool(self):
        return {"type": "function", "function": {
            "name": self.name, "description": self.metadata.get("description", ""),
            "parameters": self.metadata.get("parameters", {})}}

for mod in ("openrappter", "openrappter.agents", "openrappter.agents.basic_agent"):
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)
sys.modules["openrappter.agents.basic_agent"].BasicAgent = BasicAgent
sys.modules["openrappter"].agents = sys.modules["openrappter.agents"]
sys.modules["openrappter.agents"].basic_agent = sys.modules["openrappter.agents.basic_agent"]

SAMPLE_AGENT = '''
class AccountIntelligenceAgent:
    """Gathers stakeholder, competitive and risk intelligence for an account."""
    name = "account_intelligence"
    def analyze_account(self, account_id: str):
        """Return a 360 intelligence brief for the account."""
        return {"status": "success"}
'''

CANNED_SPEC = {
    "display_name": "Account Intelligence",
    "unique_name": "accountintelligence",
    "description": "Gathers stakeholder, competitive and risk intelligence.",
    "instructions": "# Purpose\\nYou are an account intelligence agent.\\n# Guidelines\\n- Be concise.",
}
