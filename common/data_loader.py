import csv
import json
from pathlib import Path
from typing import Dict, List


def load_csv_rows(file_path: str) -> List[Dict[str, str]]:
    path = Path(file_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def load_json_rows(file_path: str) -> List[Dict]:
    path = Path(file_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []
