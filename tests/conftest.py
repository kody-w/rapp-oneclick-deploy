import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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
