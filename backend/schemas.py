from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str = "operator"
    permissions: Optional[List[str]] = None

class UserCreate(UserBase):
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"
    full_name: Optional[str] = None
    permissions: list[str] | None = None
    
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    permissions: Optional[List[str]] = None  # NOVO

class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    permissions: List[str] = Field(default_factory=list)  # NOVO
    class Config:
        from_attributes = True

class UserOut(UserBase):
    id: int
    created_at: datetime | None = None
    class Config: from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class ProductBase(BaseModel):
    sku: str
    name: str
    variant: Optional[str] = None
    price: float

class ProductCreate(ProductBase): pass

class ProductCreate(BaseModel):
    sku: str
    name: str
    variant: str | None = None
    price: float
    image_url: str | None = None

class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    name: Optional[str] = None
    variant: Optional[str] = None
    price: Optional[float] = None
    image_url: str | None = None

class VariantOut(BaseModel):
    id: int
    variant: str
    stock: int
    price: float | None = None
    class Config:
        from_attributes = True

class VariantCreate(BaseModel):
    variant: str
    stock: int = 0
    min_stock: int = 0
    price: float | None = None

class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    variant: str | None = None     # legado
    price: float
    variants: list[VariantOut] = []   # <-- NOVO
    image_url: str | None = None
    class Config:
        from_attributes = True


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



