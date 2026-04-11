import json
from pathlib import Path

_MAP_PATH = Path(__file__).parent.parent / "ticker_map.json"

def load_ticker_map() -> dict[str, str]:
    with open(_MAP_PATH) as f:
        return json.load(f)

def get_ticker(isin: str) -> str:
    mapping = load_ticker_map()
    if isin not in mapping:
        raise KeyError(f"No NSE ticker found for ISIN: {isin}")
    return mapping[isin]
