# Install the Phase 0 UI patch

From the existing repository root:

```bash
cd ~/Downloads/instaspark-ai-mvp
mkdir -p ~/Downloads/instaspark-backups
cp app.py ~/Downloads/instaspark-backups/app_before_phase0_ui.py
```

After downloading and unzipping the patch, copy it over the repository:

```bash
PHASE0_UI_DIR=$(find "$HOME/Downloads" -maxdepth 1 -type d -name 'instaspark-phase0-ui-patch*' -print -quit)
cp -Rfv "$PHASE0_UI_DIR"/. .
```

Remove the obsolete Phase 0 `pages/` directory because the new router uses
`st.navigation(position="hidden")` and custom page labels:

```bash
rm -rf pages
```

Install or refresh dependencies:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest -q
```

Start locally:

```bash
python -m streamlit run app.py
```

Verify all six pages and then commit:

```bash
git add app.py components views .streamlit requirements.txt tests/test_phase0_ui.py docs/05_phase0_ui_system.md PHASE0_UI_INSTALL.md
git add -u pages
git commit -m "feat: rebuild Phase 0 enterprise UI shell"
git push
```
