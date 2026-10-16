import json, os, secrets, logging
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from pydantic import BaseModel, EmailStr, Field
from .database import Base, engine, get_db
from .models import User, Profile, BusinessPlan, TransactionRecord
from .security import hash_password, verify_password, create_token, read_token, token_hash
from .mailer import send_verification
from .plan import build_plan
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO

load_dotenv()
logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="MALI MODE", description="Youth entrepreneurship and small-business growth platform")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
Base.metadata.create_all(bind=engine)
ROLES = {"business_owner", "new_entrepreneur", "supplier", "delivery_partner"}

class TransactionInput(BaseModel):
    transaction_date: str = Field(min_length=10, max_length=10)
    transaction_type: str
    description: str = Field(min_length=1, max_length=240)
    category: str = Field(default="Other", max_length=60)
    amount: float = Field(gt=0, le=100000000)
    quantity: float = Field(default=1, gt=0, le=10000000)
    payment_method: str = Field(default="Other", max_length=40)
    source: str = Field(default="typed", max_length=20)

class TransactionParseInput(BaseModel):
    text: str = Field(min_length=2, max_length=2000)

class SignupIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    role: str
    password: str = Field(min_length=10, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProfileIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=40)
    location: str = Field(min_length=2, max_length=180)
    business_name: str = Field(min_length=2, max_length=180)
    business_type: str = Field(min_length=2, max_length=120)
    product_service: str = Field(default="Not provided", max_length=500)
    target_customers: str = Field(default="Not provided", max_length=500)
    customer_problem: str = Field(default="Not provided", max_length=1000)
    starting_budget: float = Field(default=0, ge=0)
    selling_price: float = Field(default=0, ge=0)
    unit_cost: float = Field(default=0, ge=0)
    expected_units_month: int = Field(default=0, ge=0)
    monthly_fixed_costs: float = Field(default=0, ge=0)
    funding_needed: float = Field(default=0, ge=0)
    marketing_plan: str = Field(default="Not provided", max_length=1000)
    operations: str = Field(default="Not provided", max_length=1000)
    risks: str = Field(default="Not provided", max_length=1000)
    registration_status: str = Field(default="Not sure what is required", max_length=80)
    experience: str = Field(default="Not provided", max_length=1000)
    role_details: str = Field(default="", max_length=1500)


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("mali_mode_session")
    uid = read_token(token) if token else None
    if not uid: raise HTTPException(status_code=401, detail="Please sign in again.")
    user = db.get(User, uid)
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Account not available.")
    return user

def profile_data(db, user):
    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    return p, (json.loads(p.data_json) if p else {})

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/health")
def health(): return {"status":"ok", "app":"MALI MODE", "mode":"hackathon_mvp"}

@app.post("/api/signup")
def signup(data: SignupIn, db: Session = Depends(get_db)):
    if data.role not in ROLES: raise HTTPException(422, "Choose a valid account type.")
    if db.scalar(select(User).where(User.email == data.email.lower())): raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    if len(data.password) < 10 or not any(c.isalpha() for c in data.password) or not any(c.isdigit() for c in data.password): raise HTTPException(422, "Use at least 10 characters, including a letter and a number.")
    token = secrets.token_urlsafe(32)
    user = User(full_name=data.full_name.strip(), email=data.email.lower(), phone=data.phone.strip(), role=data.role, password_hash=hash_password(data.password), verification_token_hash=token_hash(token))
    db.add(user); db.commit(); db.refresh(user)
    db.add(Profile(user_id=user.id, data_json=json.dumps({"full_name":user.full_name,"phone":user.phone,"email":user.email}), completed=False)); db.commit()
    try: send_verification(user.email, user.full_name, token)
    except Exception: logging.exception("Verification email failed")
    return {"message":"Account created. Verify your email before signing in.", "email":user.email, "verification_sent":bool(os.getenv("SMTP_HOST"))}

@app.get("/verify-email", response_class=HTMLResponse)
def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.verification_token_hash == token_hash(token)))
    if not user: return HTMLResponse("<h2>This verification link is invalid or has already been used.</h2><p>Please request a new verification email.</p>", status_code=400)
    user.email_verified = True; user.verification_token_hash = None; db.commit()
    return templates.TemplateResponse(request, "verified.html", {"email":user.email})

