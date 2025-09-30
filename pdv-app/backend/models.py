from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


# =========================
# Users
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="operator")
    created_at = Column(DateTime, server_default=func.now())


# =========================
# Products
# =========================
class Product(Base):
    __tablename__ = "products"

    id      = Column(Integer, primary_key=True, index=True)
    sku     = Column(String(64),  nullable=False, index=True)
    name    = Column(String(255), nullable=False)
    variant = Column(String(120), nullable=True)
    price   = Column(Float, default=0.0)

    # NOVO: imagem principal do produto (usada também no PDV)
    image_url = Column(String, nullable=True)

    # Nunca permitir mesmo (sku, name)
    __table_args__ = (
        UniqueConstraint("sku", "name", name="uq_products_sku_name"),
    )

    # Relacionamento explícito com variações
    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant = Column(String(120), nullable=False)      # ex: P, M, G, UN, KG
    stock = Column(Integer, default=0, nullable=False) # estoque atual
    min_stock = Column(Integer, default=0, nullable=False)
    price = Column(Float, nullable=True)               # pode sobrepor o preço do produto
    image_url = Column(String, nullable=True)          # imagem específica da variação (opcional)

    product = relationship("Product", back_populates="variants")


# =========================
# Clients
# =========================
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)


# =========================
# Sales
# =========================
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

    items = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
    )


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
