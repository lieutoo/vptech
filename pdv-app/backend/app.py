import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .database import Base, engine, get_db
from . import models, schemas, crud

load_dotenv()

app = FastAPI(title="PDV API")

# CORS (opcional via .env)
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Garante que os modelos estão carregados antes de criar as tabelas
Base.metadata.create_all(bind=engine)

# --------------------- ROTAS DA API ---------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/clients")
def api_clients(limit: int = 50, db: Session = Depends(get_db)):
    data = db.query(models.Client).order_by(models.Client.name.asc()).limit(limit).all()
    return {"items": [{"id": c.id, "name": c.name} for c in data]}

@app.get("/api/products/find", response_model=schemas.ProductOut | None)
def find_product(query: str, db: Session = Depends(get_db)):
    prod = crud.find_product(db, query)
    if prod is None:
        raise HTTPException(404, "Produto não encontrado")
    return prod

@app.post("/api/products", response_model=schemas.ProductOut)
def create_product(p: schemas.ProductCreate, db: Session = Depends(get_db)):
    prod = crud.get_or_create_product(db, sku=p.sku, name=p.name, price=p.price, variant=p.variant)
    return prod

@app.post("/api/sales", response_model=schemas.SaleOut)
def create_sale(payload: schemas.SaleIn, db: Session = Depends(get_db)):
    sale = crud.create_sale(db, payload)
    return sale

@app.get("/api/sales")
def list_sales(limit: int = 20, db: Session = Depends(get_db)):
    sales = crud.list_sales(db, limit=limit)
    items = []
    for s in sales:
        items.append({
            "id": s.id,
            "client_name": s.client_name,
            "payment": s.payment,
            "installments": s.installments,
            "discount_value": s.discount_value,
            "discount_pct": s.discount_pct,
            "freight": s.freight,
            "received": s.received,
            "subtotal": s.subtotal,
            "total": s.total,
            "created_at": s.created_at.isoformat(),
            "items": [{
                "id": it.id,
                "sku": it.sku,
                "name": it.name,
                "variant": it.variant,
                "qty": it.qty,
                "price": it.price
            } for it in s.items]
        })
    return {"items": items}

# ----------------- FRONTEND ESTÁTICO (POR ÚLTIMO) -----------------

FRONT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=FRONT_DIR, html=True), name="frontend")