@app.post("/api/login")
def login(data: LoginIn, response=None, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Email or password is incorrect.")
    if not user.email_verified: raise HTTPException(403, "Please verify your email using the link sent to you before signing in.")
    token = create_token(user.id)
    result = JSONResponse({"message":"Signed in.", "user":{"id":user.id,"name":user.full_name,"role":user.role,"email":user.email}})
    result.set_cookie("mali_mode_session", token, httponly=True, secure=os.getenv("COOKIE_SECURE", "false").lower()=="true", samesite="lax", max_age=43200, path="/")
    return result

@app.post("/api/logout")
def logout():
    r = JSONResponse({"message":"Signed out."}); r.delete_cookie("mali_mode_session", path="/"); return r

@app.get("/api/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, data = profile_data(db, user)
    plan = db.scalar(select(BusinessPlan).where(BusinessPlan.user_id == user.id))
    gate_complete = user.role != "new_entrepreneur" or bool(p and p.completed and plan)
    return {"id":user.id,"name":user.full_name,"email":user.email,"phone":user.phone,"role":user.role,"email_verified":user.email_verified,"profile_completed":bool(p and p.completed),"business_plan_ready":bool(plan),"dashboard_unlocked":gate_complete,"profile":data}

@app.post("/api/profile")
def save_profile(data: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Entrepreneurs must provide the full planning profile before the dashboard is unlocked.
    if user.role == "new_entrepreneur":
        if data.starting_budget <= 0: raise HTTPException(422, "Enter a starting budget above zero. If you have no starting capital, explain a realistic funding plan before continuing.")
        if data.selling_price < data.unit_cost and data.expected_units_month > 0: raise HTTPException(422, "Your selling price is below your unit cost. Review your numbers or explain your pricing strategy before continuing.")
    elif not data.role_details.strip():
        raise HTTPException(422, "Please complete the details requested for your account type.")
    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not p: p = Profile(user_id=user.id, data_json="{}", completed=False); db.add(p)
    d = data.model_dump(); d["email"] = user.email; d["role"] = user.role
    p.data_json = json.dumps(d); p.completed = True
    user.full_name = data.full_name.strip(); user.phone = data.phone.strip()
    db.commit()
    return {"message":"Profile saved.", "profile_completed":True}

@app.post("/api/business-plan/generate")
def generate_plan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "new_entrepreneur": raise HTTPException(403, "The guided startup plan is for new entrepreneurs.")
    p, data = profile_data(db, user)
    if not p or not p.completed: raise HTTPException(403, "Complete your full business profile before generating a plan.")
    plan_data = build_plan(data)
    plan = db.scalar(select(BusinessPlan).where(BusinessPlan.user_id == user.id))
    if not plan: plan = BusinessPlan(user_id=user.id, plan_json=json.dumps(plan_data)); db.add(plan)
    else: plan.plan_json = json.dumps(plan_data)
    db.commit()
    return {"message":"Business plan generated from your answers. Review every section before using it.", "plan":plan_data,"dashboard_unlocked":True}

@app.get("/api/business-plan")
def get_plan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.scalar(select(BusinessPlan).where(BusinessPlan.user_id == user.id))
    if not plan: raise HTTPException(404, "Complete the guided profile and generate your plan first.")
    return json.loads(plan.plan_json)

@app.get("/api/business-plan.pdf")
def download_plan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.scalar(select(BusinessPlan).where(BusinessPlan.user_id == user.id))
    if not plan: raise HTTPException(403, "Generate your business plan before downloading it.")
    d = json.loads(plan.plan_json); buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=48,leftMargin=48,topMargin=48,bottomMargin=48)
    styles = getSampleStyleSheet(); styles.add(ParagraphStyle(name="KasiTitle", parent=styles["Title"], textColor=colors.HexColor("#145b43"), spaceAfter=16))
    story = [Paragraph(d["title"], styles["KasiTitle"]), Paragraph(f"Prepared {d['created']} • Draft based on owner-provided information", styles["Normal"]), Spacer(1,14)]
    sections = [("Executive summary","executive_summary"),("Product or service","offer"),("Target customers","customers"),("Operating area","area"),("Customer need","customer_problem"),("Marketing plan","marketing"),("Operations","operations"),("Starting budget","budget"),("Funding sought","funding_needed"),("Pricing and assumptions","financial_note"),("Risk considerations","risks")]
    for heading,key in sections:
        story.extend([Paragraph(heading, styles["Heading2"]), Paragraph(str(d.get(key,"Not provided")).replace("&","&amp;"), styles["BodyText"]), Spacer(1,6)])
    story.append(Paragraph("Illustrative monthly estimate", styles["Heading2"]))
    for label,key in [("Expected units/month","monthly_units"),("Estimated revenue","monthly_revenue"),("Estimated variable costs","monthly_variable_cost"),("Monthly fixed costs","monthly_fixed_costs"),("Estimated surplus before omitted costs","estimated_monthly_surplus")]: story.append(Paragraph(f"{label}: {d.get(key,'Not provided')}", styles["BodyText"]))
    story.append(Paragraph("Milestones", styles["Heading2"]))
    story.append(ListFlowable([ListItem(Paragraph(x,styles["BodyText"])) for x in d["milestones"]], bulletType="bullet"))
    story.append(Paragraph("Documentation checklist", styles["Heading2"]))
    story.append(ListFlowable([ListItem(Paragraph(x,styles["BodyText"])) for x in d["documents"]], bulletType="bullet"))
    story.extend([Spacer(1,12), Paragraph(d["disclaimer"], styles["Italic"])])
    doc.build(story); buf.seek(0)
    filename = "MALI_MODE_Business_Plan.pdf"
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition":f'attachment; filename="{filename}"'})

def parse_transaction_text(raw: str):
    """Conservative rule-based parser for the hackathon MVP; user must review its draft."""
    import re
    text = raw.strip()
    low = text.lower()
    if re.search(r'\b(sold|sale|selling|received payment)\b', low): kind = "Sale"
    elif re.search(r'\b(bought|buy|purchase|purchased|restocked)\b', low): kind = "Purchase"
    elif re.search(r'\b(refund|refunded|returned money)\b', low): kind = "Refund"
    elif re.search(r'\b(spent|paid|expense|cost me|fuel|transport|rent|electricity|wages)\b', low): kind = "Expense"
    else: kind = "Sale"
    patterns = [r'\bR\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)', r'\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:rand|rands|zar)\b', r'\b(?:for|of|amount(?:ing)? to|paid)\s+(?:R\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)']
    amount = None
    for pat in patterns:
        m = re.search(pat, low, re.I)
        if m:
            try: amount = float(m.group(1).replace(',', '')); break
            except ValueError: pass
    qty = 1.0
    m = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\s+(?:bags?|bunches?|boxes?|crates?|bottles?|packs?|kg|kilograms?|units?|items?)\b', low)
    if m: qty = float(m.group(1))
    pay = "Cash" if re.search(r'\b(cash)\b', low) else "Card" if re.search(r'\b(card|swipe)\b', low) else "Bank Transfer" if re.search(r'\b(bank transfer|eft|transfer)\b', low) else "E-wallet" if re.search(r'\b(e-wallet|ewallet|mobile money)\b', low) else "Other"
    category = "Stock" if kind == "Purchase" else "Transport" if re.search(r'\b(transport|taxi|fuel|petrol)\b', low) else "Sales" if kind == "Sale" else "Other"
    cleaned = re.sub(r'\b(today|yesterday|this morning|tonight|cash|by card|card|bank transfer|eft|transfer|e-wallet|ewallet|mobile money|sold|sell|selling|bought|buy|purchased|purchase|restocked|spent|paid|expense|refunded|refund|received payment for)\b', '', text, flags=re.I)
    cleaned = re.sub(r'\bR\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?\b|\b[0-9][0-9,]*(?:\.[0-9]{1,2})?\s*(?:rand|rands|zar)\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'^I\s+', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\b(for|of)\s*$', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,!;:-') or text
    txdate = date.today() - timedelta(days=1) if re.search(r'\byesterday\b', low) else date.today()
    return {"transaction_date":txdate.isoformat(), "transaction_type":kind, "description":cleaned[:240], "category":category, "amount":amount, "quantity":qty, "payment_method":pay, "source":"typed", "needs_review":True, "original_text":text}

@app.post("/api/transactions/parse")
def transaction_parse(data: TransactionParseInput, user: User = Depends(current_user)):
    return parse_transaction_text(data.text)

@app.get("/api/transactions")
def list_transactions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(TransactionRecord).where(TransactionRecord.user_id == user.id).order_by(desc(TransactionRecord.id)).limit(300)).all()
    return [{"id":r.id,"transaction_date":r.transaction_date,"transaction_type":r.transaction_type,"description":r.description,"category":r.category,"amount":r.amount/100,"quantity":float(r.quantity),"payment_method":r.payment_method,"source":r.source} for r in rows]

@app.get("/api/business-insights")
def business_insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Transparent rule-based insights calculated only from the signed-in user's saved records."""
    from collections import Counter, defaultdict
    from datetime import datetime
    rows = db.scalars(select(TransactionRecord).where(TransactionRecord.user_id == user.id).order_by(TransactionRecord.transaction_date.asc()).limit(5000)).all()
    tx = []
    for r in rows:
        try:
            tx.append({"date": date.fromisoformat(r.transaction_date), "type": r.transaction_type,
                       "description": (r.description or "Unlabelled transaction").strip(),
                       "category": (r.category or "Other").strip(), "amount": r.amount / 100,
                       "quantity": float(r.quantity or 1)})
        except (ValueError, TypeError):
            continue
    today = date.today()
    current_start = today - timedelta(days=29)
    previous_start = today - timedelta(days=59)
    sales_types = {"Sale"}
    cost_types = {"Purchase", "Expense"}
    current = [r for r in tx if current_start <= r["date"] <= today]
    previous = [r for r in tx if previous_start <= r["date"] < current_start]
    def totals(items):
        sales = sum(r["amount"] for r in items if r["type"] in sales_types)
        refunds = sum(r["amount"] for r in items if r["type"] == "Refund")
        costs = sum(r["amount"] for r in items if r["type"] in cost_types)
        return {"sales": round(sales, 2), "refunds": round(refunds, 2), "costs": round(costs, 2), "net_recorded": round(sales - refunds - costs, 2)}
    cur, prev = totals(current), totals(previous)
    advice = []
    if len(tx) < 5:
        advice.append({"title":"Build a useful record history", "priority":"Start here", "detail":f"You have {len(tx)} saved transaction(s). Record sales and costs consistently for at least a few weeks before relying on trends. You can import old records to get started faster."})
    if cur["sales"] > 0 and cur["costs"] > cur["sales"] - cur["refunds"]:
        advice.append({"title":"Costs are higher than recorded sales", "priority":"High", "detail":"In the last 30 days, recorded purchases and expenses exceed sales after refunds. Review your largest costs and confirm that all sales have been recorded. This is a record-based warning, not a full accounting profit calculation."})
    elif cur["sales"] > 0 and cur["net_recorded"] >= 0:
        advice.append({"title":"Keep tracking the money left over", "priority":"Useful next step", "detail":f"Your recorded sales less purchases, expenses and refunds are R{cur['net_recorded']:.2f} for the last 30 days. Keep recording every cost, including transport and fees, to make this estimate more complete."})
    if prev["sales"] > 0:
        change = ((cur["sales"] - prev["sales"]) / prev["sales"]) * 100
        if change <= -15:
            advice.append({"title":"Recorded sales have fallen", "priority":"Review", "detail":f"Sales are {abs(change):.0f}% lower than the previous 30-day period. Check your sales days, product availability and customer activity before deciding what to change."})
        elif change >= 15:
            advice.append({"title":"Recorded sales are growing", "priority":"Opportunity", "detail":f"Sales are {change:.0f}% higher than the previous 30-day period. Check that stock and supplier capacity can keep up, and avoid increasing costs until the trend is sustained."})
    category_costs = defaultdict(float)
    for r in current:
        if r["type"] in cost_types:
            category_costs[r["category"] or "Other"] += r["amount"]
    if category_costs:
        top_cat, top_value = max(category_costs.items(), key=lambda kv: kv[1])
        advice.append({"title":"Review your largest recorded cost", "priority":"Cost control", "detail":f"{top_cat} is your largest purchase/expense category in the last 30 days at R{top_value:.2f}. Compare prices or quantities with your records before making a change."})
    sale_descriptions = Counter(r["description"] for r in current if r["type"] == "Sale" and r["description"])
    if sale_descriptions:
        top_item, count = sale_descriptions.most_common(1)[0]
        advice.append({"title":"Look at repeat sales", "priority":"Sales insight", "detail":f'"{top_item}" appears in {count} recorded sale(s) in the last 30 days. Check whether this reflects repeat demand and whether you have enough stock.'})
    if not tx:
        advice = [{"title":"Start with one real transaction", "priority":"First step", "detail":"Record a sale or expense, or import your existing records. MALI MODE will use your saved history to calculate business indicators and give record-based suggestions."}]
    return {"generated_at": today.isoformat(), "records_analysed": len(tx), "period_days": 30,
            "current_period": cur, "previous_period": prev, "advice": advice[:6],
            "method":"Transparent rule-based analysis of saved transaction history. Advice is indicative and only as complete as the records entered; it is not accounting, credit or investment advice."}

@app.post("/api/transactions")
def create_transaction(data: TransactionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.transaction_type not in {"Sale","Purchase","Expense","Refund"}: raise HTTPException(422,"Choose a valid transaction type.")
    if data.payment_method not in {"Cash","Card","Bank Transfer","E-wallet","Credit","Other"}: raise HTTPException(422,"Choose a valid payment method.")
    try: parsed_date = date.fromisoformat(data.transaction_date)
    except ValueError: raise HTTPException(422,"Use a valid transaction date.")
    if parsed_date > date.today(): raise HTTPException(422,"Transaction date cannot be in the future.")
    row = TransactionRecord(user_id=user.id, transaction_date=parsed_date.isoformat(), transaction_type=data.transaction_type, description=data.description.strip(), category=data.category, amount=round(data.amount*100), quantity=str(data.quantity), payment_method=data.payment_method, source=data.source if data.source in {"typed","voice","scan","csv"} else "typed")
    db.add(row); db.commit(); db.refresh(row)
    return {"message":"Transaction saved.","transaction":{"id":row.id,"transaction_date":row.transaction_date,"transaction_type":row.transaction_type,"description":row.description,"category":row.category,"amount":row.amount/100,"quantity":float(row.quantity),"payment_method":row.payment_method,"source":row.source}}

@app.post("/api/transactions/scan")
async def scan_records(file: UploadFile = File(...), user: User = Depends(current_user)):
    """Extract text from a photographed page/receipt. OCR is optional and must be installed locally."""
    name = (file.filename or "").lower()
    if not name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
        raise HTTPException(415,"Upload a photo (PNG, JPG, WEBP or TIFF). For existing spreadsheets, use CSV import instead.")
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024: raise HTTPException(413,"Image must be smaller than 8 MB.")
    try:
        from PIL import Image
        import pytesseract
        from io import BytesIO as ImageBytes
        img = Image.open(ImageBytes(raw)).convert("RGB")
        extracted = pytesseract.image_to_string(img)
    except ImportError:
        raise HTTPException(503,"Photo scanning needs Pillow, pytesseract and the Tesseract OCR program. Install the optional scan requirements and Tesseract, or use voice/text/CSV import.")
    except Exception:
        raise HTTPException(422,"Could not read this image. Try a clear, well-lit photo taken straight-on.")
    lines = [line.strip(" •\t") for line in extracted.splitlines() if line.strip()]
    parsed=[]
    for line in lines:
        draft=parse_transaction_text(line)
        if draft.get("amount") and draft.get("description"):
            draft["source"]="scan"
            parsed.append({k:draft[k] for k in ["transaction_date","transaction_type","description","category","amount","quantity","payment_method","source"]})
    return {"message":"Text extracted. OCR can misread handwriting, dates and amounts. Review each suggested row before confirming.","extracted_text":"\n".join(lines)[:12000],"lines":lines[:100],"preview":parsed[:100],"source":"scan"}

@app.post("/api/transactions/import-csv")
async def import_transactions_csv(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    import csv
    from io import StringIO
    if not (file.filename or "").lower().endswith(".csv"): raise HTTPException(415,"Please upload a CSV file.")
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024: raise HTTPException(413,"CSV must be smaller than 2 MB.")
    try: rows = list(csv.DictReader(StringIO(raw.decode("utf-8-sig"))))
    except Exception: raise HTTPException(422,"Could not read the CSV. Save it as UTF-8 CSV and try again.")
    if not rows: raise HTTPException(422,"The CSV has no data rows.")
    if len(rows)>1000: raise HTTPException(413,"Import up to 1,000 rows at a time.")
    made=[]; errors=[]
    for i,r in enumerate(rows, start=2):
        low={str(k).strip().lower():v for k,v in r.items() if k}
        try:
            amount=float(str(low.get("amount", low.get("amount (r)", low.get("value", "")))).replace("R","").replace(","," ").replace(" ",""))
            kind=str(low.get("type",low.get("transaction_type","Sale"))).strip().title()
            if kind not in {"Sale","Purchase","Expense","Refund"}: kind="Sale"
            desc=str(low.get("description",low.get("item",low.get("item or description","Imported transaction")))).strip()[:240]
            rawdate=str(low.get("date",low.get("transaction_date",date.today().isoformat()))).strip()[:10]
            date.fromisoformat(rawdate)
            if amount<=0 or not desc: raise ValueError("description/amount missing")
            made.append({"transaction_date":rawdate,"transaction_type":kind,"description":desc,"category":str(low.get("category","Other"))[:60],"amount":amount,"quantity":float(low.get("quantity",1) or 1),"payment_method":str(low.get("payment method",low.get("payment_method","Other"))).title()[:40] or "Other"})
        except Exception: errors.append(f"Row {i}: missing/invalid date, description or amount")
    return {"rows_found":len(rows),"valid_count":len(made),"errors":errors[:30],"preview":made[:100],"message":"Preview only. Nothing has been saved yet. Review the rows, then confirm import."}

@app.post("/api/transactions/import-confirm")
def confirm_import(payload: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows=payload.get("rows",[])
    source=payload.get("source", "csv")
    source=source if source in {"csv","scan"} else "csv"
    if not isinstance(rows,list) or not rows or len(rows)>1000: raise HTTPException(422,"Choose between 1 and 1,000 reviewed rows.")
    created=0
    for item in rows:
        try:
            d=date.fromisoformat(str(item["transaction_date"]))
            kind=str(item["transaction_type"])
            amount=float(item["amount"]); qty=float(item.get("quantity",1))
            desc=str(item["description"]).strip()
            if d>date.today() or kind not in {"Sale","Purchase","Expense","Refund"} or amount<=0 or qty<=0 or not desc: continue
            pay=str(item.get("payment_method","Other")); pay=pay if pay in {"Cash","Card","Bank Transfer","E-wallet","Credit","Other"} else "Other"
            db.add(TransactionRecord(user_id=user.id,transaction_date=d.isoformat(),transaction_type=kind,description=desc[:240],category=str(item.get("category","Other"))[:60],amount=round(amount*100),quantity=str(qty),payment_method=pay,source=source)); created+=1
        except Exception: continue
    db.commit()
    return {"message":f"Imported {created} reviewed transaction(s).","imported":created}

@app.get("/api/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, data = profile_data(db, user)
    plan = db.scalar(select(BusinessPlan).where(BusinessPlan.user_id == user.id))
    if user.role == "new_entrepreneur" and not (p and p.completed and plan):
        raise HTTPException(403, "Your dashboard is locked. Complete the guided profile and generate your business plan first.")
    labels = {"business_owner":"Business owner dashboard", "new_entrepreneur":"Business growth dashboard", "supplier":"Supplier dashboard", "delivery_partner":"Delivery partner dashboard"}
    actions = {
      "business_owner":["Record sales and expenses","Manage stock","Find local suppliers","Prepare business reports and tender documents"],
      "new_entrepreneur":["Review your business plan","Track sales and expenses","Build six-month records","Explore local tenders and formal markets"],
      "supplier":["Manage product catalogue","Review incoming orders","Confirm prices and availability","Contact buyers"],
      "delivery_partner":["View delivery requests","Confirm pickup and drop-off","Share location during delivery","Update delivery status"]}
    return {"title":labels[user.role],"role":user.role,"profile":data,"actions":actions[user.role],"plan_ready":bool(plan)}
