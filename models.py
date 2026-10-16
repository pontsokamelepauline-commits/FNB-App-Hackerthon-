from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, BigInteger, String, Text, func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(160), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(40), nullable=False)
    role = Column(String(40), nullable=False)
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    verification_token_hash = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    data_json = Column(Text, default="{}", nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BusinessPlan(Base):
    __tablename__ = "business_plans"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_json = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class TransactionRecord(Base):
    __tablename__ = "transaction_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    transaction_date = Column(String(10), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    description = Column(String(240), nullable=False)
    category = Column(String(60), default="Other", nullable=False)
    amount = Column(BigInteger, nullable=False)  # amount stored in cents to avoid floating-point rounding
    quantity = Column(String(40), default="1", nullable=False)
    payment_method = Column(String(40), default="Other", nullable=False)
    source = Column(String(20), default="typed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
