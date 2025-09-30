import os
import uuid
import logging
from datetime import datetime, date, time, timedelta

from dotenv import load_dotenv
from fastapi import (
    FastAPI, Depends, HTTPException, Header, Response, Query, Path, UploadFile, File
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

# Silenciar ruído do passlib/bcrypt
logging.getLogger("passlib").setLevel(logging.ERROR)

from .database import Base, engine, get_db
from . import models, schemas, crud
from .auth import (
    create_access_token,
    get_current_user,
    require_admin,
    user_from_token_str,
)

load_dotenv()

app = FastAPI(title="PDV API")

# CORS (libera tudo em dev se CORS_ORIGINS não estiver definido)
origins_env = os.getenv("CORS_ORIGINS")
origins = [o.strip() for o in origins_env.split(",")] if origins_env else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pastas de uploads (imagens de produtos) ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PRODUCTS_DIR = os.path.join(UPLOAD_DIR, "products")
os.makedirs(PRODUCTS_DIR, exist_ok=True)

# Servir uploads estaticamente (antes do frontend)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Criação das tabelas
Base.metadata.create_all(bind=engine)

# ---------------------------
#           AUTH
# ---------------------------

@app.post("/api/auth/login")
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    # Busca e valida credenciais (bcrypt seguro tratado no crud)
    user = crud.get_user_by_username(db, payload.username)
    if not user or not crud.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = create_access_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
        },
    }


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(user=Depends(get_current_user)):
    return user


@app.post("/api/auth/register", response_model=schemas.UserOut)
def register(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    # Primeiro usuário pode ser criado sem autenticação (bootstrap)
    if crud.count_users(db) == 0:
        return crud.create_user(
            db,
            username=payload.username,
            password=payload.password,
            role=payload.role or "admin",
            full_name=payload.full_name,
        )

    # Depois, só admin autenticado pode criar
    admin = user_from_token_str(authorization, db)
    if not admin or admin.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem criar usuários após o primeiro.",
        )
    return crud.create_user(
        db,
        username=payload.username,
        password=payload.password,
        role=payload.role or "operator",
        full_name=payload.full_name,
    )

# ---------------------------
#          HEALTH
# ---------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ---------------------------
#      DASHBOARD (período)
# ---------------------------

def _parse_bounds(start: str | None, end: str | None):
    # aceita "YYYY-MM-DD"; se vazio → hoje
    if start and end:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end,   "%Y-%m-%d")
        s = datetime.combine(s.date(), time.min)
        e = datetime.combine(e.date(), time.max)
    else:
        today = date.today()
        s = datetime.combine(today, time.min)
        e = datetime.combine(today, time.max)
    return s, e

@app.get("/api/dashboard/summary")
def dash_summary(
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    s, e = _parse_bounds(start, end)

    orders = (
        db.query(func.count(models.Sale.id))
        .filter(models.Sale.created_at >= s, models.Sale.created_at <= e)
        .scalar()
        or 0
    )

    revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
        .filter(models.Sale.created_at >= s, models.Sale.created_at <= e)
        .scalar()
        or 0.0
    )

    avg_ticket = (revenue / orders) if orders else 0.0

    # faturamento acumulado do mês corrente
    first_day = date(date.today().year, date.today().month, 1)
    # primeiro dia do mês seguinte
    if first_day.month == 12:
        next_first = date(first_day.year + 1, 1, 1)
    else:
        next_first = date(first_day.year, first_day.month + 1, 1)
    # último dia do mês corrente
    last_day = next_first - timedelta(days=1)

    ms = datetime.combine(first_day, time.min)
    me = datetime.combine(last_day, time.max)

    month_revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
        .filter(models.Sale.created_at >= ms, models.Sale.created_at <= me)
        .scalar()
        or 0.0
    )

    return {
        "period": {"start": s.isoformat(), "end": e.isoformat()},
        "kpis": {
            "orders": orders,
            "revenue": revenue,
            "avg_ticket": avg_ticket,
            "month_revenue": month_revenue,
        },
    }

@app.get("/api/dashboard/latest_sales")
def dash_latest_sales(
    start: str | None = None,
    end: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    s, e = _parse_bounds(start, end)
    q = (
        db.query(models.Sale)
        .filter(models.Sale.created_at >= s, models.Sale.created_at <= e)
        .order_by(models.Sale.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "created_at": x.created_at.isoformat(),
                "channel": "PDV",
                "payment": x.payment,
                "total": x.total,
            }
            for x in q
        ]
    }

