
# Javascript-React Dashboard with postgresql

A dashboard to manage and visualize **multiple YouTube channels** (or Content Owner accounts) using **YouTube Analytics API**.
Includes a **Python backend** for fetching reports and a **React frontend** for interactive charts.

## Features

* Manage multiple channels with separate credentials.
* Supports **Content Owner** and **Channel** modes.
* Auto-export reports:

  * Traffic Sources
  * Geography
* Multiple periods: 7d, 28d, 90d, 365d, lifetime, 2025, 2024.
* React UI with charts, tables, and period selector.

## Project Structure

```
python_backend/   # fetch & export reports (CSV → JS)
react-dashboard/  # frontend visualization
```

## Setup
npm install
### Backend (Python)

```bash
cd python_backend
pip install -r requirements.txt
python yt_analytics_csv.py
```

* Place OAuth credentials JSON in `credentials/`.
* Tokens will be stored in `token/`.
* Reports saved in `reports/<channel>/`.

### Frontend (React)

```bash
cd react-dashboard
npm install
npm start   # or: npm run dev (if using Vite)
```

## Workflow

1. Run backend to fetch reports → CSV.
2. Convert CSV → JS into `src/data/channels/`.
3. Start frontend to view dashboards.

## Notes

* Do not commit credentials or tokens. Add to `.gitignore`.
* If using Content Owner, set:

  ```
  CONTENT_OWNER_ID=YOUR_ID
  ```


## To run rest api
python -m uvicorn main:app --reload
python -m uvicorn src.api.main:app --port 8001
python -m uvicorn bridge:app --reload --port 8765