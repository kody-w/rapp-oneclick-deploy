// One-click deployer configuration.
//
// The page works out-of-the-box in "terminal" mode (copy a one-liner) with NO setup.
// To enable the PURE in-browser one-click deploy, register an Entra "Single-page
// application" (SPA) with redirect URI = this Pages URL, grant delegated
// "Dynamics CRM / user_impersonation", and paste its Application (client) ID below.
window.RAPP_CONFIG = {
  clientId: "REPLACE_WITH_ENTRA_SPA_CLIENT_ID",          // <- set to enable in-browser deploy
  tenant: "organizations",                                // or your tenant GUID
  solutionUrl: "https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main/solution/dealprogression_solution.zip",
  solutionName: "Deal Progression Agent (RAPP)",
  installCommand: "curl -fsSL https://kody-w.github.io/rapp-oneclick-deploy/install.sh | bash",
};
