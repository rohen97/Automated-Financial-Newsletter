from __future__ import annotations

import os


def fetch_macro_data() -> list[dict]:
    fred_key = os.getenv("FRED_API_KEY")
    source = {"name": "FRED" if fred_key else "Sample Data", "url": "https://fred.stlouisfed.org/"}
    return [
        {"indicator": "US policy rate", "value": "configured via FRED" if fred_key else "sample", "comment": "Rates remain central to discount-rate sensitivity.", "source": source},
        {"indicator": "Inflation", "value": "configured via FRED" if fred_key else "sample", "comment": "Inflation surprises drive cross-asset repricing.", "source": source},
        {"indicator": "Growth", "value": "configured via FRED" if fred_key else "sample", "comment": "Growth momentum informs sector and credit risk appetite.", "source": source},
    ]
