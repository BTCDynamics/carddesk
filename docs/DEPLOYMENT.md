# CardDesk Deployment Guide

_Last updated: 2026-06-10_

## Production Source

```text
GitHub repo: https://github.com/BTCDynamics/carddesk.git
Branch: main
Render service: CardDesk
```

## Local Development Folder

```text
C:\apps\carddesk
```

## Normal Local Workflow

```powershell
cd C:\apps\carddesk
.\venv\Scripts\Activate.ps1

python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers

git status
git add .
git commit -m "Describe changes"
git push origin main
```

## Render Deploy Checklist

1. Confirm Render is connected to:
   - repo: `BTCDynamics/carddesk`
   - branch: `main`
2. Push current code to GitHub.
3. In Render, use:
   - Manual Deploy
   - Clear build cache & deploy
4. Watch logs during startup.
5. Open key pages:
   - `/`
   - `/cards`
   - `/dealer-hub`
   - `/storage`
   - `/intake-tools`
   - `/ai-import/review`
   - `/show-prep`
   - `/fulfillment`

## Common Render Problems

| Symptom | Likely Cause | First Check |
|---|---|---|
| `BuildError: Could not build url for endpoint` | Template route mismatch | `python tools\route_audit.py` |
| `no such column` | Render DB schema older than models | `python tools\db_schema_audit.py` |
| `ModuleNotFoundError` | Missing package or wrong requirements | `requirements.txt` |
| Local works, Render fails | Git/Render/DB mismatch | Render repo/branch, logs, schema |
| Old behavior still showing | Render cache or wrong branch | Clear build cache & deploy |

## Start Command

Typical Render start command:

```text
gunicorn app:app
```

## Build Command

Typical Render build command:

```text
pip install -r requirements.txt
```

## Before Any Major Deploy

```powershell
python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers
git status
```

Then create a safety snapshot:

```powershell
Compress-Archive -Path C:\apps\carddesk\* -DestinationPath C:\apps\carddesk-snapshot.zip -Force
```

## Rollback Strategy

1. Find last known-good commit:

```powershell
git log --oneline -10
```

2. On Render, use previous deploy rollback if available, or revert locally and push.

3. If database schema changed, verify whether rollback also needs database restore.

## Do Not Commit

These should stay out of GitHub:

```text
.env
venv/
.venv/
__pycache__/
instance/
data/
*.db
uploads/
photos/
images/
*.zip
API token text files
```
