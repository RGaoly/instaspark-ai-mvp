# P0 local verification

The former copy-over installation procedure is deprecated. P0 is now part of
the repository and should be run directly from a clean checkout.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

Verify both first-level entry points and the five shared-workspace pages:

- Launch Mission
- Creator Opportunity
- Creator Search & Match
- Creator Compare
- Content Studio
- Outreach Operations
- Growth Review

The authoritative scope and acceptance criteria are in
[`docs/06_p0_product_contract.md`](docs/06_p0_product_contract.md).
