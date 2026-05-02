from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, init_db, User, Property, Tenant, Payment, PlotSale, Installment, Maintenance, Expense
from jose import JWTError, jwt
from datetime import datetime, timedelta, date
from pydantic import BaseModel
from typing import Optional, List
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import hashlib
import secrets

app = FastAPI(title="Gandwi Agencies", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

SECRET_KEY = "property-manager-secret-key-2024"
ALGORITHM = "HS256"

def create_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(hours=24)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
# --- AUTH HELPERS ---


def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(plain, hashed):
    try:
        salt, hash_val = hashed.split(":")
        return hashlib.sha256((plain + salt).encode()).hexdigest() == hash_val
    except:
        return False
# --- SCHEMAS ---
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "staff"

class UserLogin(BaseModel):
    email: str
    password: str

class PropertyCreate(BaseModel):
    name: str
    type: str
    location: str
    county: str
    landlord_name: Optional[str] = None
    room_type: Optional[str] = None      # ← ADD THIS
    size_sqft: Optional[float] = None
    bedrooms: Optional[int] = None
    status: str = "vacant"
    rent_amount: Optional[float] = None
    sale_price: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[str] = None      # ← ADD THIS

class TenantCreate(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    id_number: Optional[str] = None
    property_id: int
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    monthly_rent: float
    deposit_paid: float = 0

class PaymentCreate(BaseModel):
    tenant_id: int
    property_id: int
    amount: float
    payment_date: str
    month_paid_for: str
    mpesa_ref: Optional[str] = None
    payment_method: str = "mpesa"
    notes: Optional[str] = None

class PlotSaleCreate(BaseModel):
    property_id: int
    buyer_name: str
    buyer_phone: str
    buyer_id_number: Optional[str] = None
    sale_price: float
    deposit_paid: float = 0
    status: str = "deposit_paid"
    title_deed_status: str = "pending"
    sale_date: Optional[str] = None
    notes: Optional[str] = None

class MaintenanceCreate(BaseModel):
    property_id: int
    tenant_id: Optional[int] = None
    description: str
    priority: str = "medium"
    assigned_to: Optional[str] = None
    cost: Optional[float] = None

class ExpenseCreate(BaseModel):
    property_id: Optional[int] = None
    category: str
    amount: float
    date: str
    description: Optional[str] = None

# --- AUTH ROUTES ---
@app.post("/api/auth/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created", "id": new_user.id}

@app.post("/api/auth/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": user.email, "role": user.role, "name": user.name})
    return {"token": token, "name": user.name, "role": user.role}

# --- PROPERTY ROUTES ---
@app.get("/api/properties")
def get_properties(db: Session = Depends(get_db)):
    return db.query(Property).all()

@app.post("/api/properties")
def create_property(prop: PropertyCreate, db: Session = Depends(get_db)):
    data = prop.model_dump()
    new_prop = Property(
        name=data['name'],
        type=data['type'],
        location=data['location'],
        county=data['county'],
        landlord_name=data.get('landlord_name'),
        room_type=data.get('room_type'),
        size_sqft=data.get('size_sqft'),
        bedrooms=data.get('bedrooms'),
        status=data.get('status', 'vacant'),
        rent_amount=data.get('rent_amount'),
        sale_price=data.get('sale_price'),
        description=data.get('description'),
        image_url=data.get('image_url'),
    )
    db.add(new_prop)
    db.commit()
    db.refresh(new_prop)
    return new_prop

@app.put("/api/properties/{prop_id}")
def update_property(prop_id: int, prop: PropertyCreate, db: Session = Depends(get_db)):
    existing = db.query(Property).filter(Property.id == prop_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Property not found")
    data = prop.model_dump()
    existing.name = data['name']
    existing.type = data['type']
    existing.location = data['location']
    existing.county = data['county']
    existing.landlord_name = data.get('landlord_name')
    existing.room_type = data.get('room_type')
    existing.size_sqft = data.get('size_sqft')
    existing.bedrooms = data.get('bedrooms')
    existing.status = data.get('status', 'vacant')
    existing.rent_amount = data.get('rent_amount')
    existing.sale_price = data.get('sale_price')
    existing.description = data.get('description')
    if data.get('image_url'):
        existing.image_url = data.get('image_url')
    db.commit()
    db.refresh(existing)
    return existing

@app.delete("/api/properties/{prop_id}")
def delete_property(prop_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    db.delete(prop)
    db.commit()
    return {"message": "Deleted"}

# --- TENANT ROUTES ---
@app.get("/api/tenants")
def get_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).all()

@app.post("/api/tenants")
def create_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    data = tenant.dict()
    if data.get("lease_start"):
        data["lease_start"] = datetime.strptime(data["lease_start"], "%Y-%m-%d").date()
    if data.get("lease_end"):
        data["lease_end"] = datetime.strptime(data["lease_end"], "%Y-%m-%d").date()
    new_tenant = Tenant(**data)
    db.add(new_tenant)
    prop = db.query(Property).filter(Property.id == tenant.property_id).first()
    if prop:
        prop.status = "occupied"
    db.commit()
    db.refresh(new_tenant)
    return new_tenant

@app.put("/api/tenants/{tenant_id}")
def update_tenant(tenant_id: int, tenant: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Tenant not found")
    data = tenant.model_dump()
    existing.full_name = data['full_name']
    existing.phone = data['phone']
    existing.email = data.get('email')
    existing.id_number = data.get('id_number')
    existing.property_id = data['property_id']
    existing.monthly_rent = data['monthly_rent']
    existing.deposit_paid = data.get('deposit_paid', 0)
    if data.get('lease_start'):
        existing.lease_start = datetime.strptime(data['lease_start'], "%Y-%m-%d").date()
    if data.get('lease_end'):
        existing.lease_end = datetime.strptime(data['lease_end'], "%Y-%m-%d").date()
    else:
        existing.lease_end = None
    db.commit()
    db.refresh(existing)
    return existing

@app.delete("/api/tenants/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()
    return {"message": "Deleted"}

# --- PAYMENT ROUTES ---
@app.get("/api/payments")
def get_payments(db: Session = Depends(get_db)):
    return db.query(Payment).all()

@app.post("/api/payments")
def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    data = payment.dict()
    data["payment_date"] = datetime.strptime(data["payment_date"], "%Y-%m-%d").date()
    new_payment = Payment(**data)
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment

# --- PLOT SALES ROUTES ---
@app.get("/api/plot-sales")
def get_plot_sales(db: Session = Depends(get_db)):
    return db.query(PlotSale).all()

@app.post("/api/plot-sales")
def create_plot_sale(sale: PlotSaleCreate, db: Session = Depends(get_db)):
    data = sale.dict()
    data["balance_remaining"] = data["sale_price"] - data["deposit_paid"]
    if data.get("sale_date"):
        data["sale_date"] = datetime.strptime(data["sale_date"], "%Y-%m-%d").date()
    new_sale = PlotSale(**data)
    db.add(new_sale)
    prop = db.query(Property).filter(Property.id == sale.property_id).first()
    if prop:
        prop.status = "sold" if data["balance_remaining"] == 0 else "for_sale"
    db.commit()
    db.refresh(new_sale)
    return new_sale

@app.put("/api/plot-sales/{sale_id}")
def update_plot_sale(sale_id: int, sale: PlotSaleCreate, db: Session = Depends(get_db)):
    existing = db.query(PlotSale).filter(PlotSale.id == sale_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Sale not found")
    data = sale.dict()
    data["balance_remaining"] = data["sale_price"] - data["deposit_paid"]
    for key, value in data.items():
        setattr(existing, key, value)
    db.commit()
    return existing

# --- MAINTENANCE ROUTES ---
@app.get("/api/maintenance")
def get_maintenance(db: Session = Depends(get_db)):
    return db.query(Maintenance).all()

@app.post("/api/maintenance")
def create_maintenance(item: MaintenanceCreate, db: Session = Depends(get_db)):
    new_item = Maintenance(**item.dict())
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@app.put("/api/maintenance/{item_id}")
def update_maintenance(item_id: int, item: MaintenanceCreate, db: Session = Depends(get_db)):
    existing = db.query(Maintenance).filter(Maintenance.id == item_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in item.dict().items():
        setattr(existing, key, value)
    db.commit()
    return existing

# --- EXPENSES ROUTES ---
@app.get("/api/expenses")
def get_expenses(db: Session = Depends(get_db)):
    return db.query(Expense).all()

@app.post("/api/expenses")
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    data = expense.dict()
    data["date"] = datetime.strptime(data["date"], "%Y-%m-%d").date()
    new_expense = Expense(**data)
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense

# --- DASHBOARD SUMMARY ---
@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    total_properties = db.query(Property).count()
    occupied = db.query(Property).filter(Property.status == "occupied").count()
    vacant = db.query(Property).filter(Property.status == "vacant").count()
    total_tenants = db.query(Tenant).filter(Tenant.status == "active").count()
    current_month = datetime.utcnow().strftime("%Y-%m")
    monthly_income = db.query(Payment).filter(
        Payment.month_paid_for.startswith(current_month)
    ).all()
    total_income = sum(p.amount for p in monthly_income)
    plot_sales = db.query(PlotSale).all()
    total_plot_revenue = sum(s.deposit_paid for s in plot_sales)
    open_maintenance = db.query(Maintenance).filter(
        Maintenance.status == "open"
    ).count()
    recent_payments = db.query(Payment).order_by(
        Payment.created_at.desc()
    ).limit(5).all()
    return {
        "total_properties": total_properties,
        "occupied": occupied,
        "vacant": vacant,
        "occupancy_rate": round((occupied / total_properties * 100) if total_properties > 0 else 0, 1),
        "total_tenants": total_tenants,
        "monthly_income": total_income,
        "total_plot_revenue": total_plot_revenue,
        "open_maintenance": open_maintenance,
        "recent_payments": [
            {"id": p.id, "amount": p.amount, "month": p.month_paid_for,
             "method": p.payment_method, "mpesa_ref": p.mpesa_ref}
            for p in recent_payments
        ]
    }
from fastapi.responses import StreamingResponse
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

@app.get("/api/receipts/{payment_id}")
def generate_receipt(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    tenant = db.query(Tenant).filter(Tenant.id == payment.tenant_id).first()
    prop = db.query(Property).filter(Property.id == payment.property_id).first()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Header
    story.append(Paragraph("GANDWI AGENCIES", ParagraphStyle('title',
        fontSize=18, fontName='Helvetica-Bold', textColor=colors.HexColor('#1B4332'),
        alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph("Official Rent Payment Receipt", ParagraphStyle('sub',
        fontSize=11, fontName='Helvetica', textColor=colors.HexColor('#6B7280'),
        alignment=TA_CENTER, spaceAfter=16)))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#52B788')))
    story.append(Spacer(1, 0.4*cm))

    # Receipt number and date
    receipt_data = [
        ['Receipt No:', f'RCP-{payment.id:04d}', 'Date:', str(payment.payment_date)],
    ]
    t = Table(receipt_data, colWidths=[3.5*cm, 6*cm, 3*cm, 5*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1B4332')),
        ('TEXTCOLOR', (2,0), (2,-1), colors.HexColor('#1B4332')),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # Tenant and property details
    story.append(Paragraph("TENANT DETAILS", ParagraphStyle('section',
        fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1B4332'), spaceAfter=6)))
    details = [
        ['Tenant Name:', tenant.full_name if tenant else 'N/A'],
        ['Phone:', tenant.phone if tenant else 'N/A'],
        ['Property:', prop.name if prop else 'N/A'],
        ['Location:', f"{prop.location}, {prop.county}" if prop else 'N/A'],
        ['Landlord:', prop.landlord_name if prop and prop.landlord_name else 'N/A'],
    ]
    t2 = Table(details, colWidths=[4*cm, 14*cm])
    t2.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#6B7280')),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor('#F9FAFB'), colors.white]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.5*cm))

    # Payment details — handle all methods
    method_display = payment.payment_method.upper()
    ref_label = "Reference"
    ref_value = payment.mpesa_ref or "N/A"

    if payment.payment_method == "mpesa":
        ref_label = "M-Pesa Reference"
        ref_value = payment.mpesa_ref or "N/A"
    elif payment.payment_method == "cash":
        ref_label = "Received By"
        ref_value = payment.notes or "Cash payment received"
    elif payment.payment_method == "bank":
        ref_label = "Bank Reference"
        ref_value = payment.mpesa_ref or payment.notes or "N/A"

    pay_details = [
        ['Month Paid For:', payment.month_paid_for],
        ['Payment Method:', method_display],
        [ref_label + ':', ref_value],
        ['Notes:', payment.notes or 'N/A'],
    ]
    
    t3 = Table(pay_details, colWidths=[4*cm, 14*cm])
    t3.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#6B7280')),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor('#F9FAFB'), colors.white]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.5*cm))

    # Amount box
    amount_data = [['AMOUNT PAID', f'KES {payment.amount:,.2f}']]
    t4 = Table(amount_data, colWidths=[9*cm, 9*cm])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1B4332')),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 14),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('ROUNDEDCORNERS', [6,6,6,6]),
    ]))
    story.append(t4)
    story.append(Spacer(1, 1*cm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E5E7EB')))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("This is an official receipt generated by PropertyPro Management System.",
        ParagraphStyle('footer', fontSize=9, fontName='Helvetica',
        textColor=colors.HexColor('#9CA3AF'), alignment=TA_CENTER)))
    story.append(Paragraph(f"Generated on {datetime.utcnow().strftime('%d %B %Y at %H:%M')} UTC",
        ParagraphStyle('footer2', fontSize=9, fontName='Helvetica',
        textColor=colors.HexColor('#9CA3AF'), alignment=TA_CENTER)))

    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=receipt_RCP{payment_id:04d}.pdf"})


@app.get("/api/reports/monthly")
def monthly_report(year: int, month: int, db: Session = Depends(get_db)):
    month_str = f"{year}-{month:02d}"
    payments = db.query(Payment).filter(Payment.month_paid_for.startswith(month_str)).all()
    total_rent = sum(p.amount for p in payments)
    expenses = db.query(Expense).filter(
        Expense.date >= date(year, month, 1)
    ).all()
    total_expenses = sum(e.amount for e in expenses)
    tenants = db.query(Tenant).filter(Tenant.status == "active").all()
    properties = db.query(Property).all()
    occupied = [p for p in properties if p.status == "occupied"]
    vacant = [p for p in properties if p.status == "vacant"]
    plots_sold = db.query(PlotSale).filter(PlotSale.status == "completed").all()
    plots_pipeline = db.query(PlotSale).filter(PlotSale.status != "completed").all()
    maintenance_done = db.query(Maintenance).filter(Maintenance.status == "done").all()
    maintenance_cost = sum(m.cost or 0 for m in maintenance_done)

    return {
        "period": month_str,
        "rent_collected": total_rent,
        "total_expenses": total_expenses,
        "maintenance_cost": maintenance_cost,
        "net_revenue": total_rent - total_expenses,
        "payments_count": len(payments),
        "active_tenants": len(tenants),
        "occupied_properties": len(occupied),
        "vacant_properties": len(vacant),
        "total_properties": len(properties),
        "plots_sold": len(plots_sold),
        "plots_pipeline": len(plots_pipeline),
        "plot_revenue": sum(s.deposit_paid for s in plots_sold),
        "payments": [{"tenant_id": p.tenant_id, "amount": p.amount,
                      "method": p.payment_method, "mpesa_ref": p.mpesa_ref} for p in payments],
        "expenses_breakdown": [{"category": e.category, "amount": e.amount,
                                "description": e.description} for e in expenses],
    }

@app.get("/api/reports/yearly")
def yearly_report(year: int, db: Session = Depends(get_db)):
    monthly_data = []
    total_rent = 0
    total_expenses = 0
    for m in range(1, 13):
        month_str = f"{year}-{m:02d}"
        payments = db.query(Payment).filter(Payment.month_paid_for.startswith(month_str)).all()
        expenses = db.query(Expense).filter(
            Expense.date >= date(year, m, 1),
            Expense.date <= date(year, m, 28)
        ).all()
        rent = sum(p.amount for p in payments)
        exp = sum(e.amount for e in expenses)
        total_rent += rent
        total_expenses += exp
        monthly_data.append({"month": month_str, "rent": rent, "expenses": exp, "net": rent - exp})

    properties = db.query(Property).all()
    plots_sold = db.query(PlotSale).filter(PlotSale.status == "completed").all()
    plot_revenue = sum(s.sale_price for s in plots_sold)

    return {
        "year": year,
        "total_rent_collected": total_rent,
        "total_expenses": total_expenses,
        "total_plot_revenue": plot_revenue,
        "gross_revenue": total_rent + plot_revenue,
        "net_revenue": total_rent + plot_revenue - total_expenses,
        "monthly_breakdown": monthly_data,
        "total_properties": len(properties),
        "plots_sold_count": len(plots_sold),
    }

@app.get("/api/public/properties")
def public_properties(db: Session = Depends(get_db)):
    props = db.query(Property).filter(
        Property.status.in_(["vacant", "for_sale"])
    ).all()
    return [{"id": p.id, "name": p.name, "type": p.type, "location": p.location,
             "county": p.county, "room_type": p.room_type, "bedrooms": p.bedrooms,
             "size_sqft": p.size_sqft, "status": p.status, "rent_amount": p.rent_amount,
             "sale_price": p.sale_price, "description": p.description,
             "image_url": p.image_url} for p in props]
    
# --- SERVE FRONTEND ---
@app.get("/")
def serve_frontend():
    return FileResponse("templates/index.html")

@app.get("/{page}")
def serve_page(page: str):
    file_path = f"templates/{page}.html"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return FileResponse("templates/index.html")

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)