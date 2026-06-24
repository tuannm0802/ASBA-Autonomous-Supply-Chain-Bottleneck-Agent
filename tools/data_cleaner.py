"""
Data Cleaner Tool for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performs deduplication, categorical typo correction,
group-by imputation, and outlier capping on raw database tables.
"""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

# Ensure project root is in path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.database import get_db_connection

def clean_dataset(table_name: str = "historical_orders") -> str:
    """Loads a table from SQLite, cleans it, and saves it to a cleaned table."""
    try:
        print(f"  [CLEAN] Reading table '{table_name}' from database...")
        with get_db_connection() as conn:
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)

        original_len = len(df)
        if original_len == 0:
            return json.dumps({
                "status": "error",
                "message": f"Table '{table_name}' is empty."
            })

        # ── 1. Deduplication ──────────────────────────────────
        df_clean = df.drop_duplicates(subset=[c for c in df.columns if c != "Order_ID"], keep="first").copy()
        dupes_removed = original_len - len(df_clean)
        print(f"  [CLEAN] Removed {dupes_removed} duplicate rows.")

        # ── 2. Standardize Categorical Typos ─────────────────
        # Mappings
        priority_map = {
            "critcal": "Critical", "critical": "Critical",
            "high": "High", "medium": "Medium", "low": "Low"
        }
        fwd_map = {
            "d.h.l": "DHL", "dhll": "DHL", "dhl": "DHL",
            "o.n.e": "ONE", "one_logistics": "ONE", "one": "ONE",
            "wanhai_inc": "Wanhai", "wanhai": "Wanhai",
            "gemadept_port": "Gemadept", "gemadept": "Gemadept"
        }
        mill_map = {
            "internel": "Internal", "internal": "Internal",
            "outsourced": "Outsource", "outsource": "Outsource",
            "both_mills": "Both", "both": "Both"
        }

        # Priority cleaning
        df_clean["Order_Priority"] = df_clean["Order_Priority"].astype(str).str.strip().str.lower().map(
            lambda val: priority_map.get(val, val.capitalize())
        )

        # Forwarder cleaning
        df_clean["Forwarder"] = df_clean["Forwarder"].astype(str).str.strip().str.lower().map(
            lambda val: fwd_map.get(val, "ONE")  # Default to majority ONE
        )

        # Mill source cleaning
        df_clean["Mill_Source"] = df_clean["Mill_Source"].astype(str).str.strip().str.lower().map(
            lambda val: mill_map.get(val, "Internal")  # Default to Internal
        )

        # ── 3. Imputation (Group by Supplier median) ──────────
        numeric_cols = [
            "Fabric_Trim", "Fabric_Rib", "Fabric_Body", "Fabric_CollarCuff",
            "Sewing_Trims", "Packing_Trims", "Interlining", "Threads", "Order_Value_USD"
        ]
        
        imputed_counts = 0
        for col in numeric_cols:
            if col in df_clean.columns:
                # Count missing before imputation
                missing_before = df_clean[col].isnull().sum()
                
                if missing_before > 0:
                    # Impute with supplier median
                    supplier_medians = df_clean.groupby("Supplier_ID")[col].transform("median")
                    df_clean[col] = df_clean[col].fillna(supplier_medians)
                    
                    # Fallback overall median for any remaining NaNs
                    overall_median = df_clean[col].median()
                    df_clean[col] = df_clean[col].fillna(overall_median)
                    
                    imputed_counts += missing_before

        # ── 4. Outlier Capping (IQR Method) ───────────────────
        outlier_cols = ["Order_Value_USD", "Delay_Penalty_USD_Per_Day"]
        capped_counts = 0
        
        for col in outlier_cols:
            if col in df_clean.columns:
                q1 = df_clean[col].quantile(0.25)
                q3 = df_clean[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                # Check how many would be capped
                outliers_mask = (df_clean[col] < lower_bound) | (df_clean[col] > upper_bound)
                num_outliers = outliers_mask.sum()
                
                # Clip values
                df_clean[col] = np.clip(df_clean[col], lower_bound, upper_bound)
                capped_counts += num_outliers

        # ── 5. Re-create One-Hot columns for ML ───────────────
        df_clean["Fwd_DHL"] = (df_clean["Forwarder"] == "DHL").astype(float)
        df_clean["Fwd_ONE"] = (df_clean["Forwarder"] == "ONE").astype(float)
        df_clean["Fwd_Wanhai"] = (df_clean["Forwarder"] == "Wanhai").astype(float)
        df_clean["Fwd_Gemadept"] = (df_clean["Forwarder"] == "Gemadept").astype(float)
        
        df_clean["Internal_Mill"] = df_clean["Mill_Source"].isin(["Internal", "Both"]).astype(float)
        df_clean["Outsource_Mill"] = df_clean["Mill_Source"].isin(["Outsource", "Both"]).astype(float)

        # ── 6. Save Cleaned Table back to SQLite ──────────────
        dest_table = f"cleaned_{table_name}" if not table_name.startswith("cleaned_") else table_name
        
        with get_db_connection() as conn:
            # Recreate table with proper schema
            conn.execute(f"DROP TABLE IF EXISTS {dest_table};")
            df_clean.to_sql(dest_table, conn, if_exists="replace", index=False)
            print(f"  [CLEAN] Cleaned data saved to table '{dest_table}' ({len(df_clean)} rows)")

        # Prepare summary
        missing_after = int(df_clean.isnull().sum().sum())
        
        summary = {
            "status": "success",
            "source_table": table_name,
            "destination_table": dest_table,
            "original_rows": original_len,
            "cleaned_rows": len(df_clean),
            "duplicates_removed": int(dupes_removed),
            "total_imputed_values": int(imputed_counts),
            "total_outliers_capped": int(capped_counts),
            "missing_values_after": missing_after,
        }
        
        if "Delivery_Status" in df_clean.columns:
            dist = df_clean["Delivery_Status"].value_counts().to_dict()
            summary["class_distribution"] = {k: int(v) for k, v in dist.items()}

        return json.dumps(summary, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "message": f"Cleaning failed: {str(e)}",
            "traceback": traceback.format_exc()
        })

if __name__ == "__main__":
    res = clean_dataset("historical_orders")
    print("\nCleaner Result JSON:")
    print(res)
