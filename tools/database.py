import sqlite3
import os
import sys
from pathlib import Path
from contextlib import contextmanager

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import DATA_DIR

DB_PATH = DATA_DIR / "supply_chain.db"

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connection.
    Enables WAL mode and returns the connection.
    """
    conn = sqlite3.connect(DB_PATH)
    # Enable Write-Ahead Logging (WAL) for better concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    """Initializes the database schema if tables do not exist."""
    print(f"  [DB] Initializing SQLite database at: {DB_PATH}")
    with get_db_connection() as conn:
        # 1. Historical raw dirty orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historical_orders (
                Order_ID TEXT PRIMARY KEY,
                Supplier_ID TEXT,
                Fabric_Trim REAL,
                Fabric_Rib REAL,
                Fabric_Body REAL,
                Fabric_CollarCuff REAL,
                Sewing_Trims REAL,
                Packing_Trims REAL,
                Interlining REAL,
                Threads REAL,
                Color_Sets_Count REAL,
                Fwd_DHL REAL,
                Fwd_ONE REAL,
                Fwd_Wanhai REAL,
                Fwd_Gemadept REAL,
                Internal_Mill REAL,
                Outsource_Mill REAL,
                Unit_Count REAL,
                Order_Value_USD REAL,
                Delay_Penalty_USD_Per_Day REAL,
                Shipping_Cost_USD REAL,
                Order_Priority TEXT,
                Delivery_Status TEXT
            );
        """)

        # 2. Historical cleaned orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cleaned_historical_orders (
                Order_ID TEXT PRIMARY KEY,
                Supplier_ID TEXT,
                Fabric_Trim REAL,
                Fabric_Rib REAL,
                Fabric_Body REAL,
                Fabric_CollarCuff REAL,
                Sewing_Trims REAL,
                Packing_Trims REAL,
                Interlining REAL,
                Threads REAL,
                Color_Sets_Count REAL,
                Fwd_DHL REAL,
                Fwd_ONE REAL,
                Fwd_Wanhai REAL,
                Fwd_Gemadept REAL,
                Internal_Mill REAL,
                Outsource_Mill REAL,
                Unit_Count REAL,
                Order_Value_USD REAL,
                Delay_Penalty_USD_Per_Day REAL,
                Shipping_Cost_USD REAL,
                Order_Priority TEXT,
                Delivery_Status TEXT
            );
        """)

        # 3. Current active orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS current_orders (
                Order_ID TEXT PRIMARY KEY,
                Supplier_ID TEXT,
                Fabric_Trim REAL,
                Fabric_Rib REAL,
                Fabric_Body REAL,
                Fabric_CollarCuff REAL,
                Sewing_Trims REAL,
                Packing_Trims REAL,
                Interlining REAL,
                Threads REAL,
                Color_Sets_Count REAL,
                Fwd_DHL REAL,
                Fwd_ONE REAL,
                Fwd_Wanhai REAL,
                Fwd_Gemadept REAL,
                Internal_Mill REAL,
                Outsource_Mill REAL,
                Unit_Count REAL,
                Order_Value_USD REAL,
                Delay_Penalty_USD_Per_Day REAL,
                Shipping_Cost_USD REAL,
                Order_Priority TEXT
            );
        """)

        # 4. Predictions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                Order_ID TEXT PRIMARY KEY,
                Risk_Probability REAL,
                Risk_Level TEXT,
                Prediction_Date TEXT
            );
        """)

        # 5. Mitigations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mitigations (
                Order_ID TEXT PRIMARY KEY,
                Mitigation_Type TEXT,
                New_Supplier_ID TEXT,
                New_Forwarder TEXT,
                New_Mill_Source TEXT,
                New_Risk_Probability REAL,
                New_Risk_Level TEXT,
                Mitigation_Date TEXT
            );
        """)

        # 6. Supplier directory table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS supplier_directory (
                Supplier_ID TEXT PRIMARY KEY,
                Supplier_Name TEXT,
                Material_Specialty TEXT,
                Lead_Time_Days INTEGER,
                Historical_Delay_Rate REAL,
                Internal_Mill INTEGER,
                Outsource_Mill INTEGER
            );
        """)
        print("  [DB] Database initialization complete.")

if __name__ == "__main__":
    init_database()
