"""
District Configuration Registry for Weather Data Processing.

Enforces configuration-driven normalization to avoid hardcoded district checks.
Each district defines its raw file path, encoding, column mappings, 
ID extraction rules, and date formats.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import re
import pandas as pd


def default_panchayat_id_extractor(val: any, lgd_code: any) -> int:
    """
    Extracts or coerces an integer panchayat_id.
    If val is already an integer (e.g. 1001), returns int(val).
    If val is a string like 'MH_27_PUNE_185262', extracts the trailing integer.
    Falls back to lgd_code if parsing fails.
    """
    if pd.isnull(val):
        return int(lgd_code)
    if isinstance(val, (int, float)) and not pd.isna(val):
        return int(val)
    val_str = str(val).strip()
    # Try direct int conversion
    try:
        return int(val_str)
    except ValueError:
        pass
    # Try finding digits in the string
    match = re.search(r"(\d+)$", val_str)
    if match:
        return int(match.group(1))
    return int(lgd_code)


@dataclass
class DistrictConfig:
    name: str
    state: str = "Maharashtra"
    raw_path: str = ""
    encoding: str = "utf-8"
    column_mapping: Dict[str, str] = field(default_factory=dict)
    drop_columns: List[str] = field(default_factory=list)
    date_format: str = "%d-%m-%Y"
    panchayat_id_extractor: Callable = default_panchayat_id_extractor
    source: str = "IMD"
    source_model: str = "GFS"


DISTRICT_REGISTRY: Dict[str, DistrictConfig] = {
    "nashik": DistrictConfig(
        name="Nashik",
        state="Maharashtra",
        raw_path="data/raw/nashik/nashik_panchayat_weather_raw.csv",
        encoding="latin1",
        column_mapping={
            "latitude": "panchayat_latitude",
            "longitude": "panchayat_longitude",
        },
        drop_columns=["Unnamed: 16", "Unnamed: 0"],
        date_format="%d-%m-%Y",
        panchayat_id_extractor=default_panchayat_id_extractor,
        source="IMD",
        source_model="GFS",
    ),
    "pune": DistrictConfig(
        name="Pune",
        state="Maharashtra",
        raw_path="data/raw/pune/pune_original.csv",
        encoding="utf-8",
        column_mapping={
            "panchayat_latitude": "panchayat_latitude",
            "panchayat_longitude": "panchayat_longitude",
        },
        drop_columns=["Unnamed: 0"],
        date_format="%d-%m-%Y",
        panchayat_id_extractor=default_panchayat_id_extractor,
        source="IMD/NCMRWF",
        source_model="GFS-MeteoStat",
    ),
}


def get_district_config(district_name: str) -> DistrictConfig:
    """Retrieve district configuration by key (case-insensitive)."""
    key = district_name.strip().lower()
    if key not in DISTRICT_REGISTRY:
        supported = list(DISTRICT_REGISTRY.keys())
        raise ValueError(f"Unsupported district '{district_name}'. Supported districts: {supported}")
    return DISTRICT_REGISTRY[key]
