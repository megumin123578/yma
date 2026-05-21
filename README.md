# yt_manage_app

## Yeu cau

- Python 3.11
- Node.js va npm

## Build tree map
```npm run analyze```

### Backend

```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn python_backend.main:app --host 0.0.0.0 --port 8001 --reload
```
## build and production

```powershell
npm --prefix react_dashboard run build
npx serve -s react_dashboard/build -l 3001
```

### dev 

```powershell
$env:PORT=3001; npm --prefix react_dashboard start
```

Luu y:

- Day la cach test ban build
- Khong can chay cung luc voi `npm --prefix react_dashboard start`


## Cloudflared

```powershell
ren C:\Users\Admin\.cloudflared\cert.pem cert.pem.bak
cloudflared login
```

## Tao moi truong Python
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```



Neu thieu package, cai them:

```powershell
pip uninstall jose pycrypto crypto -y
pip install "python-jose[cryptography]"
pip install google-auth google-auth-oauthlib google-auth-httplib2
pip install google-api-python-client
pip install python-multipart
```

createdb -h localhost -U postgres analytics_restore
pg_restore -h localhost -U postgres -d analytics_restore --no-owner --no-privileges analytics_20260521_063001.dump