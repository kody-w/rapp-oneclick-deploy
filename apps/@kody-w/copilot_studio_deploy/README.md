# Copilot Studio Deploy — a RAPP rapplication

Convert any RAPP agent into a **Microsoft Copilot Studio** agent and deploy it into
**your own** environment — fully locally. The agent is the API; the UI is a local
view. No PII or secrets ship with this rapplication: you provide a
`local.settings.json` (service principal) at deploy time and it is used and stored
**only on your machine**.

## Install (two steps)
1. Hatch it: ask your brainstem **"hatch https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main/api/v1/egg/copilot_studio_deploy.egg"** (via `egg_hatcher`), or drop `singleton/copilot_studio_deploy_agent.py` into your brainstem's `agents/` folder.
2. Open the local UI the brainstem serves at **`/rapp_ui/copilot_studio_deploy/`** — pick an agent (or paste a raw `agent.py` URL), optionally import your `local.settings.json`, and click Deploy.

## How it works
- **Agent** (`singleton/copilot_studio_deploy_agent.py`) — the API. Actions: `list_catalog`, `fetch_source`, `package`, `deploy`, `complete_deploy`, `set_credentials`, `credentials_status`, `deploy_with_credentials`. The kernel's Copilot model authors the agent instructions; the agent packages a valid Copilot Studio solution and imports it via the Dataverse Web API.
- **UI** (`ui/index.html`) — calls the agent over the **cartridge bridge** (`rapp:invoke`); no token crosses the iframe boundary.
- **Two auth paths** — device-code sign-in (zero setup) or a service principal imported from `local.settings.json` (autonomous, saved to `~/.rapp_deploy_settings.json`, never sent to any cloud model).

## Identity
`rappid:@kody-w/copilot_studio_deploy:7d3729d52e62fefa7bad2ee8c3bef918cee720ca320b2c85fdf22f5aa7034d1d`
· kind `rapplication` · parent `@rapp/origin` · schema `rapp/1` (Eternity; ratified Art. LIV, formerly rapp-rappid/2.0).

MIT licensed.