@app.get("/api/dashboard/top_products")
def dash_top_products(
    start: str | None = None,
    end: str | None = None,
    limit: int = 10,
    db_session: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    s, e = _parse_bounds(start, end)
    it = models.SaleItem
    sa = models.Sale

    rows = (
        db_session.query(
            it.name.label("name"),
            func.coalesce(func.sum(it.qty), 0).label("qty"),
            func.coalesce(func.sum(it.qty * it.price), 0.0).label("revenue"),
        )
        .join(sa, it.sale_id == sa.id)
        .filter(sa.created_at >= s, sa.created_at <= e)
        .group_by(it.name)
        .order_by(func.sum(it.qty).desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {"name": r.name, "qty": int(r.qty or 0), "revenue": float(r.revenue or 0)}
            for r in rows
        ]
    }

@app.get("/api/dashboard/export/sales.csv")
def dash_export_sales_csv(
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    s, e = _parse_bounds(start, end)
    q = (
        db.query(models.Sale)
        .filter(models.Sale.created_at >= s, models.Sale.created_at <= e)
        .order_by(models.Sale.created_at.desc())
        .all()
    )
    lines = ["id,data,pagamento,total"]
    for x in q:
        lines.append(f"{x.id},{x.created_at.isoformat()},{x.payment},{x.total:.2f}")
    csv = "\n".join(lines)
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales.csv"},
    )

# ---------------------------
#          CLIENTS
# ---------------------------

@app.get("/api/clients")
def api_clients(
    limit: int = 50, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    data = (
        db.query(models.Client)
        .order_by(models.Client.name.asc())
        .limit(limit)
        .all()
    )
    return {"items": [{"id": c.id, "name": c.name} for c in data]}

# ---------------------------
#         PRODUCTS
# ---------------------------

# Upload de imagem do produto
@app.post("/api/upload/product-image")
def upload_product_image(
    file: UploadFile = File(...),
    _: models.User = Depends(require_admin),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Formato inválido (use JPG, PNG ou WEBP).")

    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(PRODUCTS_DIR, name)
    with open(path, "wb") as f:
        f.write(file.file.read())

    url = f"/uploads/products/{name}"
    return {"url": url}

# 1) Buscar por SKU/EAN/nome (ESTÁTICA — antes da dinâmica)
@app.get("/api/products/find", response_model=schemas.ProductOut)
def find_product(
    query: str = Query("", max_length=128),   # sem min_length para evitar 422
    db: Session = Depends(get_db),
):
    q = (query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Código inválido. Informe o SKU/EAN/nome.")
    prod = crud.find_product(db, q)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado. Cadastre no inventário primeiro.")
    return prod

# 2) Criar (regra de duplicidade: mesmo sku+name não permitido)
@app.post("/api/products", response_model=schemas.ProductOut)
def create_product(
    p: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    try:
        return crud.create_product_strict(db, p)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

# 3) Listar
@app.get("/api/products")
def list_products(
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    items, total = crud.list_products(db, query=query, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "variant": p.variant,
                "price": p.price,
                "image_url": p.image_url,  # <— incluir imagem no retorno
            }
            for p in items
        ],
        "total": total,
    }

# 4) Obter por ID (DINÂMICA — depois da /find)
@app.get("/api/products/{product_id}", response_model=schemas.ProductOut)
def get_product(
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    p = crud.get_product(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return p

# 5) Atualizar (com regra de duplicidade)
@app.put("/api/products/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int = Path(..., ge=1),
    p: schemas.ProductUpdate = ...,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    try:
        updated = crud.update_product_strict(db, product_id, p)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return updated

# ---------- VARIANTS (NOVO) ----------

@app.get("/api/products/{product_id}/variants", response_model=list[schemas.VariantOut])
def list_variants(
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    p = crud.get_product(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    crud.ensure_legacy_variant_row(db, p)
    # força carregar
    _ = p.variants
    return [schemas.VariantOut.model_validate(v) for v in p.variants]

@app.post("/api/products/{product_id}/variants", response_model=schemas.VariantOut)
def upsert_product_variant(
    product_id: int = Path(..., ge=1),
    payload: schemas.VariantCreate = ...,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    p = crud.get_product(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    pv = crud.upsert_variant(db, product_id, payload)
    return schemas.VariantOut.model_validate(pv)

# ---------------------------
#           SALES
# ---------------------------

@app.post("/api/sales", response_model=schemas.SaleOut)
def create_sale(
    payload: schemas.SaleIn, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    try:
        return crud.create_sale(db, payload)
    except ValueError as e:
        # caso você ative o bloqueio de estoque no crud
        raise HTTPException(status_code=409, detail=str(e))

@app.get("/api/sales")
def list_sales(
    limit: int = 20, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    sales = crud.list_sales(db, limit=limit)
    items = []
    for s in sales:
        items.append(
            {
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
                "items": [
                    {
                        "id": it.id,
                        "sku": it.sku,
                        "name": it.name,
                        "variant": it.variant,
                        "qty": it.qty,
                        "price": it.price,
                    }
                    for it in s.items
                ],
            }
        )
    return {"items": items}

# ---------------------------
#        STATIC (LAST)
# ---------------------------

FRONT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
# Montado por último para não interceptar as rotas /api/*
app.mount("/", StaticFiles(directory=FRONT_DIR, html=True), name="frontend")
