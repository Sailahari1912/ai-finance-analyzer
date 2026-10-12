from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field

class NormalizedTransaction(BaseModel):
    date: date
    raw_description: str
    amount: float = Field(
        ..., 
        description="Negative for outgoing expenses, positive for deposits/income"
    )
    merchant: Optional[str] = None
    category: Optional[str] = None
    account_tail: Optional[str] = None

class CategorizedItem(BaseModel):
    index: int = Field(..., description="Original index from the batch")
    clean_merchant: str = Field(..., description="Cleaned merchant brand name (e.g., Starbucks, Amazon, Shell)")
    category: str = Field(..., description="Standard category: Food & Dining, Groceries, Shopping, Transportation, Utilities, Income, Entertainment, or Other")
    is_recurring: bool = Field(..., description="True if likely a subscription or regular bill")

class BatchCategorizationResponse(BaseModel):
    items: List[CategorizedItem]