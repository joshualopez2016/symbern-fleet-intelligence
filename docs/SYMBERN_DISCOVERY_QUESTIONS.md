# Symbern — Discovery Questions

Questions to align on before the meeting, so we can turn this proof-of-concept
into a production tool on **your** data and systems. Grouped by theme; feel free to
answer inline or bring notes.

## 1. Data & getting to "real"
- Can you share a **sample data export** (CSV/Excel/JSON, even anonymized) so we can
  load real records and demo on live-shaped data?
- For **battery telemetry**: what fields do you capture today (state of charge,
  voltage, current, temperature, cell-level data, cycle count, GPS/location…), and
  at what **interval**?
- For **production/QA**: what does a test record contain (product, part number,
  serial, station, fixture, operator, parameters, measured values, limits, result)?
- Roughly what **data volume** should we design for — number of packs/units, tests
  per day, retention period?
- Any data that is **sensitive/regulated** and must stay on-prem or be masked?

## 2. Equipment & interfaces
- What **equipment/hardware** are we interfacing to (BMS models, chargers, test
  benches, telematics units)? Any datasheets or protocol docs?
- How does data leave that equipment today — **CAN bus, Modbus, MQTT, REST,
  serial, files**, a gateway/telematics box?
- Is telemetry **pushed** from devices or **polled**, and through what network
  (cellular, on-site LAN, cloud broker)?
- Cell-level detail available (per-cell voltages/temps) for imbalance detection?

## 3. Existing systems & platforms
- What platforms do you already run that we should **tie into or avoid
  duplicating** (fleet telematics, MES/ERP, historian, CMMS, BI tools)?
- Is there a **system of record** these tools should read from or write back to?
- Single sign-on / identity provider (Azure AD, Okta, Google) we should integrate
  for login instead of our built-in accounts?

## 4. APIs & integration
- Do you have your **own API** (or your telematics vendor's) we can pull from — and
  can you share docs, auth method, and a test key/sandbox?
- Would you prefer we **push** data to one of your endpoints, **pull** from yours,
  or both? Any message format/standards you require?
- Any **webhook/event** needs (e.g., notify an external system on a critical alarm
  or a failed test)?

## 5. Thresholds, limits & QA rules (make the intelligence yours)
- What are your **alert thresholds** for a healthy vs. degrading vs. bad battery
  (SoC, voltage, temperature, imbalance, internal resistance, capacity fade)?
- Do these vary by **product line, duty cycle, or customer**?
- For production: your **test parameters, spec limits, and pass/fail rules** per
  product — and any station/fixture calibration or guardbands?
- Any **predictive** rules you'd want (flag "getting bad" before failure), or is
  threshold-based monitoring the scope for now?

## 6. Users, roles & workflow
- Who are the **user types** and what should each see/do (operators, engineers,
  supervisors, managers, customers)? Does our 4-role model fit?
- Should some data be **scoped per customer/site** (multi-tenant)?
- Where should **support tickets** and **alerts** go — email, Slack/Teams, an
  existing ticketing system (Jira, ServiceNow)?
- Any **reports** you produce today that we should reproduce (format, cadence,
  recipients)?

## 7. Deployment, security & compliance
- Preferred hosting: **cloud, on-prem, or hybrid**? Any region/residency rules?
- Security/compliance requirements (SSO, audit logging, data retention,
  encryption, SOC 2 / ISO, customer NDAs)?
- Expected **scale** and uptime/SLA expectations?

## 8. Success criteria
- What would make this a **clear win** in the first 30/60/90 days?
- Which **one workflow**, done well, would prove the most value first?
- Who are the **decision-makers and daily users** we should design around?

---
*From the Symbern Fleet Intelligence proof-of-concept. Everything demoed today runs
on simulated data; these answers let us wire it to your real equipment and systems.*
