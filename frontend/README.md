# HR Vervoerskosten frontend

Deze React/Vite-interface gebruikt de bestaande Python-backend. Tijdens lokale ontwikkeling stuurt Vite alle `/api`-aanvragen door naar `http://127.0.0.1:8765`.

## Lokaal starten

Start de backend vanuit de projectmap:

```bash
.venv/bin/python scripts/manage_transport.py
```

Start daarna de frontend in een tweede terminal:

```bash
cd frontend
pnpm install
pnpm dev
```

Open vervolgens `http://localhost:8081`.

## Productiebuild controleren

```bash
cd frontend
pnpm build
pnpm preview
```

De statische productiebuild verschijnt in `frontend/dist/`.
