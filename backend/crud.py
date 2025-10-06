from __future__ import annotations

import re
from typing import Optional, List, Tuple

from passlib.context import CryptContext
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from . import models, schemas

# =========================
# Senhas
# =========================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password required")
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


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
    u = models.User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        full_name=full_name,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def _perms_list_to_str(role: str, permissions: list[str] | None) -> str:
    if (role or "operator") == "admin":
        return "dashboard,vendas,produtos,administracao"
    perms = permissions or ["vendas"]
    seen = set()
    norm: list[str] = []
    for p in (x.strip().lower() for x in perms if x):
        if p not in seen:
            seen.add(p)
            norm.append(p)
    return ",".join(norm)

def create_user_with_permissions(
    db: Session,
    username: str,
    password: str,
    role: str,
    full_name: str | None,
    permissions: list[str] | None,
) -> models.User:
    if get_user_by_username(db, username):
        raise ValueError("Usuário já existe.")
    perms_str = _perms_list_to_str(role or "operator", permissions)
    u = models.User(
        username=username,
        full_name=full_name,
        role=role or "operator",
        permissions=perms_str,
        password_hash=hash_password(password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def update_user(db: Session, user_id: int, data: schemas.UserUpdate):
    """Atualiza apenas os campos enviados no payload (sem estourar AttributeError)."""
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        return None

    # Compatível com Pydantic v1 e v2
    try:
        incoming = data.model_dump(exclude_unset=True)  # pydantic v2
    except Exception:
        incoming = data.dict(exclude_unset=True)        # pydantic v1

    # username (se seu schema permitir alterar)
    if "username" in incoming and incoming["username"] is not None:
        u.username = incoming["username"]

    if "full_name" in incoming and incoming["full_name"] is not None:
        u.full_name = incoming["full_name"]

    if "role" in incoming and incoming["role"] is not None:
        u.role = incoming["role"]

    if "password" in incoming and incoming["password"]:
        u.password_hash = hash_password(incoming["password"])

    if "permissions" in incoming:
        perms = incoming.get("permissions")
        u.permissions = _perms_list_to_str(u.role, perms)

    db.commit()
    db.refresh(u)
    return u

def delete_user(db: Session, user_id: int):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        return False
    db.delete(u)
    db.commit()
    return True

def list_users(db: Session, limit: int = 50):
    return db.query(models.User).order_by(models.User.username.asc()).limit(limit).all()


# =========================
# Helpers / Normalização
# =========================

def _normalize(s: str | None) -> str:
    return (s or "").strip()

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
        db.refresh(product)

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
    if not p:
        return None

    if data.image_url is not None:
        p.image_url = data.image_url

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
