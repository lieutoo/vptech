from sqlalchemy.orm import Session
from . import models, schemas
from typing import Optional, List

def get_or_create_product(db: Session, sku: str, name: str, price: float, variant: Optional[str]=None) -> models.Product:
    prod = db.query(models.Product).filter_by(sku=sku).first()
    if not prod:
        prod = models.Product(sku=sku, name=name, price=price, variant=variant)
        db.add(prod)
        db.commit()
        db.refresh(prod)
    return prod

def find_product(db: Session, query: str) -> Optional[models.Product]:
    q = db.query(models.Product).filter(
        (models.Product.sku == query) | (models.Product.name.ilike(f"%{query}%"))
    ).first()
    return q

def list_clients(db: Session, limit: int=50) -> List[models.Client]:
    return db.query(models.Client).order_by(models.Client.name.asc()).limit(limit).all()

def create_sale(db: Session, payload: schemas.SaleIn) -> models.Sale:
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
    db.add(sale); db.flush()
    for it in payload.items:
        db.add(models.SaleItem(
            sale_id=sale.id, sku=it.sku, name=it.name, variant=it.variant, qty=it.qty, price=it.price
        ))
    db.commit(); db.refresh(sale)
    return sale

def list_sales(db: Session, limit: int=20) -> list[models.Sale]:
    return db.query(models.Sale).order_by(models.Sale.id.desc()).limit(limit).all()
