from .base import Base
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

class TransactionType(enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    transaction_type = Column(String, nullable=False)  # Using String for simplicity, but could be Enum
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="completed", nullable=False)  # e.g., completed, pending, failed
    transaction_type_details = Column(JSON, nullable=True)  # For complex transfer details (e.g., source/destination account IDs)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="transactions")