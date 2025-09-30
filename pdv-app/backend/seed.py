from .database import SessionLocal, engine
from .models import Product, Client, User
from sqlalchemy.orm import Session
from .database import Base
import logging
logging.getLogger("passlib").setLevel(logging.ERROR)

# cria as tabelas antes de semear
Base.metadata.create_all(bind=engine)

def main():
    db: Session = SessionLocal()
    try:
        # Usuário admin padrão (se não existir)
        if not db.query(User).filter_by(username="admin").first():
            from .crud import create_user
            create_user(db, username="admin", password="admin", role="admin", full_name="Administrador")

        # Clientes demo
        for nm in ["Cliente Padrão", "João Silva"]:
            if not db.query(Client).filter_by(name=nm).first():
                db.add(Client(name=nm))

        # Produtos demo
        demo = [
            ("00011", "Coca-Cola Lata 350ml", 5.50),
            ("00012", "Água Mineral 500ml", 3.00),
            ("00013", "Salgadinho 45g", 7.90),
        ]
        for sku, name, price in demo:
            if not db.query(Product).filter_by(sku=sku).first():
                db.add(Product(sku=sku, name=name, variant="UN", price=price))

        db.commit()
        print("Seed OK (admin/admin, clientes e produtos).")
    finally:
        db.close()

if __name__ == "__main__":
    main()
