"""
Garment Logistics Data Generator for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generates an enterprise-scale dataset of 10,000 imbalanced,
unclean (dirty) historical records and 50 active current orders,
writing them directly to the SQLite database.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import sys
import io
import json
import shutil

# Force UTF-8 encoding on stdout/stderr to prevent Windows cp1252 encoding errors
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import (
    DATA_DIR,
    IMBALANCE_RATIO,
    CURRENT_ORDERS_COUNT,
    RANDOM_STATE,
)
from tools.database import get_db_connection, init_database

def generate_mock_logistics_data(num_samples: int = 10000) -> str:
    """Generates 10K synthetic dirty historical orders and 50 active current orders.
    Loads alternative suppliers into SQLite database.
    """
    np.random.seed(RANDOM_STATE)
    date_str = datetime.now().strftime("%Y%m%d")
    
    # ── Initialize database schema ───────────────────────────
    init_database()
    
    dest_dir_path = DATA_DIR / "garment_suppliers_directory.csv"

    # Load suppliers into SQLite
    if dest_dir_path.exists():
        df_sup = pd.read_csv(dest_dir_path)
        with get_db_connection() as conn:
            df_sup.to_sql("supplier_directory", conn, if_exists="replace", index=False)
            print(f"  [DB] Loaded {len(df_sup)} suppliers into table 'supplier_directory'")
            
    supplier_ids = [f"SUP-{i:03d}" for i in range(1, 16)]  # 15 garment suppliers

    # ── Helper to generate a single dataframe ──────────────────
    def _generate_base_data(size: int, is_current: bool = False):
        # 1. Inventory Quantities (Numeric)
        fabric_body = np.random.randint(200, 5001, size=size)
        fabric_trim = np.random.randint(50, 1501, size=size)
        fabric_rib = np.random.randint(20, 1001, size=size)
        fabric_collar_cuff = np.random.randint(20, 1001, size=size)
        sewing_trims = np.random.randint(100, 3001, size=size)
        packing_trims = np.random.randint(100, 3001, size=size)
        interlining = np.random.randint(50, 1501, size=size)
        threads = np.random.randint(200, 6001, size=size)

        # 2. Color Sets Count (Numeric)
        color_sets_count = np.random.randint(1, 11, size=size)

        # 3. Forwarders (DHL, ONE, Wanhai, Gemadept)
        fwd_choices = np.random.choice(
            ["DHL", "ONE", "Wanhai", "Gemadept"],
            size=size,
            p=[0.20, 0.35, 0.25, 0.20]
        )
        fwd_dhl = (fwd_choices == "DHL").astype(int)
        fwd_one = (fwd_choices == "ONE").astype(int)
        fwd_wanhai = (fwd_choices == "Wanhai").astype(int)
        fwd_gemadept = (fwd_choices == "Gemadept").astype(int)

        # 4. Mill Source for Fabric
        mill_choices = np.random.choice(
            ["Internal", "Outsource", "Both"],
            size=size,
            p=[0.60, 0.30, 0.10]
        )
        internal_mill = (mill_choices != "Outsource").astype(int)
        outsource_mill = (mill_choices != "Internal").astype(int)

        # 5. Financial & Sourcing details
        unit_count = np.random.randint(1000, 15001, size=size)
        unit_price = np.random.randint(6, 16, size=size)
        order_value_usd = unit_count * unit_price
        delay_penalty_per_day = np.round(order_value_usd * 0.01, 2)
        
        shipping_cost_usd = (
            fwd_dhl * 10000 + 
            fwd_one * 4500 + 
            fwd_wanhai * 2800 + 
            fwd_gemadept * 1500
        )

        df_dict = {
            "Supplier_ID": np.random.choice(supplier_ids, size=size),
            "Fabric_Trim": fabric_trim.astype(float),
            "Fabric_Rib": fabric_rib.astype(float),
            "Fabric_Body": fabric_body.astype(float),
            "Fabric_CollarCuff": fabric_collar_cuff.astype(float),
            "Sewing_Trims": sewing_trims.astype(float),
            "Packing_Trims": packing_trims.astype(float),
            "Interlining": interlining.astype(float),
            "Threads": threads.astype(float),
            "Color_Sets_Count": color_sets_count.astype(float),
            "Fwd_DHL": fwd_dhl.astype(float),
            "Fwd_ONE": fwd_one.astype(float),
            "Fwd_Wanhai": fwd_wanhai.astype(float),
            "Fwd_Gemadept": fwd_gemadept.astype(float),
            "Internal_Mill": internal_mill.astype(float),
            "Outsource_Mill": outsource_mill.astype(float),
            "Unit_Count": unit_count.astype(float),
            "Order_Value_USD": order_value_usd.astype(float),
            "Delay_Penalty_USD_Per_Day": delay_penalty_per_day.astype(float),
            "Shipping_Cost_USD": shipping_cost_usd.astype(float),
            "Order_Priority": np.random.choice(
                ["Low", "Medium", "High", "Critical"],
                size=size,
                p=[0.25, 0.45, 0.20, 0.10]
            )
        }

        if is_current:
            df_dict["Order_ID"] = [f"ORD-{date_str}-C{i:04d}" for i in range(1, size + 1)]
        else:
            df_dict["Order_ID"] = [f"ORD-{date_str}-H{i:04d}" for i in range(1, size + 1)]

        return pd.DataFrame(df_dict)

    # ── Generate Historical Dataset ────────────────────────────
    df_hist = _generate_base_data(num_samples, is_current=False)

    # Compute Late delivery score BEFORE injecting dirtiness to establish correlation
    late_score = (
        df_hist["Outsource_Mill"] * 0.25
        + df_hist["Fwd_Wanhai"] * 0.25
        + df_hist["Fwd_Gemadept"] * 0.35
        + (df_hist["Color_Sets_Count"] / 10.0) * 0.20
        + (5000 - df_hist["Fabric_Body"]) / 5000.0 * 0.15
        + (6000 - df_hist["Threads"]) / 6000.0 * 0.10
        + np.random.normal(0, 0.08, size=num_samples)
    )

    threshold = np.percentile(late_score, (1.0 - IMBALANCE_RATIO) * 100)
    df_hist["Delivery_Status"] = np.where(late_score >= threshold, "Late", "On-Time")

    # ── Inject Anomalies (Dirty Data) into Historical orders ──
    # 1. Missing Values (5% random missing in key features)
    for col in ["Fabric_Trim", "Fabric_Rib", "Threads", "Order_Value_USD"]:
        mask = np.random.rand(num_samples) < 0.05
        df_hist.loc[mask, col] = np.nan

    # 2. Outliers (1% extreme outliers in numeric fields)
    outlier_cols = ["Order_Value_USD", "Delay_Penalty_USD_Per_Day"]
    for col in outlier_cols:
        mask = np.random.rand(num_samples) < 0.01
        df_hist.loc[mask, col] = df_hist.loc[mask, col] * 15.0

    # 3. Categorical Typos
    # Priorities typos
    priority_typos = {
        "Critical": "Critcal",
        "High": "high",
        "Medium": "medium",
        "Low": "low"
    }
    mask_priority = np.random.rand(num_samples) < 0.10
    df_hist.loc[mask_priority, "Order_Priority"] = df_hist.loc[mask_priority, "Order_Priority"].map(
        lambda x: priority_typos.get(x, x)
    )

    # Forwarders typos - since forwarders are currently represented as one-hot columns:
    # We will introduce a new raw column representation for forwarder string, OR
    # just create some inconsistent values when one-hot columns are missing or both are 1.
    # In order to make it look like a dirty SQL load, we can randomly set ONE-HOT columns to 0.0 or 1.0 for multiple columns.
    # But a cleaner way to show typos is by introducing typos in a single text column "Forwarder" and let the cleaning process
    # extract one-hot encodings. Let's actually generate a "Forwarder" raw string column in raw tables,
    # so we clean it and then one-hot encode it!
    # Wait, the previous code had Fwd_DHL, Fwd_ONE, Fwd_Wanhai, Fwd_Gemadept.
    # Let's add a "Forwarder" string column to the historical database! This is much more natural.
    # Wait, if we add "Forwarder", we can inject typos: "D.H.L", "DHLL", "O.N.E", "Wanhai_Inc", "Gemadept_Port".
    # And we can do the same for Mill_Source: "Internal_Mill", "Outsource_Mill" -> we can have "Mill_Source" column: "Internal", "Outsource", "Both", and introduce typos "internel", "outsourced".
    # This is a much better, cleaner representation of dirty text columns in real databases!
    # Let's add "Forwarder" and "Mill_Source" to the tables in SQLite, which makes cleaning them extremely elegant.
    # Let's adjust df_hist before writing. We will construct a "Forwarder" string column.
    forwarders = []
    for idx, row in df_hist.iterrows():
        if row["Fwd_DHL"] == 1:
            forwarders.append("DHL")
        elif row["Fwd_ONE"] == 1:
            forwarders.append("ONE")
        elif row["Fwd_Wanhai"] == 1:
            forwarders.append("Wanhai")
        else:
            forwarders.append("Gemadept")
    df_hist["Forwarder"] = forwarders
    
    # Inject forwarder typos
    fwd_typos = {
        "DHL": "D.H.L",
        "ONE": "O.N.E",
        "Wanhai": "Wanhai_Inc",
        "Gemadept": "Gemadept_Port"
    }
    mask_fwd = np.random.rand(num_samples) < 0.10
    df_hist.loc[mask_fwd, "Forwarder"] = df_hist.loc[mask_fwd, "Forwarder"].map(lambda x: fwd_typos.get(x, x))

    # Mill source string representation
    mills = []
    for idx, row in df_hist.iterrows():
        if row["Internal_Mill"] == 1 and row["Outsource_Mill"] == 1:
            mills.append("Both")
        elif row["Internal_Mill"] == 1:
            mills.append("Internal")
        else:
            mills.append("Outsource")
    df_hist["Mill_Source"] = mills
    
    # Inject mill typos
    mill_typos = {
        "Internal": "internel",
        "Outsource": "outsourced",
        "Both": "both_mills"
    }
    mask_mill = np.random.rand(num_samples) < 0.08
    df_hist.loc[mask_mill, "Mill_Source"] = df_hist.loc[mask_mill, "Mill_Source"].map(lambda x: mill_typos.get(x, x))

    # Remove the one-hot columns from the raw historical orders table to simulate raw enterprise inputs
    df_hist_raw = df_hist.drop(columns=["Fwd_DHL", "Fwd_ONE", "Fwd_Wanhai", "Fwd_Gemadept", "Internal_Mill", "Outsource_Mill"])

    # 4. Duplicates (Append 100 rows)
    dupes = df_hist_raw.sample(n=100, random_state=42)
    df_hist_raw = pd.concat([df_hist_raw, dupes], ignore_index=True)

    # Save historical raw dirty data to SQLite
    with get_db_connection() as conn:
        # Drop columns before writing so SQLite handles the new schema
        conn.execute("DROP TABLE IF EXISTS historical_orders;")
        df_hist_raw.to_sql("historical_orders", conn, if_exists="replace", index=False)
        print(f"  📦 Historical dirty orders saved to table 'historical_orders' ({len(df_hist_raw)} rows)")

    # ── Generate Current Active Orders ────────────────────────
    df_curr = _generate_base_data(CURRENT_ORDERS_COUNT, is_current=True)
    
    # Construct string representations for current orders too
    curr_fwd = []
    for idx, row in df_curr.iterrows():
        if row["Fwd_DHL"] == 1:
            curr_fwd.append("DHL")
        elif row["Fwd_ONE"] == 1:
            curr_fwd.append("ONE")
        elif row["Fwd_Wanhai"] == 1:
            curr_fwd.append("Wanhai")
        else:
            curr_fwd.append("Gemadept")
    df_curr["Forwarder"] = curr_fwd

    curr_mill = []
    for idx, row in df_curr.iterrows():
        if row["Internal_Mill"] == 1 and row["Outsource_Mill"] == 1:
            curr_mill.append("Both")
        elif row["Internal_Mill"] == 1:
            curr_mill.append("Internal")
        else:
            curr_mill.append("Outsource")
    df_curr["Mill_Source"] = curr_mill

    df_curr_raw = df_curr.drop(columns=["Fwd_DHL", "Fwd_ONE", "Fwd_Wanhai", "Fwd_Gemadept", "Internal_Mill", "Outsource_Mill"])

    with get_db_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS current_orders;")
        df_curr_raw.to_sql("current_orders", conn, if_exists="replace", index=False)
        print(f"  📋 Current active orders saved to table 'current_orders' ({CURRENT_ORDERS_COUNT} rows)")

    # ── Save CSV fallbacks for safety ─────────────────────────
    historical_path = DATA_DIR / "garment_logistics_data.csv"
    df_hist_raw.to_csv(historical_path, index=False)
    
    current_orders_path = DATA_DIR / "garment_current_orders.csv"
    df_curr_raw.to_csv(current_orders_path, index=False)

    # ── Build output summary ──────────────────────────────────
    # Counts based on dirty/clean distribution
    late_count = int((df_hist["Delivery_Status"] == "Late").sum())
    on_time_count = int((df_hist["Delivery_Status"] == "On-Time").sum())
    missing_sum = int(df_hist_raw.isnull().sum().sum())

    result = {
        "status": "success",
        "total_historical_records": len(df_hist_raw),
        "total_current_orders": CURRENT_ORDERS_COUNT,
        "class_distribution": {
            "Late": late_count,
            "On-Time": on_time_count,
            "Late_percentage": round(late_count / num_samples * 100, 2),
        },
        "missing_values": missing_sum,
        "columns": list(df_hist_raw.columns),
    }

    return json.dumps(result)

if __name__ == "__main__":
    res = generate_mock_logistics_data(10000)
    print("\nGenerator Result JSON:")
    print(res)
