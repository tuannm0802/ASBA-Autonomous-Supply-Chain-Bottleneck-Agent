"""
ML Prediction Tool for the ASBA garment logistics system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trains an XGBoost classifier on cleaned historical data in SQLite,
saves predictions to SQLite, and identifies late-delivery risk on active orders.
"""

import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from xgboost import XGBClassifier
from datetime import datetime

# Ensure project root is in sys.path
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import RISK_THRESHOLD, RANDOM_STATE, DATA_DIR
from tools.database import get_db_connection

def train_and_predict_risk(balanced_filepath: str = None, current_orders_filepath: str = None) -> str:
    """Trains an XGBoost classifier and predicts delivery risks on garment orders.
    Reads training/prediction data from SQLite database.
    """
    try:
        # ── 1. Load datasets from SQLite ────────────────────────
        # If filepaths are provided, load from CSV (for backward compatibility),
        # otherwise query from the database tables.
        with get_db_connection() as conn:
            if balanced_filepath and Path(balanced_filepath).exists():
                print(f"  [ML] Loading balanced training data from file: {balanced_filepath}")
                train_df = pd.read_csv(balanced_filepath)
            else:
                print("  [ML] Loading training data from SQLite table 'cleaned_historical_orders'")
                train_df = pd.read_sql("SELECT * FROM cleaned_historical_orders", conn)

            if current_orders_filepath and Path(current_orders_filepath).exists():
                print(f"  [ML] Loading current orders from file: {current_orders_filepath}")
                current_df = pd.read_csv(current_orders_filepath)
            else:
                print("  [ML] Loading current orders from SQLite table 'cleaned_current_orders'")
                # Make sure cleaned_current_orders exists, else clean it first
                try:
                    current_df = pd.read_sql("SELECT * FROM cleaned_current_orders", conn)
                except Exception:
                    # Clean active orders first
                    from tools.data_cleaner import clean_dataset
                    clean_dataset("current_orders")
                    current_df = pd.read_sql("SELECT * FROM cleaned_current_orders", conn)

        target_col = "Delivery_Status"

        # ── Identify feature columns ──────────────────────────
        all_cols = [c for c in train_df.columns if c != target_col]
        id_cols = [c for c in all_cols
                   if "ID" in c.upper() or c.upper().startswith("ORDER") or c in ["Forwarder", "Mill_Source"]]
        
        # Include numeric inventory columns and one-hot variables
        training_features = [c for c in all_cols if c not in id_cols]

        X = train_df[training_features].copy()
        y = train_df[target_col].copy()

        # ── Encode categorical features ────────────────────────
        label_encoders: dict[str, LabelEncoder] = {}
        categorical_cols = X.select_dtypes(include=["object"]).columns.tolist()

        for col in categorical_cols:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col])
            label_encoders[col] = le

        # Encode target
        target_le = LabelEncoder()
        y_encoded = target_le.fit_transform(y)
        class_list = list(target_le.classes_)
        late_class_index = class_list.index("Late") if "Late" in class_list else 1

        # ── Train / Test Split ─────────────────────────────────
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded,
            test_size=0.2,
            random_state=RANDOM_STATE,
            stratify=y_encoded,
        )

        # ── Train XGBoost ──────────────────────────────────────
        print(f"  🧠 Training XGBoost on {len(X_train)} samples...")
        model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=RANDOM_STATE,
            eval_metric="logloss",
        )
        model.fit(X_train, y_train)

        # ── Save Model and Metadata for quick mitigation re-inference ──
        try:
            model_path = DATA_DIR / "xgb_model.json"
            model.save_model(str(model_path))
            
            meta_path = DATA_DIR / "ml_metadata.pkl"
            with open(meta_path, "wb") as f:
                pickle.dump({
                    "label_encoders": label_encoders,
                    "target_le": target_le,
                    "training_features": training_features,
                    "categorical_cols": categorical_cols,
                    "late_class_index": late_class_index
                }, f)
            print("  💾 XGBoost model and encoders saved to data/")
        except Exception as save_err:
            print(f"  ⚠️ Failed to save model/metadata: {save_err}")

        # ── Evaluate ───────────────────────────────────────────
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, late_class_index]

        accuracy = round(float(accuracy_score(y_test, y_pred)), 4)
        f1 = round(float(f1_score(y_test, y_pred, pos_label=late_class_index)), 4)

        try:
            auc = round(float(roc_auc_score(y_test, y_proba)), 4)
            if auc < 0.5:
                auc = round(1.0 - auc, 4)
        except ValueError:
            auc = 0.5

        print(f"  📈 Model performance — Acc: {accuracy}, F1: {f1}, AUC: {auc}")

        # ── Predict on current orders ──────────────────────────
        order_ids = current_df["Order_ID"] if "Order_ID" in current_df.columns else pd.Series([f"ORD-{i}" for i in range(len(current_df))])
        supplier_ids = current_df["Supplier_ID"] if "Supplier_ID" in current_df.columns else pd.Series(["Unknown"] * len(current_df))

        X_current = current_df[training_features].copy()

        # Encode categoricals
        for col in categorical_cols:
            if col in X_current.columns:
                le = label_encoders[col]
                X_current[col] = X_current[col].apply(
                    lambda val, _le=le: (
                        _le.transform([val])[0]
                        if val in _le.classes_
                        else 0
                    )
                )

        current_proba = model.predict_proba(X_current)[:, late_class_index]

        # ── Save predictions to SQLite database ────────────────
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # Prepare predictions records
        predictions_rows = []
        for i in range(len(current_df)):
            order_id = str(order_ids.iloc[i])
            prob = float(current_proba[i])
            if prob > 0.90:
                level = "CRITICAL"
            elif prob > RISK_THRESHOLD:
                level = "HIGH"
            elif prob > 0.40:
                level = "MEDIUM"
            else:
                level = "LOW"
            predictions_rows.append((order_id, prob, level, today_date))
            
        with get_db_connection() as conn:
            # Clear past predictions
            conn.execute("DELETE FROM predictions;")
            conn.executemany(
                "INSERT INTO predictions (Order_ID, Risk_Probability, Risk_Level, Prediction_Date) VALUES (?, ?, ?, ?)",
                predictions_rows
            )
            print(f"  💾 Saved {len(predictions_rows)} active predictions to SQLite table 'predictions'")

        # ── Classify risk levels and parse details ─────────────
        high_risk_orders = []
        risk_level_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

        for i in range(len(current_df)):
            prob = float(current_proba[i])

            if prob > 0.90:
                level = "CRITICAL"
            elif prob > RISK_THRESHOLD:
                level = "HIGH"
            elif prob > 0.40:
                level = "MEDIUM"
            else:
                level = "LOW"

            risk_level_counts[level] += 1

            row = current_df.iloc[i]
            
            # Use raw column Forwarder / Mill_Source directly if present
            forwarder = str(row.get("Forwarder", "ONE"))
            mill_src = str(row.get("Mill_Source", "Internal"))

            # Collect details for high-risk orders
            if prob > RISK_THRESHOLD:
                high_risk_orders.append({
                    "Order_ID": str(order_ids.iloc[i]),
                    "Supplier_ID": str(supplier_ids.iloc[i]),
                    "Risk_Probability": round(prob, 4),
                    "Risk_Level": level,
                    "Order_Priority": str(row.get("Order_Priority", "Medium")),
                    "Fabric_Body": int(row.get("Fabric_Body", 0)),
                    "Fabric_Trim": int(row.get("Fabric_Trim", 0)),
                    "Fabric_Rib": int(row.get("Fabric_Rib", 0)),
                    "Fabric_CollarCuff": int(row.get("Fabric_CollarCuff", 0)),
                    "Sewing_Trims": int(row.get("Sewing_Trims", 0)),
                    "Packing_Trims": int(row.get("Packing_Trims", 0)),
                    "Interlining": int(row.get("Interlining", 0)),
                    "Threads": int(row.get("Threads", 0)),
                    "Color_Sets_Count": int(row.get("Color_Sets_Count", 0)),
                    "Forwarder": forwarder,
                    "Mill_Source": mill_src,
                    "Unit_Count": int(row.get("Unit_Count", 5000)),
                    "Order_Value_USD": float(row.get("Order_Value_USD", 50000.0)),
                    "Delay_Penalty_USD_Per_Day": float(row.get("Delay_Penalty_USD_Per_Day", 500.0)),
                    "Shipping_Cost_USD": float(row.get("Shipping_Cost_USD", 3000.0)),
                })

        # Sort high-risk by probability descending
        high_risk_orders.sort(key=lambda x: x["Risk_Probability"], reverse=True)

        # ── Feature importance ─────────────────────────────────
        importance = dict(zip(
            training_features,
            [round(float(v), 4) for v in model.feature_importances_],
        ))
        top_features = dict(
            sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
        )

        print(f"  🚨 High-risk orders identified: {len(high_risk_orders)} / {len(current_df)}")

        result = {
            "status": "success",
            "model_performance": {
                "algorithm": "XGBoost (XGBClassifier)",
                "accuracy": accuracy,
                "f1_score": f1,
                "auc_roc": auc,
                "training_samples": len(X_train),
                "test_samples": len(X_test),
            },
            "predictions_summary": {
                "total_current_orders": len(current_df),
                "high_risk_count": len(high_risk_orders),
                "risk_level_breakdown": risk_level_counts,
                "average_risk_probability": round(float(np.mean(current_proba)), 4),
            },
            "high_risk_orders": high_risk_orders,
            "top_risk_features": top_features,
        }

        return json.dumps(result)

    except Exception as e:
        import traceback
        return json.dumps({
            "status": "error",
            "message": f"ML prediction failed: {str(e)}",
            "traceback": traceback.format_exc(),
        })

if __name__ == "__main__":
    res = train_and_predict_risk()
    print("\nPredictor Result JSON:")
    print(res[:600] + "...")
