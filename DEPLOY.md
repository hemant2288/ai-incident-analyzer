# Deploy & access your live API

## Why `http://localhost:8000/docs` does not work after deploy

| URL | When it works |
|-----|----------------|
| `http://localhost:8000/docs` | **Only on your PC** while you run `uvicorn` locally |
| `https://YOUR-APP.onrender.com/docs` | After you deploy to Render/Railway/etc. |

`localhost` always means **this computer**. It is never your cloud server.

---

## Quick deploy on Render (recommended)

1. Sign in at [render.com](https://render.com) with GitHub.
2. **New → Blueprint** (or Web Service) → connect `hemant2288/ai-incident-analyzer`.
3. Render reads `render.yaml` automatically, or set manually:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in the dashboard:
   - `OPENAI_API_KEY` (optional)
   - `SLACK_WEBHOOK_URL` (optional)
5. Wait for **Live** status. Copy your URL, e.g.  
   `https://ai-incident-analyzer-xxxx.onrender.com`

### Use your live URL

| Local (dev) | Deployed (production) |
|-------------|------------------------|
| http://localhost:8000/ | https://YOUR-APP.onrender.com/ |
| http://localhost:8000/docs | https://YOUR-APP.onrender.com/docs |
| http://localhost:8000/api/health/detail | https://YOUR-APP.onrender.com/api/health/detail |

### Test deployed API

```bash
curl https://YOUR-APP.onrender.com/

python simulate_advanced_alert.py --base-url https://YOUR-APP.onrender.com
```

---

## Railway

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub.
2. Uses `Procfile` start command.
3. Add env vars → generate public domain → open `https://YOUR-APP.up.railway.app/docs`.

---

## GitHub Pages will NOT work

This project is a **Python FastAPI server**. GitHub Pages only hosts static HTML.  
You need Render, Railway, Fly.io, or a VPS.

---

## Slack buttons on production

Set Slack **Interactivity** request URL to:

`https://YOUR-APP.onrender.com/webhook/slack-actions`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Deploy build fails | Use Python **3.11**; check Render logs |
| Site sleeps (free tier) | First request after idle takes ~30s — wait and refresh |
| 502 / crash on start | Set start command with `$PORT`, not hardcoded `8000` |
| Still using localhost | Replace with your Render/Railway URL everywhere |
