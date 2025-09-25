from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ProductBase(BaseModel):
    sku: str
    name: str
    variant: Optional[str] = None
    price: float

class ProductCreate(ProductBase):
    pass

class ProductOut(ProductBase):
    id: int
    class Config: from_attributes = True

class ClientOut(BaseModel):
    id: int
    name: str
    class Config: from_attributes = True

class SaleItemIn(BaseModel):
    sku: str | None = None
    name: str
    variant: str | None = None
    qty: int
    price: float

class SaleIn(BaseModel):
    client_name: str | None = None
    payment: str
    installments: int = 1
    discount_value: float = 0
    discount_pct: float = 0
    freight: float = 0
    received: float = 0
    subtotal: float
    total: float
    items: List[SaleItemIn]

class SaleItemOut(SaleItemIn):
    id: int
    class Config: from_attributes = True

class SaleOut(BaseModel):
    id: int
    client_name: str | None
    payment: str
    installments: int
    discount_value: float
    discount_pct: float
    freight: float
    received: float
    subtotal: float
    total: float
    created_at: datetime
    items: List[SaleItemOut]
    class Config: from_attributes = True
