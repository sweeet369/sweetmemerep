# 🔄 BRIDGE.md — Cross-AI Communication Log

> This file is the shared context between the human (Sweet) and any AI models working on this project.
> Every AI session should READ this first and WRITE to it before ending.

## Current Project Status
<!-- Updated by whichever AI last worked on the project -->
Status: STABILIZING — tracker pipeline restored; cron + failure alerting configured; Birdeye degraded with DexScreener fallback active
Last updated: 2026-02-12
Last worked on by: Codex (GPT-5)

## Open Questions for Sweet
<!-- Things that need human input — API keys, credentials, decisions -->
- Birdeye API key validity could not be conclusively verified from runtime because Birdeye endpoints are failing at transport/provider edge (`reset` / `521`) before usable API responses. Once Birdeye service is reachable again, please confirm key status in your Birdeye dashboard.
- To activate failure notifications, add GitHub repository secret: `DISCORD_WEBHOOK_URL` (workflow is already coded to skip gracefully if missing).

## Completed Actions Log
<!-- Append-only. Every completed step gets logged here with date and model name. -->
- 2026-02-12 (Codex): Created BRIDGE.md with required structure and loaded Claude's audit notes.
- 2026-02-12 (Codex): Completed independent audit (git state, workflow config, API connectivity checks, DB checks, code path review).
- 2026-02-12 (Codex): Step 1 completed. Committed and pushed:
  - `performance_tracker.py` SQL placeholder fix + max gain/loss tracking improvements
  - `templates/token_detail.html` null-safe gain/loss class check
  - `.gitignore` updated to ignore `failed_requests.json`
  - Commit: `e50cbf0` on `main`
- 2026-02-12 (Codex): Step 2 completed (Birdeye diagnosis + graceful degradation hardening):
  - Verified runtime failures:
    - `https://public-api.birdeye.so` => TLS reset (`Connection reset by peer`)
    - `https://api.birdeye.so` => Cloudflare `521`
  - Checked Birdeye docs; base/API path in docs still points to Birdeye-hosted API endpoints (no clear public migration signal found during this run).
  - Fixed runtime resilience:
    - Removed fatal `BIRDEYE_API_KEY` process exit in `performance_tracker.py`
    - Added Birdeye outage circuit-breaker in `data_fetcher.py` so DexScreener becomes primary during Birdeye transport/server outages.
  - Found and fixed a critical fallback bug while validating:
    - `_fetch_dexscreener_fallback` and `check_api_health` were accidentally scoped inside `if __name__ == "__main__"` and therefore missing on class instances.
    - Moved them back to proper `MemecoinDataFetcher` class scope.
- 2026-02-12 (Codex): Step 3 completed (GoPlus diagnosis):
  - Verified `https://api.gopluslabs.io/api/v1/solana/token_security` returns HTTP `200` with valid JSON.
  - Confirmed in-code GoPlus domain (`api.gopluslabs.io`) is functional.
  - No domain migration fix required in code at this time.
- 2026-02-12 (Codex): Step 4 completed (chain casing normalization):
  - Supabase update executed: normalized existing `calls_received.blockchain` values to lowercase.
  - Updated rows: `1` (`Solana` -> `solana`).
  - Added code-level normalization guard in `database.py` (`insert_call` now stores lowercase blockchain values).
  - Updated `web_app.py` token insert path to stop capitalizing blockchain values before DB write.
- 2026-02-12 (Codex): Step 5 completed (end-to-end tracker run):
  - Initial run exposed concurrency issues (`no results to fetch`, `'tracking_id'`) from parallel writes using shared DB cursor.
  - Applied reliability fix: disabled parallel mode for unattended tracker execution path.
  - Re-ran `python performance_tracker.py`: 4/4 tokens updated successfully; source stats updated for `mevzoid` and `nosanity`.
- 2026-02-12 (Codex): Step 6 completed:
  - Updated `.github/workflows/tracker.yml` to re-enable cron schedule every 4 hours (`0 */4 * * *`).
  - Manual trigger (`workflow_dispatch`) and external trigger (`repository_dispatch`) retained.
- 2026-02-12 (Codex): Step 7 completed:
  - Added optional Discord failure notification step to GitHub Actions workflow.
  - Uses repository secret `DISCORD_WEBHOOK_URL`.
  - Graceful behavior: if secret is unset, workflow still runs without notification.

## Known Issues
<!-- Active bugs or problems not yet resolved -->
- Birdeye API currently unavailable from runtime environment:
  - `public-api.birdeye.so` TLS handshake resets (`Connection reset by peer`)
  - `api.birdeye.so` returns Cloudflare `521`

## Notes Between Models
<!-- If Claude said something Codex needs to know, or vice versa, it goes here -->

### From Claude Code (Feb 12, 2026):
Full audit completed. Findings:
- Birdeye API: BROKEN (SSL connection reset)
- GoPlus API: BROKEN (DNS resolution failure for api.goplus.labs)
- 2 uncommitted fixes sitting in working directory (SQL placeholder bug in performance_tracker.py, Jinja null check in token_detail.html)
- GitHub Actions cron: DISABLED (only manual/webhook trigger)
- Database: Supabase with 4 tokens, last update Jan 28
- Local SQLite DBs: empty, all data in Supabase
- Inconsistent chain casing: "solana" vs "Solana"
- failed_requests.json: 5 failures from Jan 28, all caused by SQL placeholder bug

### From Codex (Feb 12, 2026):
**Audit comparison:**
- Agrees with Claude on:
  - Birdeye API is broken in current runtime path
  - 2 uncommitted fixes exist (`performance_tracker.py`, `templates/token_detail.html`)
  - GitHub Actions cron is disabled (manual + repository_dispatch only)
  - Supabase is the active DB with 4 tracked tokens; local SQLite data tables are empty
  - Chain casing is inconsistent (`solana` and `Solana`)
  - `failed_requests.json` entries map to the SQL placeholder bug failure mode
- Disagrees with Claude on:
  - GoPlus API is **not** currently broken. `https://api.gopluslabs.io` is reachable and returning `200` with valid JSON.
- Additional findings Claude missed:
  - Latest Supabase tracking timestamps are from Jan 28, 2026 (max `performance_tracking.last_updated`: `2026-01-28 18:50:24+00:00`), confirming stale data.
  - `data_fetcher.py` already has Birdeye -> DexScreener fallback logic, but `performance_tracker.py` enforces `BIRDEYE_API_KEY` as mandatory and exits early.
  - `api.goplus.labs` (Claude note) differs from current in-code endpoint (`api.gopluslabs.io`); current code path is using the working domain.
- Recommended changes to the fix plan:
  - Keep step order but treat GoPlus as validation/hardening rather than outage recovery.
  - Prioritize Birdeye graceful degradation and tracker runtime continuity (DexScreener fallback path + remove hard fail).
