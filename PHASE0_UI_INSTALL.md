# P0 UI verification

The former downloadable UI patch procedure is deprecated. The current UI is
maintained in `components/`, `views/`, and `app.py`.

After following the setup in [`README.md`](README.md), verify that:

1. Launch Mission and Creator Opportunity appear together under **Start from**.
2. Activating either entry updates the context labels on all downstream pages.
3. A valid approval creates one OutreachCase and appears in Outreach Operations.
4. Growth Review shows only context-linked workflow and performance records.
5. All automated tests pass before deployment.
