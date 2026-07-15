
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd


@dataclass
class SessionData:
    filename: str
    sheets: Dict[str, pd.DataFrame]
    active_sheet: str
    mappings: dict = field(default_factory=dict)


SESSIONS: Dict[str, SessionData] = {}
