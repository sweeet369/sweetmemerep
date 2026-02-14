# CLAUDE.md - Instructions for Working With Me

## Communication Style

- **Explain things simply** - I'm not a coder, so avoid technical jargon and break things down in plain English
- **Use the AskUserQuestion tool** to ask as many follow-up questions as needed to fully understand what I want

## Before Building Features

- **Always ask clarifying questions first** - Don't start building until you understand exactly what I need
- **Don't make assumptions** - If something is unclear, ask me rather than guessing
- Ask about:
  - What the feature should do
  - How it should look or behave
  - Any edge cases or special scenarios
  - What success looks like

## When I Paste Errors

- **Just fix them** - Don't ask unnecessary questions, diagnose and solve the problem
- If you truly need more information to fix the error, then ask
- Otherwise, read the error, find the issue, and fix it

## General Guidelines

- Keep explanations short and clear
- Show me what you changed and why (in simple terms)
- If there are multiple ways to solve something, explain the options briefly and let me choose
- User prefers changes to be committed and pushed automatically after making fixes

## Project Context

- **What this is**: Python CLI + web app for tracking memecoin trading calls and measuring source performance
- **Stack**: Python 3.11, Flask, PostgreSQL (Supabase), SQLite (local fallback)
- **APIs**: Birdeye (market data, currently degraded), GoPlus (security data), DexScreener (fallback market data)
- **Database**: Supabase PostgreSQL is the active DB. Local SQLite files exist but are empty.
- **CI/CD**: GitHub Actions runs `performance_tracker.py` every 5 minutes via external dispatch (4-hour cron as backup)
- **Cross-AI coordination**: See `BRIDGE.md` for shared context between Claude Code and Codex

## Known Gotchas

- Birdeye API is intermittently down (TLS resets). Circuit breaker auto-switches to DexScreener with escalating cooldown.
- GoPlus domain is `api.gopluslabs.io` (NOT `api.goplus.labs`)
- Database uses `RealDictCursor` for PostgreSQL — access rows by key name, not index
- `database.py` uses `?` placeholders that get auto-replaced to `%s` for PostgreSQL via `_execute()`
- Blockchain values are normalized to lowercase on insert
- Source names are normalized to lowercase on insert
