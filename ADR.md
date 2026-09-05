# **Discord 市場與產業資訊自動推播系統架構決策紀錄 (ADR)**

本文件彙整了本專案所有關鍵架構決策與設計考量。

# **ADR-0001: Serverless Webhook Architecture via GitHub Actions and Discord Webhook**

For personal, zero-cost operation, we chose a serverless pipeline triggered by GitHub Actions pushing via Discord Webhooks, rather than hosting a 24/7 stateful Discord Bot. While this forfeits real-time two-way Slash Commands, it eliminates hosting infrastructure costs, avoids home computer uptime requirements, and operates entirely within free tier limits.

# **ADR-0002: Dual-Channel Webhook Routing**

We decided to route broadcasts into two distinct Discord channels (Daily Channel and Alert Channel) via separate webhook URLs (`DISCORD_WEBHOOK_DAILY_URL` and `DISCORD_WEBHOOK_ALERT_URL`), rather than broadcasting to a single channel. This separates asynchronous, longer-form market analysis from time-sensitive alerts, allowing the user to mute periodic summaries while maintaining high-priority push notifications for breaking events.

# **ADR-0003: Taiwan-US Dual-Track Market Scope**

We decided to anchor the scheduled reports on a dual-track linkage between US tech equities and the Taiwan semiconductor/electronics supply chain. The Morning Brief (08:30 UTC+8) previews Taiwan market open using overnight US indices, TSMC ADR, and futures, while the Market Wrap (17:30 UTC+8) summarizes Taiwan closing prices and institutional flows alongside pre-market previews for the upcoming US trading day.

# **ADR-0004: Dedicated GitHub Actions Workflows**

Instead of combining all cron schedules into a single monolithic workflow file, we decided to separate the tasks into four dedicated workflows (alert.yml, morning\_brief.yml, market\_wrap.yml, weekly\_deepdive.yml). Each invokes main.py with an explicit `--mode` flag. This isolates failures, simplifies manual re-runs via workflow dispatch, and avoids ambiguous schedule time parsing in application code.

# **ADR-0005: Static Configuration Over Database Tables**

We decided to eliminate the channel\_subscriptions table in Supabase and manage all target watchlists, RSS endpoints, and alert keyword heuristics within a Git-tracked `config.yaml` file. Because this is a personal serverless system without dynamic Discord slash command configurations, declarative static configuration provides zero-overhead version control and removes unnecessary database complexity.

# **ADR-0006: Full Article Extraction with Graceful Fallback**

To avoid shallow LLM summaries derived from truncated RSS snippets (50-100 words), candidate articles passing the Stage 1 rule filter will have their full editorial text extracted using `trafilatura`. If extraction fails due to anti-bot mechanisms, paywalls, or timeouts, the pipeline gracefully falls back to the original RSS description without terminating the workflow.

# **ADR-0007: Weekly Retrospective Synthesis from Stored Articles**

Instead of relying on external long-form RSS feeds that often introduce paywalls or scraping fragility, the Weekly Deep-dive synthesizes from the past 7 days of `processed_articles` stored in Supabase. This leverages historical pipeline data to construct cohesive, cross-event macro themes at zero additional cost.

# **ADR-0008: Dry-Run Flag for Safe Local Development and CI**

To prevent cluttering production Discord channels and polluting Supabase deduplication hashes during local development or CI linting, main.py supports a \--dry-run flag. It prints generated Embed payloads to stdout and skips database mutations and webhook dispatches.