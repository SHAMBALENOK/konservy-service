from .common import AccountResponse, AccountCreate
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UpdateAccount(BaseModel):
    balance: Optional[float] = Field(None, example=1500.75)
    is_active: Optional[bool] = Field(None, example=True)

class AccountDetail(AccountResponse):
    pass