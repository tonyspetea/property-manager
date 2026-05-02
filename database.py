from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum

DATABASE_URL = "sqlite:///./property_manager.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

# Allow larger data storage for images
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA page_size=65536")
    cursor.close()
    
# --- ENUMS ---
class PropertyType(str, enum.Enum):
    house = "house"
    plot = "plot"

class PropertyStatus(str, enum.Enum):
    vacant = "vacant"
    occupied = "occupied"
    for_sale = "for_sale"
    sold = "sold"

class PaymentMethod(str, enum.Enum):
    mpesa = "mpesa"
    cash = "cash"
    bank = "bank"

class SaleStatus(str, enum.Enum):
    available = "available"
    deposit_paid = "deposit_paid"
    installments = "installments"
    completed = "completed"

class MaintenanceStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"

class TitleDeedStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    transferred = "transferred"

class UserRole(str, enum.Enum):
    admin = "admin"
    staff = "staff"

# --- TABLES ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="staff")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    location = Column(String, nullable=False)
    county = Column(String, nullable=False)
    landlord_name = Column(String, nullable=True)
    room_type = Column(String, nullable=True)        # ← ADD THIS
    size_sqft = Column(Float, nullable=True)
    bedrooms = Column(Integer, nullable=True)
    status = Column(String, default="vacant")
    rent_amount = Column(Float, nullable=True)
    sale_price = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)          # ← ADD THIS
    created_at = Column(DateTime, default=datetime.utcnow)
    tenants = relationship("Tenant", back_populates="property")
    maintenance = relationship("Maintenance", back_populates="property")
    
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    id_number = Column(String, nullable=True)
    property_id = Column(Integer, ForeignKey("properties.id"))
    lease_start = Column(Date, nullable=True)
    lease_end = Column(Date, nullable=True)
    monthly_rent = Column(Float, nullable=False)
    deposit_paid = Column(Float, default=0)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    property = relationship("Property", back_populates="tenants")
    payments = relationship("Payment", back_populates="tenant")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    property_id = Column(Integer, ForeignKey("properties.id"))
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False)
    month_paid_for = Column(String, nullable=False)
    mpesa_ref = Column(String, nullable=True)
    payment_method = Column(String, default="mpesa")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="payments")

class PlotSale(Base):
    __tablename__ = "plot_sales"
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"))
    buyer_name = Column(String, nullable=False)
    buyer_phone = Column(String, nullable=False)
    buyer_id_number = Column(String, nullable=True)
    sale_price = Column(Float, nullable=False)
    deposit_paid = Column(Float, default=0)
    balance_remaining = Column(Float, nullable=False)
    status = Column(String, default="deposit_paid")
    title_deed_status = Column(String, default="pending")
    sale_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    installments = relationship("Installment", back_populates="plot_sale")

class Installment(Base):
    __tablename__ = "installments"
    id = Column(Integer, primary_key=True, index=True)
    plot_sale_id = Column(Integer, ForeignKey("plot_sales.id"))
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=True)
    mpesa_ref = Column(String, nullable=True)
    status = Column(String, default="pending")
    plot_sale = relationship("PlotSale", back_populates="installments")

class Maintenance(Base):
    __tablename__ = "maintenance"
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    description = Column(Text, nullable=False)
    priority = Column(String, default="medium")
    status = Column(String, default="open")
    assigned_to = Column(String, nullable=True)
    cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    property = relationship("Property", back_populates="maintenance")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# --- CREATE ALL TABLES ---
def init_db():
    Base.metadata.create_all(bind=engine)
    print("All tables created!")

if __name__ == "__main__":
    init_db()