"""
Order Mitigation Script for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updates active order features in SQLite, runs cleaning pipeline,
re-predicts risk probability using the trained XGBoost model,
and updates database prediction/mitigation tables and the daily report.
"""

import sys
import os
import json
import pickle
import pandas as pd
import re
from pathlib import Path
from xgboost import XGBClassifier
from datetime import datetime

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Force UTF-8 on Windows
import io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import DATA_DIR, REPORTS_DIR, RANDOM_STATE, RISK_THRESHOLD
from tools.database import get_db_connection
from tools.data_cleaner import clean_dataset


def mitigate_active_order(order_id: str, mitigation_type: str, value: str = None) -> dict:
    """Applies a sourcing or logistics mitigation to an active order in SQLite,
    re-calculates risk using ML, and logs details to SQLite tables.
    """
    mitigation_type = mitigation_type.strip().lower()
    if value:
        value = value.strip()

    # Sync GCS bucket files before mitigation load (if cloud storage enabled)
    try:
        from tools.gcs_helper import sync_cloud_to_local, sync_local_to_cloud
        sync_cloud_to_local()
    except Exception:
        pass

    # ── 1. Load active current order from SQLite ──────────────
    with get_db_connection() as conn:
        df_curr = pd.read_sql("SELECT * FROM current_orders", conn)

    # Find the target order
    order_mask = df_curr["Order_ID"] == order_id
    if not order_mask.any():
        return {
            "status": "error",
            "message": f"Order ID '{order_id}' not found in active orders."
        }

    original_row = df_curr[order_mask].iloc[0].to_dict()

    # Query the original prediction risk to solve Bug 6
    orig_prob = 0.85
    orig_level = "HIGH"
    with get_db_connection() as conn:
        pred_row = conn.execute("SELECT Risk_Probability, Risk_Level FROM predictions WHERE Order_ID = ?", (order_id,)).fetchone()
        if pred_row:
            orig_prob = float(pred_row["Risk_Probability"])
            orig_level = str(pred_row["Risk_Level"])

    # ── 2. Apply Mitigation Changes in DataFrame ──────────────
    mitigation_applied = ""
    new_supplier = original_row.get("Supplier_ID")
    new_forwarder = original_row.get("Forwarder")
    new_mill_source = original_row.get("Mill_Source")

    if mitigation_type == "logistics":
        df_curr.loc[order_mask, "Forwarder"] = "DHL"
        new_forwarder = "DHL"
        mitigation_applied = "Upgraded shipping carrier to DHL Express"

    elif mitigation_type == "mill":
        df_curr.loc[order_mask, "Mill_Source"] = "Internal"
        new_mill_source = "Internal"
        mitigation_applied = "Switched fabric sourcing to Internal Mill"

    elif mitigation_type == "supplier":
        if not value:
            return {
                "status": "error",
                "message": "Mitigation type 'supplier' requires a target supplier ID."
            }

        # Look up supplier details in directory table in SQLite
        with get_db_connection() as conn:
            sup_row = conn.execute("SELECT * FROM supplier_directory WHERE Supplier_ID = ?", (value,)).fetchone()
            
        if not sup_row:
            return {
                "status": "error",
                "message": f"Alternative supplier '{value}' not found in directory."
            }

        # Determine mill source string based on flags
        int_mill = int(sup_row["Internal_Mill"])
        out_mill = int(sup_row["Outsource_Mill"])
        if int_mill == 1 and out_mill == 1:
            mill_val = "Both"
        elif int_mill == 1:
            mill_val = "Internal"
        else:
            mill_val = "Outsource"

        df_curr.loc[order_mask, "Supplier_ID"] = value
        df_curr.loc[order_mask, "Mill_Source"] = mill_val
        new_supplier = value
        new_mill_source = mill_val
        mitigation_applied = f"Re-assigned order to B2B partner {sup_row['Supplier_Name']} ({value})"

    else:
        return {
            "status": "error",
            "message": f"Unknown mitigation type '{mitigation_type}'"
        }

    # Save changes back to SQLite current_orders table
    with get_db_connection() as conn:
        conn.execute("DELETE FROM current_orders WHERE Order_ID = ?", (order_id,))
        # Write modified row back
        df_curr[order_mask].to_sql("current_orders", conn, if_exists="append", index=False)

    # ── 3. Run Cleaning Pipeline on updated orders ────────────
    # This generates 'cleaned_current_orders' with proper one-hot encoding columns!
    clean_dataset("current_orders")

    # Load cleaned order row
    with get_db_connection() as conn:
        df_cleaned_curr = pd.read_sql("SELECT * FROM cleaned_current_orders", conn)
    cleaned_order_mask = df_cleaned_curr["Order_ID"] == order_id
    updated_cleaned_df = df_cleaned_curr[cleaned_order_mask].copy()

    # ── 4. Re-run Prediction using Saved Model ────────────────
    model_path = DATA_DIR / "xgb_model.json"
    meta_path = DATA_DIR / "ml_metadata.pkl"

    if not model_path.exists() or not meta_path.exists():
        return {
            "status": "error",
            "message": "Trained model or encoders metadata not found. Run prediction pipeline first."
        }

    # Load model
    model = XGBClassifier()
    model.load_model(str(model_path))

    # Load encoders and meta
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)

    label_encoders = meta["label_encoders"]
    training_features = meta["training_features"]
    categorical_cols = meta["categorical_cols"]
    late_class_index = meta["late_class_index"]

    # Preprocess categorical features using loaded encoders
    X_order = updated_cleaned_df[training_features].copy()
    for col in categorical_cols:
        if col in X_order.columns:
            le = label_encoders[col]
            X_order[col] = X_order[col].apply(
                lambda val, _le=le: (
                    _le.transform([val])[0]
                    if val in _le.classes_
                    else 0
                )
            )

    # Re-predict risk probability
    new_proba = float(model.predict_proba(X_order)[0, late_class_index])

    # Determine new risk level
    if new_proba > 0.90:
        new_level = "CRITICAL"
    elif new_proba > RISK_THRESHOLD:
        new_level = "HIGH"
    elif new_proba > 0.40:
        new_level = "MEDIUM"
    else:
        new_level = "LOW"

    # ── 5. Write predictions and logs to SQLite tables ────────
    today_date = datetime.now().strftime("%Y-%m-%d")
    with get_db_connection() as conn:
        # Update predictions table
        conn.execute(
            "INSERT OR REPLACE INTO predictions (Order_ID, Risk_Probability, Risk_Level, Prediction_Date) VALUES (?, ?, ?, ?)",
            (order_id, new_proba, new_level, today_date)
        )
        # Log to mitigations table
        conn.execute(
            "INSERT OR REPLACE INTO mitigations (Order_ID, Mitigation_Type, New_Supplier_ID, New_Forwarder, New_Mill_Source, New_Risk_Probability, New_Risk_Level, Mitigation_Date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, mitigation_type, new_supplier, new_forwarder, new_mill_source, new_proba, new_level, today_date)
        )
        print(f"  [DB] Saved prediction & mitigation logs for order '{order_id}' to database.")

    # ── 6. Update the Saved Daily Report JSON ──────────────────
    report_files = sorted(list(REPORTS_DIR.glob("report_*.json")))
    report_updated = False
    
    if report_files:
        latest_report_path = report_files[-1]
        try:
            with open(latest_report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)

            # Update the order details in high_risk_orders list
            orders_list = report_data.get("high_risk_orders", [])
            for order in orders_list:
                if order["Order_ID"] == order_id:
                    order["Supplier_ID"] = new_supplier
                    order["Risk_Probability"] = round(new_proba, 4)
                    order["Risk_Level"] = new_level
                    order["Forwarder"] = new_forwarder
                    order["Mill_Source"] = new_mill_source
                    order["mitigated"] = True
                    order["mitigation_action"] = mitigation_applied
                    order["remediation_advice"] = f"✔️ RISK MITIGATED: {mitigation_applied}. Delivery risk successfully lowered to {new_proba*100:.1f}% ({new_level})."
                    
                    report_updated = True
                    break

            if report_updated:
                # Re-calculate high-risk counts in prediction summary
                active_high_risk = [o for o in orders_list if o.get("Risk_Level") in ["HIGH", "CRITICAL"] and not o.get("mitigated", False)]
                
                if "predictions_summary" in report_data:
                    report_data["predictions_summary"]["high_risk_count"] = len(active_high_risk)
                    
                    breakdown = report_data["predictions_summary"].get("risk_level_breakdown", {})
                    # Deduct from original level
                    if orig_level in breakdown and breakdown[orig_level] > 0:
                        breakdown[orig_level] -= 1
                    # Add to new level
                    if new_level in breakdown:
                        breakdown[new_level] += 1
                    else:
                        breakdown[new_level] = 1

                with open(latest_report_path, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2)

        except Exception as report_err:
            print(f"  ⚠️ Failed to update JSON report file: {report_err}")

    # ── 7. Sourcing Costs Calculations for decision-making ──
    try:
        unit_count = int(original_row.get("Unit_Count", 5000))
        order_val = float(original_row.get("Order_Value_USD", 50000.0))
        penalty_per_day = float(original_row.get("Delay_Penalty_USD_Per_Day", 500.0))
        orig_shipping = float(original_row.get("Shipping_Cost_USD", 3000.0))

        # Risk exposure formula: Prob * (5 days penalty + 15% order value for lost sales)
        def calc_exposure(prob):
            return round(prob * (penalty_per_day * 5.0 + order_val * 0.15), 2)

        cost_original = {
            "name": "Keep Original Sourcing",
            "shipping": orig_shipping,
            "premium": 0.0,
            "exposure": calc_exposure(orig_prob),
            "total": round(orig_shipping + calc_exposure(orig_prob), 2)
        }

        cost_dhl = {
            "name": "Upgrade Shipping (DHL)",
            "shipping": 10000.0,
            "premium": 0.0,
            "exposure": calc_exposure(0.02),
            "total": round(10000.0 + calc_exposure(0.02), 2)
        }

        cost_internal = {
            "name": "Switch to Internal Mill",
            "shipping": orig_shipping,
            "premium": round(unit_count * 0.50, 2),
            "exposure": calc_exposure(0.10),
            "total": round(orig_shipping + (unit_count * 0.50) + calc_exposure(0.10), 2)
        }

        cost_supplier = {
            "name": "Re-assign B2B Partner",
            "shipping": 3500.0,
            "premium": round(unit_count * 0.80, 2),
            "exposure": calc_exposure(0.04),
            "total": round(3500.0 + (unit_count * 0.80) + calc_exposure(0.04), 2)
        }

        cost_comparison = [cost_original, cost_dhl, cost_internal, cost_supplier]
    except Exception as cost_err:
        print(f"  ⚠️ Cost calculation failed: {cost_err}")
        cost_comparison = []

    # Sync local changes back to GCS bucket
    try:
        sync_local_to_cloud()
    except Exception:
        pass

    return {
        "status": "success",
        "order_id": order_id,
        "mitigation_applied": mitigation_applied,
        "previous_probability": round(orig_prob, 4),
        "new_probability": round(new_proba, 4),
        "new_risk_level": new_level,
        "updated_features": {
            "Supplier_ID": new_supplier,
            "Forwarder": new_forwarder,
            "Mill_Source": new_mill_source,
        },
        "cost_comparison": cost_comparison,
        "report_updated": report_updated
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "status": "error",
            "message": "Usage: python mitigate_order.py <order_id> <mitigation_type> [<supplier_id>]"
        }))
        return

    order_id = sys.argv[1].strip()
    mitigation_type = sys.argv[2].strip().lower()
    value = sys.argv[3].strip() if len(sys.argv) > 3 else None

    # ── Security validation regexes ──────────────────────────
    order_id_pattern = re.compile(r"^ORD-\d{8}-[CH]\d{4}$")
    supplier_id_pattern = re.compile(r"^(ALT-)?SUP-\d{3}$")

    if not order_id_pattern.match(order_id):
        print(json.dumps({
            "status": "error",
            "message": f"[SECURITY] Rejected malformed Order ID: {order_id}"
        }))
        return

    if mitigation_type not in ["logistics", "mill", "supplier"]:
        print(json.dumps({
            "status": "error",
            "message": f"[SECURITY] Rejected invalid mitigation type: {mitigation_type}"
        }))
        return

    if mitigation_type == "supplier":
        if not value or not supplier_id_pattern.match(value):
            print(json.dumps({
                "status": "error",
                "message": f"[SECURITY] Rejected invalid Supplier ID: {value}"
            }))
            return

    res = mitigate_active_order(order_id, mitigation_type, value)
    print(f"===REPORT_START===\n{json.dumps(res, indent=2)}\n===REPORT_END===")


if __name__ == "__main__":
    main()
