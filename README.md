# MALI MODE — FNB AOTY Hackathon 2026 MVP

MALI MODE is a working web application concept for youth entrepreneurs and small businesses. It helps users capture everyday business transactions, digitise existing records, and receive plain-language business insights based on saved activity. It is a real web app with a FastAPI backend and persistent database, not a static website.

## MVP features
- Account signup, email verification and sign-in with password hashing and signed HTTP-only session cookies.
- Role-specific profiles and dashboards for business owners, new entrepreneurs, suppliers and delivery partners.
- Guided startup business-plan draft and PDF download for new entrepreneurs.
- Transaction entry from natural-language text and supported browser speech-to-text. Users review extracted values before saving.
- Optional OCR scanning of paper records and receipts, with review before import.
- CSV import preview and explicit confirmation, designed to help users migrate existing records without retyping each row.
- Saved transaction history and user-specific business intelligence: recent sales, recorded costs, indicative balance, comparison to the previous 30-day period, largest cost category and repeat sale descriptions.
- Rule-based next-step advice derived only from that user's saved transaction records.
- Official links for government eTenders, the Central Supplier Database and SEDA.

## Business intelligence behaviour
The `/api/business-insights` endpoint calculates indicators from the signed-in user's saved records. It uses transparent rules, not a trained AI model. The interface explains that recommendations are indicative and only as complete as the records entered. The system does not claim to calculate audited profit, predict funding approval, process payments or verify suppliers.

## Run locally (Python 3.11+)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Generate a strong secret key and replace `SECRET_KEY` in `.env`. For a quick local demo, leave `COOKIE_SECURE=false` on localhost. Then run:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs. Health check: http://127.0.0.1:8000/health. SQLite database `mali_mode.db` is created on first run.

## Email verification for local testing
Configure SMTP values in `.env` to send verification emails. If SMTP is not configured, the development verification link is logged in the server terminal; use this only for local testing. Do not deploy publicly with this development fallback.

## Optional scanning and voice
- Photo OCR requires Pillow, pytesseract and the Tesseract OCR executable installed on the host. Printed text generally works better than handwriting.
- Voice-to-text depends on browser/device support and may require microphone permission and HTTPS outside localhost. Typing and CSV import remain available when voice is unsupported.

## Sample CSV
Use `sample_transactions.csv` as an import example. The app previews rows before saving; check dates, amounts and transaction types before confirming.

## Security and limitations
This is a hackathon MVP, not a production-certified financial system. Before public deployment, configure HTTPS and secure cookies, add CSRF protection and rate limiting, add password reset and resend-verification flows, use database migrations, set up encrypted backups and monitoring, review POPIA obligations, and run a security test. Email verification verifies control of an email address only; it does not verify a person's identity or a supplier's legitimacy.

Supplier catalogues, real order fulfilment, verified supplier badges, delivery tracking, tender aggregation, payment processing, bank integrations and AI/LLM recommendations are not implemented as live integrations in this MVP. Official external links are provided as starting points only. Do not enter real payment card details or sensitive bank credentials.

## Hackathon demo path
1. Create a test account and verify it using the configured email or local terminal link.
2. Complete the profile and, for a new entrepreneur, review the generated business plan.
3. Record a sale and an expense using text; use voice if supported.
4. Import `sample_transactions.csv` or test a photo scan if OCR is installed.
5. Open Business Intelligence & Next Steps and show how recommendations respond to saved history.
6. Explain limitations honestly and show the security plan in the Sonke SSDLC submission.
