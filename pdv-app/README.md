# PDV — Frontend acessível + Backend FastAPI (sem Docker)

Este projeto entrega um **PDV web/local** inspirado no layout da imagem, com **modo Dark/Light**, acessibilidade (atalhos, ARIA, foco visível), e **integração de backend (Python/FastAPI + SQLAlchemy)** usando SQLite local por padrão e pronto para escalar para Postgres na nuvem.

## Estrutura de pastas

```
pdv-app/
├─ frontend/               # HTML/CSS/JS acessíveis e responsivos
│  ├─ index.html
│  ├─ styles.css
│  ├─ app.js
│  └─ assets/
│     └─ logo.svg
├─ backend/                # API FastAPI (Python) + ORM
│  ├─ app.py
│  ├─ database.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ crud.py
│  ├─ requirements.txt
│  └─ .env.example
└─ README.md
```

## Como rodar (local)

1) **Backend (API)**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # edite se quiser
uvicorn app:app --reload
```

2) **Frontend**
- Acesse http://127.0.0.1:8000/ (o backend já serve o `index.html`).

## Produção / Cloud

- Troque `DATABASE_URL` no `.env` para PostgreSQL (RDS, Aurora, etc.).
- Rode `uvicorn`/`gunicorn` atrás de um **reverse proxy** (Nginx) com TLS.
- Ative CORS apontando `CORS_ORIGINS` para seu domínio.
- Para escalar horizontalmente, use um banco gerenciado e um storage de sessão (se introduzir autenticação stateful).

## Acessibilidade

- **Contraste** alto, foco visível, labels em todos inputs.
- **Atalhos**: `Alt+D` alterna tema; `Ctrl+Backspace` limpa itens; `Enter` adiciona item.
- **ARIA**: landmarks, estados `aria-selected`, rotulagem nas ações.

## Observações

- O frontend funciona mesmo sem API (modo demonstração), mas **salvar venda** exige backend rodando.
- Evitei frameworks pesados no front para manter **acessível e simples**.
