from datetime import date

def money(value):
    try: return f"R{float(value):,.2f}"
    except (ValueError, TypeError): return "Not provided"

def build_plan(d):
    name = d.get("business_name") or "Business to be named"
    product = d.get("product_service") or "Product/service to be confirmed"
    customer = d.get("target_customers") or "Customers to be validated locally"
    area = d.get("area") or "Area to be confirmed"
    budget = float(d.get("starting_budget") or 0)
    price = float(d.get("selling_price") or 0)
    cost = float(d.get("unit_cost") or 0)
    units = int(float(d.get("expected_units_month") or 0))
    revenue = price * units
    variable = cost * units
    fixed = float(d.get("monthly_fixed_costs") or 0)
    profit = revenue - variable - fixed
    funding = max(0, float(d.get("funding_needed") or 0))
    return {
      "title": f"Business Plan: {name}", "created": date.today().isoformat(), "business_name": name,
      "executive_summary": f"{name} is a proposed small business operating in {area}. It plans to offer {product} to {customer}. This plan is based on information supplied by the entrepreneur and includes assumptions that should be validated before investing or applying for finance.",
      "offer": product, "customers": customer, "area": area,
      "customer_problem": d.get("customer_problem", "Interview potential customers to confirm the problem, demand and current alternatives."),
      "marketing": d.get("marketing_plan", "Start with referrals, WhatsApp Business, local community groups and a simple record of customer enquiries. Ask permission before adding customers to marketing lists."),
      "operations": d.get("operations", "Confirm suppliers, lead times, quality, transport, storage and a daily record-keeping routine before launch."),
      "budget": money(budget), "funding_needed": money(funding), "price": money(price), "unit_cost": money(cost),
      "monthly_units": units, "monthly_revenue": money(revenue), "monthly_variable_cost": money(variable), "monthly_fixed_costs": money(fixed), "estimated_monthly_surplus": money(profit),
      "financial_note": "This is a simple planning estimate, not a guarantee or audited forecast. It excludes any costs you have not entered, including tax, owner drawings, loan repayments, spoilage, fees and seasonal changes.",
      "risks": d.get("risks", "Main risks to check: customer demand may be lower than expected; supplier prices can change; cash flow may be uneven; permits or sector-specific rules may apply."),
      "milestones": ["Speak to at least 10 likely customers and record what they would buy and at what price.", "Get written price and availability quotes from at least 2 suppliers.", "Test with a small batch before committing the full budget.", "Record every sale, expense, stock movement and supplier payment.", "Review actual results after 30 days and revise the plan."],
      "documents": ["Identity/contact details, where required by the receiving institution", "Business address or proof of operating location, if required", "Business registration documents, if already registered or required for the opportunity", "Bank account details in the business owner's name where required", "Six-month sales/expense records and bank statements, if available", "Supplier quotations and customer demand evidence", "Tax, sector permits or compliance documents where applicable", "Tender-specific forms, declarations and eligibility evidence listed in the official notice"],
      "disclaimer": "MALI MODE helps organise information; it does not certify facts, register the business, guarantee funding, or submit a tender automatically. Check official requirements and have the owner review every statement before sharing it."
    }
