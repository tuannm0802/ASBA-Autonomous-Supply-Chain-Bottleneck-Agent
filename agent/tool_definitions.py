"""
Tool Definitions & Dispatch Registry for the ASBA Agent.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Collects all tool functions into lists for the Gemini SDK to consume.
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from data_generator import generate_mock_logistics_data
from tools.balance_checker import check_data_balance
from tools.balancing import apply_balancing_strategy
from tools.ml_predictor import train_and_predict_risk
from tools.report_writer import save_daily_report
from tools.directory_lookup import search_supplier_directory

# Tools for the Risk Analyst Agent
ANALYST_TOOLS = [
    generate_mock_logistics_data,
    check_data_balance,
    apply_balancing_strategy,
    train_and_predict_risk,
]

# Tools for the Sourcing Mitigator Agent
MITIGATOR_TOOLS = [
    search_supplier_directory,
    save_daily_report,
]

# Combined list of all tools
TOOL_FUNCTIONS = ANALYST_TOOLS + MITIGATOR_TOOLS

# Dispatch table mapping function name (str) -> callable
TOOL_DISPATCH = {func.__name__: func for func in TOOL_FUNCTIONS}
