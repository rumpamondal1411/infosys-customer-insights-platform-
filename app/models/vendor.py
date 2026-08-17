"""
Vendor model.

Captures marketplace seller identity, business details, commission
structure and lifecycle state, per the Week 1 requirement:
"Capture vendor information including business details, product categories,
contact information, commission structures, and operational status."
"""
import enum
from datetime import datetime

from sqlalchemy import String, Float, DateTime, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VendorStatus(str, enum.Enum):
    PENDING = "pending"        # applied, awaiting review
    ACTIVE = "active"          # approved and trading
    SUSPENDED = "suspended"    # temporarily disabled (policy / performance)
    REJECTED = "rejected"      # onboarding application declined


class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    IN_REVIEW = "in_review"
    VERIFIED = "verified"
    FAILED = "failed"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Business details
    business_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    legal_entity_name: Mapped[str] = mapped_column(String(150), nullable=True)
    tax_id: Mapped[str] = mapped_column(String(50), nullable=True, unique=True)
    primary_category: Mapped[str] = mapped_column(String(80), nullable=True)

    # Contact information
    contact_person: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(60), nullable=True)

    # Commission / financial structure
    commission_rate: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)

    # Lifecycle / compliance
    status: Mapped[VendorStatus] = mapped_column(
        Enum(VendorStatus), default=VendorStatus.PENDING, nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.UNVERIFIED, nullable=False
    )
    compliance_notes: Mapped[str] = mapped_column(Text, nullable=True)

    onboarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    suspended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    products = relationship("Product", back_populates="vendor", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="vendor")

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name={self.business_name} status={self.status}>"
