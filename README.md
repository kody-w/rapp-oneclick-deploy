# RAPP → Copilot Studio · One-Click Deploy

Deploy a RAPP agent into **your own** Microsoft Copilot Studio environment in one click.
Sign in once and the agent imports itself — no downloads, no manual solution import, no config.

[![Deploy to Copilot Studio](https://img.shields.io/badge/Deploy%20to-Copilot%20Studio-742774?style=for-the-badge&logo=microsoft)](https://kody-w.github.io/rapp-oneclick-deploy/)

> **One honest caveat:** you can't push a solution into someone's tenant without *their* sign-in.
> "One click" = click → sign in once (consent) → it autonomously discovers your environment and
> imports the agent. After that single sign-in there are zero manual steps.

---

## Two ways to run it

### A) Drop-in agent — no UI, chat-driven (the simplest)
Drop **one file** into your brainstem's `agents/` folder and just chat — no UI, no extra port:

```bash
curl -fsSL "https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main/apps/@kody-w/copilot_studio_deploy/singleton/copilot_studio_deploy_agent.py" \
  -o ~/.brainstem/src/rapp_brainstem/agents/copilot_studio_deploy_agent.py
```
Then:
> *"Find me a proposal agent to deploy to Copilot Studio."* → it **searches [AI-Agent-Templates](https://github.com/kody-w/AI-Agent-Templates)** (the default source), you pick one, the kernel's Copilot model authors the instructions, and it packages + deploys into your environment.

Sources accepted: an **AI-Agent-Templates** template (default · `action=search_templates`), **any public GitHub raw `agent.py` URL**, or a **local file path**. Actions: `search_templates · list_catalog · fetch_source · package · deploy · complete_deploy · set_credentials · credentials_status · deploy_with_credentials`. The kernel reloads agents every `/chat`, so it's live immediately (verified: appears in `/health`, runs end-to-end).

### B) Full rapplication — egg + local UI
The same capability packaged as a spec-compliant **RAPP rapplication** ([`apps/@kody-w/copilot_studio_deploy`](apps/@kody-w/copilot_studio_deploy)) — agent + cartridge UI, `brainstem-egg/2.2-rapplication`, Eternity rappid. Hatch it:
> *"hatch https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main/api/v1/egg/copilot_studio_deploy.egg"*

served locally at `/rapp_ui/copilot_studio_deploy/`. Same engine as (A), with a UI.

## Three ways to feed the pipe

1. **Pick from the catalog** — agents sourced from [`kody-w/AI-Agent-Templates`](https://kody-w.github.io/AI-Agent-Templates/)
   (`catalog/agents.json`). Pre-converted ones deploy instantly.
2. **Paste a raw `agent.py` URL** — any `raw.githubusercontent.com/.../agent.py`. The **RAPP brainstem**
   looks it up from the public repo and runs it through the conversion pipeline.
3. **Terminal one-liner** — zero setup, zero app registration:
   ```bash
   curl -fsSL https://kody-w.github.io/rapp-oneclick-deploy/install.sh | bash
   ```

## How it works

```
 Path A — prebuilt:   ready solution.zip ─────────────────────────────┐
                                                                       ▼
 Path B — convert:    agent.py (raw URL) ─► convert.py ─► solution.zip ─► agent.py
                                              │                            (ImportSolution)
                                              ▼                            ─► your env
                                     RAPP brainstem /chat  (REQUIRED LLM;
                                     the brainstem's model flipper / Copilot
                                     account picks the model)
```

- **Deploy engine** — [`agent.py`](agent.py): stdlib-only, device-code sign-in (no secrets), discovers
  your environment via the Global Discovery Service, imports + publishes the solution.
- **In-browser one-click** — [`docs/index.html`](docs/index.html): MSAL.js sign-in → environment pick →
  `ImportSolution` directly from the browser.
- **Conversion** — [`convert.py`](convert.py): fetches the `agent.py`, calls the **RAPP brainstem**
  ([`brainstem_llm.py`](brainstem_llm.py)) to author the Copilot Studio agent definition, and packages a
  valid solution by rebranding the system skeleton + injecting the generated GPT instructions. The LLM
  step is **required** — if the brainstem is unreachable, conversion fails (it is not optional).

## Deploy modes

| Mode | Auth | Use |
|---|---|---|
| Browser (Pages) | MSAL popup sign-in | End users, true one-click |
| Terminal (`install.sh`) | Device-code (no secrets) | No app registration needed |
| CI ([`deploy.yml`](.github/workflows/deploy.yml)) | Service principal | Unattended / pipelines |

### Make the browser deploy fully one-click
Register an Entra **single-page application** (redirect URI = the Pages URL), grant delegated
**Dynamics CRM / `user_impersonation`**, and paste its client ID into [`docs/config.js`](docs/config.js).
Until then the page falls back to the terminal one-liner (which needs nothing).

## Repo layout
```
agent.py                 deploy engine (device-code + service-principal)
install.sh               curl | bash bootstrap
catalog/agents.json      agent catalog (sourced from AI-Agent-Templates)
solution/                bundled, pre-converted solution .zip(s)
docs/                    GitHub Pages one-click UI (index.html + config.js)
.github/workflows/       deploy.yml (CI deploy) · convert.yml (pipeline conversion)
```

## Security
Nothing leaves Microsoft: the browser/CLI talks straight to `login.microsoftonline.com` and your
Dataverse Web API. This repo never sees your tokens. The default sign-in uses the Power Platform CLI's
public client; override with `--client-id` / your own registered app for production.

## Develop & test
```bash
pip install pytest && python -m pytest -q      # 13 tests: brainstem client, convert, deploy, catalog
python convert.py --source <raw agent.py URL>  # real conversion via the running brainstem
```
CI runs the suite on every push ([`.github/workflows/test.yml`](.github/workflows/test.yml)).

_MIT licensed. A RAPP project._
