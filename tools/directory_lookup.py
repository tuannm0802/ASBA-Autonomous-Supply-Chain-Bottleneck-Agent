"""
Directory Lookup Tool for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Allows the agent to search the B2B suppliers directory in SQLite
to find alternative, low-risk sourcing options for materials.
"""

import pandas as pd
import json
import sys
import io
from pathlib import Path

# Force UTF-8 on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.database import get_db_connection

def search_supplier_directory(material_type: str) -> str:
    """Searches the B2B supplier directory for alternatives of a specific material.
    Reads from SQLite database table 'supplier_directory'.
    """
    try:
        # Load from SQLite database
        is_table = False
        with get_db_connection() as conn:
            try:
                conn.execute("SELECT 1 FROM supplier_directory LIMIT 1")
                is_table = True
            except Exception:
                pass

        if is_table:
            print("  [DIRECTORY] Loading B2B directory from SQLite table 'supplier_directory'")
            with get_db_connection() as conn:
                df = pd.read_sql("SELECT * FROM supplier_directory", conn)
        else:
            # Fallback path if table not loaded
            print("  [DIRECTORY] Fallback: Loading B2B directory from CSV")
            csv_path = _project_root / "data" / "garment_suppliers_directory.csv"
            if not csv_path.exists():
                csv_path = _project_root / "backend" / "data" / "garment_suppliers_directory.csv"
            if not csv_path.exists():
                csv_path = Path("data/garment_suppliers_directory.csv")
            df = pd.read_csv(csv_path)

        # ── Filter by material specialty ───────────────────────
        material_clean = material_type.strip().lower()
        matches = df[df["Material_Specialty"].str.lower().str.contains(material_clean)]

        if matches.empty:
            # Try splitting by underscores (e.g., Fabric_Body -> Fabric)
            short_term = material_clean.split("_")[0]
            matches = df[df["Material_Specialty"].str.lower().str.contains(short_term)]

        if matches.empty:
            return json.dumps({
                "status": "success",
                "message": f"No alternative suppliers found for specialty '{material_type}'.",
                "suppliers": []
            })

        suppliers = []
        for _, row in matches.iterrows():
            suppliers.append({
                "Supplier_ID": str(row["Supplier_ID"]),
                "Supplier_Name": str(row["Supplier_Name"]),
                "Material_Specialty": str(row["Material_Specialty"]),
                "Lead_Time_Days": int(row["Lead_Time_Days"]),
                "Historical_Delay_Rate": float(row["Historical_Delay_Rate"]),
                "Internal_Mill": int(row["Internal_Mill"]),
                "Outsource_Mill": int(row["Outsource_Mill"]),
            })

        result = {
            "status": "success",
            "material_queried": material_type,
            "total_alternatives_found": len(suppliers),
            "suppliers": suppliers
        }

        print(f"  🔍 B2B Sourcing search for '{material_type}': found {len(suppliers)} matches")
        return json.dumps(result)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to search supplier directory: {str(e)}",
        })

if __name__ == "__main__":
    res = search_supplier_directory("Fabric_Body")
    print("\nResult:")
    print(res)
