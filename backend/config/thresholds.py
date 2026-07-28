"""Alert thresholds — the single source of truth for the whole app.

Both the simulator (which raises alarms) and the API (which serves limits to the
UI via GET /api/config/thresholds) import from here, so the numbers the
dashboard colors on are exactly the numbers the simulator alarms on.

Change limits HERE, nowhere else. Nothing is hardcoded in UI components.
"""
from __future__ import annotations

# Voltage limits are expressed as a FRACTION of each device's nominal voltage,
# so one config works across packs of different nominal voltages.
THRESHOLDS = {
    "soc": {  # state of charge, % — lower is worse
        "direction": "below",
        "warning": 25.0,
        "critical": 10.0,
        "unit": "%",
    },
    "pack_voltage_frac": {  # fraction of nominal voltage — lower is worse
        "direction": "below",
        "warning": 0.92,
        "critical": 0.85,
        "unit": "x_nominal",
    },
    "temperature_c": {  # deg C — higher is worse
        "direction": "above",
        "warning": 45.0,
        "critical": 55.0,
        "unit": "C",
    },
}

# Ordering so we can pick the "worst" severity across several tripped signals.
SEVERITY_RANK = {"ok": 0, "info": 1, "warning": 2, "critical": 3}


def _severity_below(value: float, warning: float, critical: float) -> str:
    if value < critical:
        return "critical"
    if value < warning:
        return "warning"
    return "ok"


def _severity_above(value: float, warning: float, critical: float) -> str:
    if value > critical:
        return "critical"
    if value > warning:
        return "warning"
    return "ok"


def evaluate(soc: float, pack_voltage: float, temperature_c: float,
             nominal_voltage: float) -> dict:
    """Classify one reading against the thresholds.

    Returns {"status": <worst severity>, "alarms": [{code, severity, value}, ...]}
    where `alarms` lists only the signals currently in warning/critical.
    """
    v_frac = pack_voltage / nominal_voltage if nominal_voltage else 1.0

    checks = [
        ("LOW_SOC", _severity_below(
            soc, THRESHOLDS["soc"]["warning"], THRESHOLDS["soc"]["critical"]), soc),
        ("LOW_VOLTAGE", _severity_below(
            v_frac, THRESHOLDS["pack_voltage_frac"]["warning"],
            THRESHOLDS["pack_voltage_frac"]["critical"]), pack_voltage),
        ("OVER_TEMP", _severity_above(
            temperature_c, THRESHOLDS["temperature_c"]["warning"],
            THRESHOLDS["temperature_c"]["critical"]), temperature_c),
    ]

    alarms = [
        {"code": code, "severity": sev, "value": round(val, 2)}
        for code, sev, val in checks
        if sev != "ok"
    ]

    status = "ok"
    for a in alarms:
        if SEVERITY_RANK[a["severity"]] > SEVERITY_RANK[status]:
            status = a["severity"]

    return {"status": status, "alarms": alarms}
