from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from .database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    variant = Column(String(120), nullable=True)
    price = Column(Float, default=0.0)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=True)
    payment = Column(String(50), nullable=False)
    installments = Column(Integer, default=1)
    discount_value = Column(Float, default=0.0)
    discount_pct = Column(Float, default=0.0)
    freight = Column(Float, default=0.0)
    received = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())

    items = relationship("SaleItem", back_populates="sale")

class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False, index=True)
    sku = Column(String(64), nullable=True)
    name = Column(String(255), nullable=False)
    variant = Column(String(120), nullable=True)
    qty = Column(Integer, default=1)
    price = Column(Float, default=0.0)

    sale = relationship("Sale", back_populates="items")
