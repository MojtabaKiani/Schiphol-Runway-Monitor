"""Constants for Schiphol Runway Monitor integration."""

DOMAIN = "schiphol_runways"
DEFAULT_SCAN_INTERVAL = 5  # minutes — matches LVNL update cadence

# Sensor states
STATE_NOT_IN_USE = "not_in_use"
STATE_INBOUND    = "inbound"
STATE_OUTBOUND   = "outbound"
STATE_BOTH       = "inbound_and_outbound"

# All Schiphol runways.
# "headings" lists all possible designators for that physical runway strip.
# The API already distinguishes landing vs departing — we just need to know
# which headings belong to which runway pair.
RUNWAYS: dict[str, dict] = {
    "06/24":   {"name": "Kaagbaan",         "headings": ["06", "24"]},
    "09/27":   {"name": "Oostbaan",          "headings": ["09", "27"]},
    "18C/36C": {"name": "Zwanenburgbaan",    "headings": ["18C", "36C", "18", "36"]},
    "18L/36R": {"name": "Aalsmeerbaan",      "headings": ["18L", "36R"]},
    "18R/36L": {"name": "Polderbaan",        "headings": ["18R", "36L"]},
    "04/22":   {"name": "Buitenveldertbaan", "headings": ["04", "22"]},
}
