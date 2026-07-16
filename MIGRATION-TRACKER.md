# RAPP Eternity rappid — migration tracker

Target format: `rappid:@<owner>/<slug>:<hex>` — no `v2:`/`v3:` prefix, no `<kind>:` segment, no `@github.com/...` suffix. `kind` lives in the `rappid.json` record. Schema is `rapp/1` (ratified Constitution Art. LIV, 2026-07-15; formerly `rapp-rappid/2.0`). Hash preserved (32-hex grandfathered) or fresh-minted (64-hex). Never regenerated. (Constitution Art. XXXIV.1, locked 2026-06-03.)

Full audit: `~/Desktop/RAPPID-Eternity-Migration-Inventory.md` · 50 repos audited, ~150 touch-points across 30 repos.

> ✅ **Done:** `copilot_studio_deploy` rapplication minted compliant — `rappid:@kody-w/copilot_studio_deploy:5fe75198…` (this repo). It's the reference for the new form.

## Phase 0 — Canonical parser / specs (unblocks everything)
- [ ] **RAPP-Bible** — `SPEC/kernel/CONSTITUTION.md` (L2365, 2694), `ESTATE_SPEC.md` (L20,71,87,113): publish Eternity grammar; move `kind` to record. *(other specs copy this)*
- [ ] **rapp-commons** — `tools/federate.py` `_parse_rappid()` regex `^rappid:v2:...`: **accept Eternity BEFORE migrating any records** or federation breaks. ⚠️ critical
- [ ] **RAPP** — confirm `tools/door_address.py` + `migrate_rappid.py` as the single canonicalizer (already compliant); reuse everywhere instead of new regex. `RAR` = compliance benchmark (0 changes).

## Phase 1 — Minting code (stop the bleeding)
- [ ] **RAPP** — `installer/initialize-variant.sh` (~L22–24): hardcoded v2-long parent → `rappid:@rapp/origin:0b635450c04249fbb4b1bdb571044dec`
- [ ] **rapp-egg-hub** — `agents/twin_agent.py` (~L1050 `_summon()`): mints `str(uuid.uuid4())`, schema `rapp-rappid/1.1` → `rappid:<slug>:<64hex>`, schema 2.0
- [ ] **rapp-zoo** — `agents/summon_twin_agent.py` (L340, L37–38): v1-uuid + bare-UUID constants → align to compliant `bond.py`
- [ ] **neighborhood-example** — `agents/egg_hatcher_agent.py` `_mint_rappid()` (~L127): v2-long fallback → `sha256(uuid4().bytes)`
- [ ] **rapp-god-forum** — `singleton/forum_agent.py` (L128), `index.html` (~L342 mint, ~L356 validate): `rappid:v3:` → Eternity *(live forum)* <!-- legacy v2 form: read-forever, never written -->
- [ ] **rapp-resident** — `verify.py`: validates `rappid:v3:` → accept Eternity
- [ ] **microsoft-se-team-neighborhood** — `index.html`: mints `rappid:v3:` → Eternity <!-- legacy v2 form: read-forever, never written -->

## Phase 2 — Generators / stores
- [ ] **RAPP_Store** — `scripts/build_pokedex_api.py` (L113–114, 202–203, parent L125/240): emit Eternity → regenerates all 14 rapplication JSONs + 3 eggs in one pass
- [ ] **wildhaven-ceo** — `genesis-customer-estate.py`, `sign-heartbeat.py` (+6 blessing/cert files)

## Phase 3 — Regenerate organism identity files (run canonicalizer per repo; auto-derivable, hash preserved)
`card.json` / `facets.json` / `members.json` / `rar/index.json` cluster — strip envelope to match the already-clean `rappid.json`:
- [ ] **twin** (card+facets) · [ ] **kody-twin** (card+facets) · [ ] **kody-w-twin** (5 files)
- [ ] **echo-brainstem** (5) · [ ] **tide-brainstem** (8) · [ ] **lumen-brainstem** (6)
- [ ] **wildhaven-ai-homes-twin** (card+facets) · [ ] **aibast-twin** (3, +hatcher regex) · [ ] **bots-in-blazers-twin** (3)
- [ ] **sim-demo-twin** (8) · [ ] **sim-art-collective** (8, +4 member rappids) · [ ] **ant-farm** (4, + `__PLACEHOLDER_HASH__` needs fresh mint)
- [ ] **microsoft-se-team-neighborhood** (3) · [ ] **rapp-test-neighbor** (3) · [ ] **rapp-commons** (identity files, v2-long)
- [ ] **braintrust-template** — card v2-long + 3 dashed-UUID; **create missing `rappid.json`** (fresh mint)
- [ ] **public-art-collective** — card v2-long; **create missing `rappid.json`** (fresh mint)
- [ ] **Species root: RAPP `rappid.json`** → `rappid:@rapp/origin:0b635450c04249fbb4b1bdb571044dec` (propagates to ~8 parent refs)

## Phase 4 — Eggs & auto-regenerated indices
- [ ] **rapp-egg-hub** `index.json` + `*.well-known/*.egg` (e.g. `rapp-commons/.well-known/neighborhood.egg`, `kody-w-twin/.well-known/twin.egg`) — many auto-regenerate via `rebuild_index.py` once source sidecars are fixed

## Phase 5 — Policy decision (don't silently break frozen contracts)
- [ ] **Frozen `specs/RAPPID_SPEC.md` snapshots** (9 repos: tide/lumen/ant-farm/sim-art/wildhaven-ai-homes/microsoft-se/public-art/echo/kody-twin) — annotate as deprecated/archival **or** update. Decide.

## Out of scope (correctly leave as-is)
- Egg-internal 16-hex grammar (`rappid:<type>:@pub/slug:<16hex>` in `RAR`, `wildhaven-ai-homes-twin/utils/egg.py`, `rapp-leviathan-hub`)
- v1-grandfathered kin-vouch rappids · session/memory UUIDs (`rapp-installer`, `CommunityRAPP` marker GUID)
- Inaccessible/empty at audit time (re-audit): `rapp-estate`, `RAPP_Hub`, `rapp-vneighborhood`, `household-neighborhood`
