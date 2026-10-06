"""Record the account value in USDT: one CSV row per call. Run hourly by cron and after each daily run.

Usage: python -m bot.balance
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import pandas as pd

from .config import SYMBOLS

logger = logging.getLogger("bot")

BALANCE_CSV = Path(__file__).resolve().parent.parent / "balance.csv"


def record(account, symbols: list[str], path: Path = BALANCE_CSV) -> dict:
    snap = account.snapshot(symbols)
    row = {"time": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M"), "total_usdt": round(snap["total"], 2),
           "free_usdt": round(snap["usdt"], 2)}
    for s, c in snap["coins"].items():
        base = s.split("-")[0].lower()
        row[f"{base}_qty"] = c["qty"]
        row[f"{base}_usdt"] = round(c["value"], 2)
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)
    logger.info("account value %.2f USDT (free USDT %.2f)", snap["total"], snap["usdt"])
    return row


def read(path: Path = BALANCE_CSV) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    from .exchange import KucoinAccount
    record(KucoinAccount(), [c.symbol for c in SYMBOLS])
