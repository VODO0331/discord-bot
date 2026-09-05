# **Discord Market Broadcast Context (CONTEXT.md)**

Context for the automated industry and market information broadcast system delivered via Discord.

# **Language (統一領域語言)**

Breaking Alert:  
A high-urgency market or industry notification triggered when an event matches watchlist entities and achieves an LLM significance rating of 4 or higher.  
Avoid: News flash, push notification, instant alert

Morning Brief:  
A daily scheduled market summary sent before market open, containing overnight indices and key upcoming events.  
Avoid: Daily news, pre-market report

**Market Wrap**:  
A daily post-close market summary highlighting index fluctuations, strong/weak sectors, and key corporate announcements.  
Avoid: Closing report, evening summary

Daily Channel:  
A Discord channel dedicated to scheduled periodic summaries (Morning Brief, Market Wrap, Weekly Deep-dive) intended for asynchronous reading.  
*Avoid*: Main channel, feed channel, news channel

Alert Channel:  
A Discord channel dedicated exclusively to Breaking Alerts with active notifications enabled.  
Avoid: Urgent channel, notification channel

Watchlist:  
The predefined set of core equities, ADRs, and indices tracked across US and Taiwan tech ecosystems (e.g., SOX, Nasdaq, TSM, NVDA, 2330.TW).  
Avoid: Stock list, portfolio, favorites

Institutional Flow (三大法人籌碼):  
The net buy/sell positions of foreign investors, investment trusts, and dealers in the Taiwan stock market, reported daily during Market Wrap.  
*Avoid*: Big money flow, market chips

**Execution Mode**:

The CLI runtime argument (`--mode=alert|morning|wrap|weekly`) passed by dedicated GitHub Actions workflows to invoke specific pipeline logic in main.py.  
|---|---|

Feed Config:  
The declarative Git-versioned config.yaml file defining watchlists, RSS endpoints, and keyword rules.  
*Avoid*: Subscription settings, DB config, channel rules

**Processed Article**:  
An article whose unique URL SHA-256 hash has been verified and recorded in the Supabase database to prevent duplicate broadcasts.  
Avoid: Stored news, broadcast log, cached item

Article Extraction:  
The retrieval of clean editorial body text from candidate articles via trafilatura, with automatic graceful fallback to the RSS description upon network or anti-bot failures.  
*Avoid*: Web scraping, page download, text mining

**Weekly Deep-dive**:  
A Saturday retrospective synthesized by LLM from the past 7 days of processed\_articles in Supabase, structured into 3 macro technology/supply chain trends with top article references.  
Avoid: Weekend special, weekly digest, market recap

**Dry-Run Mode**:  
A CLI execution flag (`--dry-run`) that runs data pipelines and prints assembled Embed JSON payloads to the console without writing to Supabase or dispatching HTTP POST requests to Discord Webhooks.  
Avoid: Test mode, mock run, debug print