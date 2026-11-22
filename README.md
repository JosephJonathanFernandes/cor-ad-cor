# Cor ad Cor — Catholic Daily Liturgical & Spiritual Companion

A grounded Catholic AI companion that brings **today's Mass readings**, the **Saint of the Day**, and the **Catechism of the Catholic Church (CCC)** into plain, unhurried human language—delivered in a warm, reflective spiritual-companion voice with strict source citations.

## Roadmap (Phased Build)

- **Phase 1 (Complete): Grounded Core Engine**
  - Daily Catholic Mass readings & liturgical calendar fetcher + local cache
  - Catechism (`CCC §1–2865`) paragraph-indexed FAISS vector store
  - 4-key Groq LLM router with automatic rate-limit rotation & Gemini fallback
  - Compassionate spiritual companion prompt + theological & pastoral guardrails
- **Phase 2 (Complete): "Bring Your Day to Today's Mass" Web App (MVP)**
  - Calm, ad-free "Liturgical Sanctuary" web UI (`GET /`) with Morning Light & Evening Vigil themes
  - Expandable Mass readings, Saint of the Day, and live Catechism FAISS search
  - Interactive `[CCC §...]` and `[Gospel]` citation pills that scroll to and highlight source texts
  - Two-way personal check-in with starter prompts, pastoral crisis guardrail card, and zero-key preview mode
- **Phase 3 (Complete): Evening Ignatian Examen & Continuity**
  - 3-Minute Nightly Ignatian Examen (`POST /api/v1/examen`) tied back to the morning's readings & Catechism
  - Opt-in local SQLite season memory (`GET /api/v1/memory`, `DELETE /api/v1/memory`) tracking recurring spiritual themes across a liturgical season
  - Gentle, non-scrupulous Confession Prep & Examination of Conscience helper (`POST /api/v1/confession-prep`) with post-Confession clean-slate wipe
- **Phase 4 (Complete): Voice & Messaging Delivery**
  - Calm spoken-word voice-note mode: instant browser narration (`Listen (Calm Voice)`) + cached neural MP3 synthesis (`POST /api/v1/audio/voice-note` via `edge-tts`)
  - Telegram Companion Bot (`scripts/run_telegram_bot.py` for local polling + `POST /api/v1/telegram/webhook`) supporting `/today`, `/voice`, `/examen`, `/confession`, `/ccc`, `/wipe`, and freeform personal check-ins
  - Scheduled morning/evening digest sender (`scripts/send_daily_digest.py`)

## Quickstart (All Phases 1–4)

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
# Add your GROQ_API_KEY_1..4, GEMINI_API_KEY, and optional TELEGRAM_BOT_TOKEN in .env

# Download, normalize, and FAISS-index the full 2,865-paragraph Catechism (CCC §1–§2865)
.venv\Scripts\python scripts\fetch_ccc_full.py

# Or rebuild the FAISS index anytime (e.g., after adding GEMINI_API_KEY for semantic embeddings)
.venv\Scripts\python scripts\ingest_ccc.py

# Start the Web App & API server (Phases 1–4)
.venv\Scripts\uvicorn app.main:app --reload
# Open http://127.0.0.1:8000 in your browser

# Optional: Run the Telegram Companion Bot (long polling)
.venv\Scripts\python scripts\run_telegram_bot.py

# Optional: Send a morning Mass briefing + MP3 voice-note digest (or test with --dry-run)
.venv\Scripts\python scripts\send_daily_digest.py --mode morning --offline --dry-run
```
