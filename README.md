# Portfolio Manager

Enter an amount in ₹ and a risk profile, get back an optimized portfolio
allocation across a diversified basket of NSE-listed ETFs — computed with
real Modern Portfolio Theory (mean-variance optimization) over 5 years of
historical prices. Educational tool, not financial advice.

## Architecture

- `backend/` — Python FastAPI service. Fetches historical prices for a fixed
  Indian ETF universe (`backend/app/universe.py` — Nifty 50, Nifty Next 50,
  Bank/IT sector, Nasdaq 100 for international exposure, G-Sec bonds,
  liquid/cash, gold, silver), computes expected returns and a shrunk
  covariance matrix, and solves three efficient-frontier portfolios
  (Conservative / Moderate / Aggressive) with
  [PyPortfolioOpt](https://pyportfolioopt.readthedocs.io/). The risk-free
  rate defaults to ~6.5% (approx. short-term Indian G-Sec yield).
- `frontend/` — Next.js (App Router) dashboard. The UI calls a same-origin
  API route (`/api/portfolio`) which proxies to the FastAPI backend, so the
  browser never needs CORS.

## Running locally

**Terminal 1 — backend**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend**

```powershell
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000.

## Notes / deviations from the original plan

- **Market data source**: the plan called for the `yfinance` package, but at
  build time Yahoo Finance's cookie/crumb authentication endpoint
  (`/v1/test/getcrumb`) was rate-limiting requests, which made every
  `yfinance.download()` call fail with a JSON decode error. The underlying
  chart data endpoint (`query1.finance.yahoo.com/v8/finance/chart/{ticker}`)
  works reliably without that crumb dance, so `backend/app/data.py` fetches
  from it directly instead of going through the `yfinance` package. Same
  data source (Yahoo Finance), same "free, no API key" property — just a
  more reliable path to it. If Yahoo changes this endpoint, `data.py` is the
  only file that needs to change.
- Prices are cached in-memory for 60 minutes (`CACHE_TTL_MINUTES` in
  `backend/app/config.py`) with a startup warm-up fetch, so requests after
  the first are fast and don't re-hit Yahoo Finance each time.

## Configuration

- `backend/.env` (optional): `RISK_FREE_RATE`, `CACHE_TTL_MINUTES`,
  `LOOKBACK_YEARS`, `MAX_WEIGHT`.
- `frontend/.env.local`: `PYTHON_BACKEND_URL` (defaults to
  `http://localhost:8000`).
