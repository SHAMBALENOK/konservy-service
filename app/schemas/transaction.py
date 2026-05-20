from .common import TransactionResponse, TransactionCreate
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DepositRequest(BaseModel):
    account_id: int = Field(..., example=1, description="The account ID to deposit funds into")
    amount: float = Field(..., gt=0, example=100.50, description="The amount to deposit")
    description: Optional[str] = Field(None, example="Salary deposit", description="Optional description for the deposit")

class TransferRequest(BaseModel):
    destination_account_id: int = Field(..., example=2, description="The destination account ID")
    amount: float = Field(..., gt=0, example=50.25, description="The amount to transfer")
    description: Optional[str] = Field(None, example="Payment for goods", description="Optional description for the transfer")

class TransactionDetail(TransactionResponse):
    pass