"""
Data Balancing Tool for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Implements two strategies to handle class imbalance:
  • SMOTE  — fast statistical oversampling (encodes categoricals internally)
  • CTGAN  — GAN-based synthetic data generation via SDV
"""

import pandas as pd
import numpy as np
import json
import sys
import io
from pathlib import Path
from sklearn.preprocessing import LabelEncoder
from datetime import datetime

# Force UTF-8 on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import DATA_DIR, CTGAN_EPOCHS, RANDOM_STATE
from tools.database import get_db_connection

def apply_balancing_strategy(filepath: str, method: str) -> str:
    """Applies a data balancing strategy to handle class imbalance.
    Can read from and write to SQLite database tables.
    """
    try:
        df = None
        is_table = False
        with get_db_connection() as conn:
            try:
                conn.execute(f"SELECT 1 FROM {filepath} LIMIT 1")
                is_table = True
            except Exception:
                pass

        if is_table:
            print(f"  [BALANCING] Loading dataset from SQLite table '{filepath}'")
            with get_db_connection() as conn:
                df = pd.read_sql(f"SELECT * FROM {filepath}", conn)
        elif Path(filepath).exists():
            print(f"  [BALANCING] Loading dataset from CSV file: {filepath}")
            df = pd.read_csv(filepath)
        else:
            print("  [BALANCING] Defaulting to SQLite table 'cleaned_historical_orders'")
            with get_db_connection() as conn:
                df = pd.read_sql("SELECT * FROM cleaned_historical_orders", conn)

        method_upper = method.strip().upper()

        if method_upper == "SMOTE":
            balanced_df = _apply_smote(df)
        elif method_upper == "CTGAN":
            balanced_df = _apply_ctgan(df)
        else:
            return json.dumps({
                "status": "error",
                "message": f"Unknown method '{method}'. Must be 'SMOTE' or 'CTGAN'.",
            })

        # ── Save balanced dataset to SQLite ────────────────────
        dest_table = "balanced_historical_orders"
        with get_db_connection() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {dest_table};")
            balanced_df.to_sql(dest_table, conn, if_exists="replace", index=False)
            print(f"  [BALANCING] Saved balanced data to SQLite table '{dest_table}' ({len(balanced_df)} rows)")

        # ── Save CSV fallback for backward compatibility ────────
        balanced_path = DATA_DIR / f"garment_balanced_data_{method_upper.lower()}.csv"
        balanced_df.to_csv(balanced_path, index=False)

        # ── Compute distributions ──────────────────────────────
        original_dist = df["Delivery_Status"].value_counts().to_dict()
        new_dist = balanced_df["Delivery_Status"].value_counts().to_dict()

        result = {
            "status": "success",
            "balanced_filepath": str(balanced_path),
            "balanced_table": dest_table,
            "method_used": method_upper,
            "original_distribution": {k: int(v) for k, v in original_dist.items()},
            "new_distribution": {k: int(v) for k, v in new_dist.items()},
            "original_total": len(df),
            "new_total": len(balanced_df),
            "samples_generated": len(balanced_df) - len(df),
        }

        print(f"  ⚖️  Balanced with {method_upper}: "
              f"{original_dist} → {new_dist}")

        return json.dumps(result)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "message": f"Balancing with {method} failed: {str(e)}",
            "traceback": traceback.format_exc(),
            "suggestion": "Try the alternative method (SMOTE if CTGAN failed, or vice versa).",
        })

def _apply_smote(df: pd.DataFrame) -> pd.DataFrame:
    """Apply SMOTE oversampling to balance the dataset."""
    from imblearn.over_sampling import SMOTE

    target_col = "Delivery_Status"
    X = df.drop(columns=[target_col]).copy()
    y = df[target_col].copy()

    # Encode categoricals
    categorical_cols = X.select_dtypes(include=["object"]).columns.tolist()
    label_encoders: dict[str, LabelEncoder] = {}

    for col in categorical_cols:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        label_encoders[col] = le

    # Encode target
    target_le = LabelEncoder()
    y_encoded = target_le.fit_transform(y)

    print(f"  [SMOTE] Oversampling minority class...")

    # Apply SMOTE
    smote = SMOTE(random_state=RANDOM_STATE)
    X_resampled, y_resampled = smote.fit_resample(X, y_encoded)

    # Decode categoricals back
    X_resampled = pd.DataFrame(X_resampled, columns=X.columns)
    for col in categorical_cols:
        le = label_encoders[col]
        max_val = len(le.classes_) - 1
        X_resampled[col] = X_resampled[col].round().astype(int).clip(0, max_val)
        X_resampled[col] = le.inverse_transform(X_resampled[col])

    # Decode target
    y_decoded = target_le.inverse_transform(y_resampled)

    balanced_df = X_resampled.copy()
    balanced_df[target_col] = y_decoded
    return balanced_df

def _apply_ctgan(df: pd.DataFrame) -> pd.DataFrame:
    """Apply CTGAN-based synthetic data generation to balance the dataset."""
    from sdv.metadata import SingleTableMetadata
    from sdv.single_table import CTGANSynthesizer

    target_col = "Delivery_Status"

    class_counts = df[target_col].value_counts()
    majority_class = class_counts.idxmax()
    minority_class = class_counts.idxmin()
    majority_count = int(class_counts[majority_class])
    minority_count = int(class_counts[minority_class])
    samples_needed = majority_count - minority_count

    if samples_needed <= 0:
        print("  [CTGAN] Data is already balanced — no synthesis needed.")
        return df.copy()

    minority_df = df[df[target_col] == minority_class].copy()

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(minority_df)

    synthesizer = CTGANSynthesizer(
        metadata,
        epochs=CTGAN_EPOCHS,
        verbose=True,
    )

    print(f"  [CTGAN] Training on {len(minority_df)} minority samples for {CTGAN_EPOCHS} epochs...")
    synthesizer.fit(minority_df)

    print(f"  [CTGAN] Generating {samples_needed} synthetic samples...")
    synthetic_df = synthesizer.sample(num_rows=int(samples_needed))
    synthetic_df[target_col] = minority_class

    balanced_df = pd.concat([df, synthetic_df], ignore_index=True)
    return balanced_df

if __name__ == "__main__":
    res = apply_balancing_strategy("cleaned_historical_orders", "SMOTE")
    print("\nResult:")
    print(res)
