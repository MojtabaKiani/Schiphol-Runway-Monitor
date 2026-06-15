"""Constants for Schiphol Runway Monitor integration."""

DOMAIN = "schiphol_runways"
DEFAULT_SCAN_INTERVAL = 5  # minutes — matches LVNL update cadence

# LVNL page that embeds the runway widget (scraped as fallback)
LVNL_PAGE_URL = "https://www.lvnl.nl/omgeving/actueel-baangebruik-schiphol"
LVNL_EN_PAGE_URL = "https://en.lvnl.nl/local-community/current-runway-usage-at-schiphol"

# Sensor states
STATE_NOT_IN_USE = "not_in_use"
STATE_INBOUND = "inbound"
STATE_OUTBOUND = "outbound"
STATE_BOTH = "inbound_and_outbound"
STATE_UNAVAILABLE = "unavailable"

# All Schiphol runways with their pairing info
# Key: display name. Values: inbound_heading, outbound_heading, name
RUNWAYS = {
    "06/24": {
        "name": "Kaagbaan",
        "inbound_headings": ["06"],
        "outbound_headings": ["24"],
    },
    "09/27": {
        "name": "Oostbaan",
        "inbound_headings": ["09"],
        "outbound_headings": ["27"],
    },
    "18C/36C": {
        "name": "Zwanenburgbaan",
        "inbound_headings": ["18C", "18"],
        "outbound_headings": ["36C", "36"],
    },
    "18L/36R": {
        "name": "Aalsmeerbaan",
        "inbound_headings": ["18L"],
        "outbound_headings": ["36R"],
    },
    "18R/36L": {
        "name": "Polderbaan",
        "inbound_headings": ["18R"],
        "outbound_headings": ["36L"],
    },
    "04/22": {
        "name": "Buitenveldertbaan",
        "inbound_headings": ["04"],
        "outbound_headings": ["22"],
    },
}
