# scripts/add_image_columns.py
from backend.database import engine

SQLS = [
    "ALTER TABLE products ADD COLUMN image_url TEXT",
    "ALTER TABLE product_variants ADD COLUMN image_url TEXT",
]

with engine.begin() as conn:
    for sql in SQLS:
        try:
            conn.exec_driver_sql(sql)
            print(f"OK -> {sql}")
        except Exception as e:
            # Já existe / versão do SQLite etc. (seguimos em frente)
            print(f"SKIP -> {sql} ({e})")
