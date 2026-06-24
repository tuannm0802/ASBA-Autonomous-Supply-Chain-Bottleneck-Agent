"""
Report Writer Tool for the ASBA system.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Saves the agent's daily risk assessment report as a rich markdown file
in the daily_reports/ directory.
"""

import json
from config import REPORTS_DIR


def save_daily_report(report_content: str, date_str: str) -> str:
    """Saves the agent's daily risk assessment report as a markdown file.

    The report should be a comprehensive markdown document containing:
    - Data Integrity Check (total rows, missing values)
    - Class Distribution Analysis (before and after balancing)
    - Model Performance metrics (accuracy, F1, AUC-ROC)
    - High-Risk Orders table with details
    - Remediation Recommendations for high-risk suppliers
    - Reasoning Log explaining the agent's balancing method choice

    Args:
        report_content: The full markdown-formatted report content.
        date_str: Date string for the filename (e.g. '20260621').

    Returns:
        A JSON-formatted string confirming the save location and status.
    """
    try:
        report_path = REPORTS_DIR / f"report_{date_str}.md"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        file_size = report_path.stat().st_size

        print(f"  💾 Report saved: {report_path} ({file_size:,} bytes)")

        result = {
            "status": "success",
            "report_path": str(report_path),
            "report_size_bytes": file_size,
            "message": f"Daily report saved successfully to {report_path}",
        }

        return json.dumps(result)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to save report: {str(e)}",
        })
