# Install Phase 0 into the existing repository

From the repository root:

```bash
cp app.py app_pre_phase0.py
cp -R pages pages_pre_phase0 2>/dev/null || true
cp -R components components_pre_phase0 2>/dev/null || true
cp -R services services_pre_phase0 2>/dev/null || true
```

Copy the Phase 0 package over the repository, then run:

```bash
python -m pytest -q
python -m streamlit run app.py
```

Check all seven sidebar entries:

- Mission Control
- Launch Mission
- Creator Search
- Creator Compare
- Content Studio
- Outreach Operations
- Growth Review

When verified:

```bash
git add app.py pages components services tests/test_phase0_structure.py docs/05_phase0_architecture.md
git commit -m "refactor: establish six-module product architecture"
git push
```
