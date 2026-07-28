# Symbern Fleet Intelligence — Demo Walkthrough

A click-by-click script for showing the platform to Symbern. Sign in as the admin
(`admin@bms.local`) to show everything, then optionally re-sign as the viewer to
show role restrictions.

## Opening (30 seconds — the positioning)
- "This is one platform that follows a battery pack through its **whole
  lifecycle** — from **manufacturing test** to **deployed in the field** —
  matching your 'Batteries. Equipment. Intelligence.'"
- Point out the branding: Symbern name, tagline, colors, and the **Fleet /
  Production** switch in the header. "Two data domains, one shell."
- Note the **⚡ Realtime** badge: "the fleet view updates live over a WebSocket —
  no refreshing."

## Sign-in & roles (the security story)
- Show the **login screen** — "nothing is visible until you sign in."
- After login, point to the **user chip** (email + role) and the **👥 Users**
  button (admins only). "Four roles — Viewer, Engineer, Supervisor, Administrator
  — enforced on the server, not just hidden in the UI."
- Optional: open **Users** — add a user, change a role. "Admins manage access here."

## Fleet Intelligence (deployed batteries)
- **The grid**: color-coded packs, worst-first. Each card shows state of charge,
  pack voltage, load/charge current, temperature, and active alarms.
- **Status tallies + Filters**: click **critical/warning**; open **⚙ Filters** and
  narrow by site, company, equipment, an **SoC range**, or "only packs with active
  alarms." "All server-side, so it stays fast at thousands of packs."
- **✨ Ask AI** (AI feature #1 — natural-language filtering): type
  *"warning packs under 25% at Harbor Marine"* → it turns plain English into a real
  filtered result and explains what it did.
- **AI Briefing**: click it → a live, plain-English fleet-health summary grounded
  in the real numbers.
- **Active Alerts** panel: newest-first, click an alert to jump to the pack.
- **Drill-down**: click any pack → live **SoC & voltage trend charts** with
  warning/critical threshold lines, the device details, and **Notes** (per-user
  annotations; note the viewer can't edit — role in action).
- **Reports/Export**: **📄 Daily Report** (per-pack, 30 columns) with **Print /
  Save-as-PDF**; **⬇ CSV / Excel** exports that honor the active filters.
- **🔎 Query Builder**: "no-code — pick a data source, add conditions, run." Show
  the generated SQL preview. "It runs on a read-only database role, so it can never
  change data." Mention it can query the production data too.

## Production Test Records (manufacturing / QA)
- Flip the header switch to **Production**.
- **Daily Production Summary**: Total Tested / Passed / Failed / Pass % / Fail %,
  plus **Most-Failed Product / Fixture / Station** — with a date picker.
- **Pass/Fail Lookup**: filter by product, station, fixture, test parameter,
  result, serial, date range. Export to CSV/Excel.
- **Universal Search**: one bar — type an operator (e.g. `OP-Chen`) or a fixture
  (`FIX-C`) and it searches across serial / part / product / station / fixture /
  operator.
- **Serial history**: click any **serial** → full chronological test history for
  that unit (every test, station, result, measured-vs-limit, failure reason).
  "Full traceability."

## The Assistant (AI feature #2 — the chatbot)
- Click **💬 Assistant** (bottom-right). Ask *"How do I export failed tests?"* — it
  answers, specific to this app.
- Click **🎫 Start a support ticket** → file an IT or Management request. "Users get
  help without leaving the app; you get a ticket queue."

## Close (the honest engineering points)
- "**All data here is simulated** — cloud-safe for this demo. The schema and API
  are shaped so swapping in **your real feeds** is a drop-in, not a rewrite."
- "Everything is **role-secured, parameterized (no SQL injection), tested** (37
  automated tests + a Postman collection), and uses only **permissively-licensed**
  components."
- Hand off to the discovery questions (see `SYMBERN_DISCOVERY_QUESTIONS.md`).
