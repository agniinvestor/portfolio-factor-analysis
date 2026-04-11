import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

def is_stale(path: Path, max_age_hours: int = 24) -> bool:
    """Return True if cache file is missing or older than max_age_hours."""
    if not path.exists():
        return True
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - mtime > timedelta(hours=max_age_hours)

def write_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

def read_cache(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
