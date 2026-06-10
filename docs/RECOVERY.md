# CardDesk Recovery Guide

_Last updated: 2026-06-10_

## Goal

This document is the "get CardDesk back up" checklist if something goes sideways.

## First Rule

Do not panic and do not overwrite the only working copy.

Before trying fixes, make a snapshot:

```powershell
Compress-Archive -Path C:\apps\carddesk\* -DestinationPath C:\apps\carddesk-before-fix.zip -Force
```

## Quick Diagnosis

Run:

```powershell
cd C:\apps\carddesk
git status
git log --oneline -5
git remote -v
python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers
```

## If Local App Will Not Start

1. Activate venv:

```powershell
cd C:\apps\carddesk
.\venv\Scripts\Activate.ps1
```

2. Install requirements:

```powershell
pip install -r requirements.txt
```

3. Compile code:

```powershell
python -m compileall modules helpers
python -m py_compile app.py
```

4. Run app:

```powershell
python app.py
```

## If Render Fails But Local Works

Check these first:

```text
Render repo: BTCDynamics/carddesk
Render branch: main
Latest Git commit matches local
Manual Deploy -> Clear build cache & deploy
```

Then check logs for:

```text
BuildError
ModuleNotFoundError
ImportError
OperationalError
no such column
no such table
```

## If You See `BuildError` / Missing Endpoint

Run:

```powershell
python tools\route_audit.py
```

Fix by adding the missing route function or correcting the template `url_for(...)`.

## If You See `no such column` or `no such table`

Run:

```powershell
python tools\db_schema_audit.py
```

This means `models.py` and the active database do not match.

## If You Restored From ZIP

After restore:

```powershell
cd C:\apps\carddesk
git status
python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers
```

Make sure the restored ZIP contains the modular folders:

```text
modules/
helpers/
templates/
static/
models.py
app.py
```

If a ZIP only has old `app.py/templates/static`, it may be old CardWatch/CardDesk code and not the current modular app.

## If GitHub Is Not Current

```powershell
git status
git add .
git commit -m "Restore working CardDesk version"
git push origin main
```

If Git says clean:

```text
nothing to commit, working tree clean
```

then GitHub already matches local.

## If You Edited The Wrong Folder

Check location:

```powershell
pwd
dir C:\apps
```

Make sure you are working in:

```text
C:\apps\carddesk
```

## Manual Survival Restore

If everything is broken:

1. Rename bad folder:

```powershell
Rename-Item C:\apps\carddesk C:\apps\carddesk-bad
```

2. Restore last known-good ZIP to:

```text
C:\apps\carddesk
```

3. Activate venv or recreate it.
4. Install requirements.
5. Run audits.
6. Run locally.
7. Commit/push only after local works.

## Backup Items That Matter

```text
Source code
models.py
modules/
helpers/
templates/
static/
docs/
tools/
requirements.txt
.env values copied somewhere safe
SQLite database files
uploads/photos/images
```

## Recovery Priority

1. Get local app running.
2. Run route audit.
3. Run DB schema audit.
4. Commit/push known-good state.
5. Clear Render build cache and deploy.
6. Confirm production pages.
