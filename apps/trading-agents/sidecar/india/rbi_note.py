"""Static RBI and CPI note.

No keyless API is wired for these two prints. Edit this file when the MPC
changes the repo rate or when a newer CPI release should be the one quoted.
The desk labels the text as a static note, not a live fetch.
"""

from __future__ import annotations

AS_OF = "2026-11-13"
REPO_RATE = "5.50%"
SDF_RATE = "5.25%"
MSF_RATE = "5.75%"
CPI = "6.09%"
CPI_PERIOD = "October 2026"
CPI_BASE = "2024=100"
FOOD_CPI = "8.94%"

NOTE = (
    f"Static desk note, not a live API, checked {AS_OF}. "
    f"RBI policy repo rate {REPO_RATE} (standing deposit facility {SDF_RATE}, "
    f"marginal standing facility {MSF_RATE}), as shown on rbi.org.in on {AS_OF}. "
    f"CPI {CPI} provisional for {CPI_PERIOD} (base {CPI_BASE}), food inflation {FOOD_CPI}, "
    "from the MoSPI release of 12 Nov 2026. This file does not move when the MPC meets. "
    "Update sidecar/india/rbi_note.py to change it."
)
