# PDV — Login + CRUD (usando pasta `pdv-app`)
Como rodar no PowerShell (Windows):
1) `cd .\pdv-app\backend`
2) `python -m venv .venv`
3) Se der erro de política: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
4) `.\.venv\Scripts\Activate.ps1`
5) `python -m pip install --upgrade pip`
6) `pip install -r requirements.txt`
7) `Copy-Item .env.example .env`
8) `cd ..` (volte para a raiz do projeto)
9) `python -m backend.seed`
10) `python -m uvicorn backend.app:app --reload`
Abra: http://127.0.0.1:8000 (login: admin / admin, se rodou o seed)
