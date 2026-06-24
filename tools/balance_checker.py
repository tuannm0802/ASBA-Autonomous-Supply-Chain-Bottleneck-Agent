"""
Data Balance Checker for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analyzes the class distribution of the Delivery_Status target variable
and determines whether the dataset is imbalanced.
"""

import pandas as pd
import json
from pathlib import Path
import sys
import io

# Force UTF-8 on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import IMBALANCE_THRESHOLD
from tools.database import get_db_connection

def check_data_balance(filepath: str) -> str:
    """Checks the class balance of the delivery status in the dataset.
    Can read from an SQLite table name or CSV file path.
    """
    try:
        df = None
        # Check if the filepath is a table name in SQLite
        is_table = False
        with get_db_connection() as conn:
            try:
                # Query a single row to verify table existence
                conn.execute(f"SELECT 1 FROM {filepath} LIMIT 1")
                is_table = True
            except Exception:
                pass

        if is_table:
            print(f"  [BALANCE] Loading dataset from SQLite table '{filepath}'")
            with get_db_connection() as conn:
                df = pd.read_sql(f"SELECT * FROM {filepath}", conn)
        elif Path(filepath).exists():
            print(f"  [BALANCE] Loading dataset from CSV file: {filepath}")
            df = pd.read_csv(filepath)
        else:
            # Default fallback to cleaned_historical_orders
            print("  [BALANCE] Defaulting to SQLite table 'cleaned_historical_orders'")
            with get_db_connection() as conn:
                df = pd.read_sql("SELECT * FROM cleaned_historical_orders", conn)

        # ── Validate target column exists ──────────────────────
        if "Delivery_Status" not in df.columns:
            return json.dumps({
                "status": "error",
                "message": "Column 'Delivery_Status' not found in dataset. "
                           f"Available columns: {list(df.columns)}",
            })

        # ── Calculate distribution ─────────────────────────────
        distribution = df["Delivery_Status"].value_counts()
        total = len(df)
        ratios = (distribution / total).to_dict()

        # ── Determine imbalance ────────────────────────────────
        minority_ratio = min(ratios.values())
        majority_ratio = max(ratios.values())
        imbalance_ratio = (
            round(majority_ratio / minority_ratio, 2)
            if minority_ratio > 0
            else float("inf")
        )

        result = {
            "status": "success",
            "filepath": filepath,
            "total_samples": total,
            "class_distribution": {k: int(v) for k, v in distribution.items()},
            "class_ratios": {k: round(v, 4) for k, v in ratios.items()},
            "minority_class": min(ratios, key=ratios.get),
            "minority_ratio": round(minority_ratio, 4),
            "imbalance_ratio": imbalance_ratio,
            "is_imbalanced": minority_ratio < IMBALANCE_THRESHOLD,
            "missing_values": int(df.isnull().sum().sum()),
            "total_columns": len(df.columns),
        }

        print(f"  📊 Balance check: {dict(distribution)} | "
              f"Imbalanced={minority_ratio < IMBALANCE_THRESHOLD}")

        return json.dumps(result)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to check data balance: {str(e)}",
        })

if __name__ == "__main__":
    # Test on cleaned_historical_orders table
    res = check_data_balance("cleaned_historical_orders")
    print("\nResult:")
    print(res)
