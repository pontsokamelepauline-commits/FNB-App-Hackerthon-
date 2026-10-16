#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if [ ! -f .env ]; then cp .env.example .env; fi
echo "Starting MALI MODE at http://127.0.0.1:8000"
echo "For local testing, open .env and set SECRET_KEY to a long random value."
uvicorn app.main:app --reload
