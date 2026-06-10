# CardDesk Survival Pack Checklist

_Last updated: 2026-06-10_

Use this before major updates, restores, or risky refactors.

## Before Major Update

```powershell
cd C:\apps\carddesk
python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers
git status
```

## Create Snapshot ZIP

```powershell
Compress-Archive -Path C:\apps\carddesk\* -DestinationPath C:\apps\carddesk-survival-pack.zip -Force
```

## What The Survival Pack Should Include

```text
app.py
models.py
config.py
extensions.py
requirements.txt
modules/
helpers/
templates/
static/
tools/
docs/
README.md
.gitignore
```

## Also Back Up Separately

These may be ignored by Git but are critical:

```text
.env values
instance/
data/
*.db
uploads/
photos/
images/
```

## Do Not Rely On GitHub Alone For

```text
SQLite databases
Uploaded card images
Local .env values
Render secret environment variables
```

## Known-Good Verification

After restoring or deploying:

```powershell
python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers
python app.py
```

Then visit:

```text
/
 /cards
 /dealer-hub
 /dashboard
 /storage
 /intake-tools
 /ai-import/review
 /show-prep
 /fulfillment
```

## Commit Known-Good State

```powershell
git add .
git commit -m "Known-good CardDesk recovery point"
git push origin main
```

## Store Copies In At Least 3 Places

```text
Local PC
External drive
Cloud drive
```

## Recovery Notes

- Never overwrite your only working folder.
- Rename bad folders instead of deleting them.
- Keep a ZIP of the last known-good working version.
- Run audits before pushing.
- If local works and Render fails, check Render logs before changing code.
