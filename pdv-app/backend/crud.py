from __future__ import annotations

import re
from typing import Optional, List, Tuple

from passlib.context import CryptContext
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from . import models, schemas

# Troca de bcrypt -> pbkdf2_sha256 para evitar erro do backend bcrypt no Windows
# (não há limite de 72 bytes e não depende da lib externa "bcrypt").
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# =========================
# Users
# =========================

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return (
        db.execute(
            select(models.User).where(models.User.username == username)
        ).scalar_one_or_none()
    )

def count_users(db: Session) -> int:
    return db.query(models.User).count()

def create_user(
    db: Session,
    username: str,
    password: str,
    role: str = "operator",
    full_name: str | None = None,
) -> models.User:
    hashed = pwd_context.hash(password)
    u = models.User(
        username=username,
        password_hash=hashed,
        role=role,
        full_name=full_name,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def verify_password(plain: str, hashed: str) -> bool:
    # Com pbkdf2_sha256 não há limite de tamanho e não depende do backend bcrypt
    return pwd_context.verify(plain, hashed)

# =========================
# Helpers / Normalização
# =========================

def _normalize(s: str | None) -> str:
    return (s or "").strip()

# Aceita “00011-P”, “00011 P”, “00011#P”
SKU_VAR_RE = re.compile(r"^\s*(?P<sku>[^\s\-#]+)\s*[-# ]\s*(?P<var>.+?)\s*$")

def parse_sku_and_variant(code: str) -> tuple[str, str | None]:
    code = (code or "").strip()
    m = SKU_VAR_RE.match(code)
    if m:
        return m.group("sku"), m.group("var").strip()
    return code, None

# =========================
# Products / Variants
# =========================

def get_product(db: Session, product_id: int) -> Optional[models.Product]:
    return db.get(models.Product, product_id)

def get_product_by_sku(db: Session, sku: str) -> Optional[models.Product]:
    return (
        db.query(models.Product)
        .filter(models.Product.sku == sku)
        .first()
    )

def get_variant_by_name(
    db: Session, product_id: int, variant: str
) -> Optional[models.ProductVariant]:
    return (
        db.query(models.ProductVariant)
        .filter(
            models.ProductVariant.product_id == product_id,
            models.ProductVariant.variant == variant,
        )
        .first()
    )

def ensure_legacy_variant_row(db: Session, product: models.Product) -> None:
    """
    Para produtos antigos (que só têm Product.variant), cria uma linha em
    product_variants na primeira vez que o produto for tocado.
    """
    if product.variants:
        return
    if product.variant:
        pv = models.ProductVariant(
            product_id=product.id,
            variant=product.variant,
            stock=0,
            min_stock=0,
            price=None,
        )
        db.add(pv)
        db.commit()
        db.refresh(product)  # garante que product.variants seja recarregado

def product_with_variants(db: Session, product: models.Product) -> models.Product:
    _ = product.variants
    return product

def upsert_variant(db: Session, product_id: int, payload: schemas.VariantCreate) -> models.ProductVariant:
    pv = get_variant_by_name(db, product_id, payload.variant)
    if pv:
        pv.stock = payload.stock
        pv.min_stock = payload.min_stock
        pv.price = payload.price
    else:
        pv = models.ProductVariant(
            product_id=product_id,
            variant=payload.variant,
            stock=payload.stock,
            min_stock=payload.min_stock,
            price=payload.price,
        )
        db.add(pv)
    db.commit()
    db.refresh(pv)
    return pv

def find_product(db: Session, query: str) -> Optional[models.Product]:
    """
    Busca por SKU (com ou sem sufixo de variante) ou por nome (ilike).
    Sempre retorna o produto com suas 'variants' carregadas e garante
    a criação da linha “legada” quando necessário.
    """
    q = _normalize(query)
    if not q:
        return None

    sku, _v = parse_sku_and_variant(q)

    p = (
        db.execute(
            select(models.Product).where(models.Product.sku == sku)
        ).scalar_one_or_none()
    )
    if not p:
        p = (
            db.execute(
                select(models.Product).where(
                    or_(
                        models.Product.sku.ilike(f"%{q}%"),
                        models.Product.name.ilike(f"%{q}%"),
                    )
                )
            ).scalar_one_or_none()
        )

    if p:
        ensure_legacy_variant_row(db, p)
        return product_with_variants(db, p)
    return None

def list_products(
    db: Session, query: str | None, limit: int = 50, offset: int = 0
) -> Tuple[List[models.Product], int]:
    qsel = select(models.Product)
    if query:
        qsel = qsel.where(
            or_(
                models.Product.sku.ilike(f"%{query}%"),
                models.Product.name.ilike(f"%{query}%"),
            )
        )
        total = (
            db.query(models.Product)
            .filter(
                or_(
                    models.Product.sku.ilike(f"%{query}%"),
                    models.Product.name.ilike(f"%{query}%"),
                )
            )
            .count()
        )
    else:
        total = db.query(models.Product).count()

    items = (
        db.execute(qsel.order_by(models.Product.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    for p in items:
        ensure_legacy_variant_row(db, p)
        _ = p.variants
    return items, total

def create_product_strict(db: Session, data: schemas.ProductCreate) -> models.Product:
    sku = _normalize(data.sku)
    name = _normalize(data.name)

    exists = (
        db.query(models.Product)
        .filter(
            func.lower(models.Product.sku) == sku.lower(),
            func.lower(models.Product.name) == name.lower(),
        )
        .first()
    )
    if exists:
        raise ValueError("Já existe um produto com este SKU e Nome.")

    p = models.Product(
        sku=sku,
        name=name,
        variant=_normalize(data.variant),
        price=data.price or 0.0,
        image_url=data.image_url,
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    ensure_legacy_variant_row(db, p)
    return p

def update_product(db: Session, product_id: int, data: schemas.ProductUpdate) -> Optional[models.Product]:
    prod = db.get(models.Product, product_id)
    if not prod:
        return None
    if data.sku is not None:
        prod.sku = data.sku
    if data.name is not None:
        prod.name = data.name
    if data.variant is not None:
        prod.variant = _normalize(data.variant)
    if data.price is not None:
        prod.price = data.price
    if data.image_url is not None:
     prod.image_url = data.image_url
    db.commit()
    db.refresh(prod)
    return prod

def update_product_strict(db: Session, product_id: int, data: schemas.ProductUpdate) -> models.Product | None:
    p = db.query(models.Product).get(product_id)
    if data.image_url is not None:
        p.image_url = data.image_url
    if not p:
        return None
    

    new_sku = _normalize(data.sku) if hasattr(data, "sku") and data.sku is not None else p.sku
    new_name = _normalize(data.name) if hasattr(data, "name") and data.name is not None else p.name

    if new_sku.lower() != p.sku.lower() or new_name.lower() != p.name.lower():
        conflict = (
            db.query(models.Product)
            .filter(
                func.lower(models.Product.sku) == new_sku.lower(),
                func.lower(models.Product.name) == new_name.lower(),
                models.Product.id != p.id,
            )
            .first()
        )
        if conflict:
            raise ValueError("Já existe um produto com este SKU e Nome.")

    p.sku = new_sku
    if data.name is not None:
        p.name = new_name
    if data.variant is not None:
        p.variant = _normalize(data.variant)
    if data.price is not None:
        p.price = data.price
    db.commit()
    db.refresh(p)

    ensure_legacy_variant_row(db, p)
    return p

def delete_product(db: Session, product_id: int) -> bool:
    prod = db.get(models.Product, product_id)
    if not prod:
        return False
    db.delete(prod)
    db.commit()
    return True

# =========================
# Sales / Estoque
# =========================

def decrease_stock_for_items(db: Session, items: list[schemas.SaleItemIn]) -> None:
    for it in items:
        prod = get_product_by_sku(db, it.sku)
        if not prod:
            continue

        ensure_legacy_variant_row(db, prod)

        varname = (it.variant or prod.variant or "-").strip()
        pv = get_variant_by_name(db, prod.id, varname)
        if not pv:
            pv = models.ProductVariant(
                product_id=prod.id, variant=varname, stock=0, min_stock=0, price=None
            )
            db.add(pv)
            db.flush()

        # (bloqueio negativo opcional)
        # if pv.stock - it.qty < 0:
        #     raise ValueError(...)

        pv.stock = int(pv.stock) - int(it.qty)

    db.commit()

def create_sale(db: Session, payload: schemas.SaleIn) -> models.Sale:
    decrease_stock_for_items(db, payload.items)

    sale = models.Sale(
        client_name=payload.client_name,
        payment=payload.payment,
        installments=payload.installments,
        discount_value=payload.discount_value,
        discount_pct=payload.discount_pct,
        freight=payload.freight,
        received=payload.received,
        subtotal=payload.subtotal,
        total=payload.total,
    )
    db.add(sale)
    db.flush()

    for it in payload.items:
        db.add(
            models.SaleItem(
                sale_id=sale.id,
                sku=it.sku,
                name=it.name,
                variant=it.variant,
                qty=it.qty,
                price=it.price,
            )
        )

    db.commit()
    db.refresh(sale)
    return sale

def list_sales(db: Session, limit: int = 20) -> list[models.Sale]:
    return db.query(models.Sale).order_by(models.Sale.id.desc()).limit(limit).all()
