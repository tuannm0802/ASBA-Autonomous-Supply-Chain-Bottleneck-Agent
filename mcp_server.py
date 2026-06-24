"""
ASBA Model Context Protocol (MCP) Server.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Allows any MCP-compliant LLM client (like Claude Desktop or Cursor) to natively 
invoke the ASBA supply chain risk prediction and sourcing tools on the local machine.

Usage:
    python mcp_server.py
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Garment Supply Chain Bottleneck Agent (ASBA)")


@mcp.tool()
def generate_mock_logistics_data(num_samples: int = 2000) -> str:
    """Generates mock garment logistics dataset with imbalanced delivery statuses.
    
    Args:
        num_samples: Total number of historical records to generate (default 2000).
    """
    from data_generator import generate_mock_logistics_data as run_generator
    return run_generator(num_samples)


@mcp.tool()
def check_data_balance(filepath: str) -> str:
    """Checks the class balance of delivery status in a logistics dataset.
    
    Args:
        filepath: Path to the CSV dataset.
    """
    from tools.balance_checker import check_data_balance as run_check
    return run_check(filepath)


@mcp.tool()
def apply_balancing_strategy(filepath: str, method: str) -> str:
    """Applies a data balancing strategy (SMOTE or CTGAN) to handle class imbalance.
    
    Args:
        filepath: Path to the imbalanced CSV dataset.
        method: Sourcing method - 'SMOTE' (statistical) or 'CTGAN' (deep learning synthesis).
    """
    from tools.balancing import apply_balancing_strategy as run_balance
    return run_balance(filepath, method)


@mcp.tool()
def train_and_predict_risk(balanced_filepath: str, current_orders_filepath: str) -> str:
    """Trains an XGBoost classifier on balanced historical logistics data and predicts risks.
    
    Args:
        balanced_filepath: Path to the balanced training dataset CSV.
        current_orders_filepath: Path to the current active orders CSV.
    """
    from tools.ml_predictor import train_and_predict_risk as run_ml
    return run_ml(balanced_filepath, current_orders_filepath)


@mcp.tool()
def search_supplier_directory(material_type: str) -> str:
    """Searches the B2B supplier directory for low-risk alternative suppliers for a material.
    
    Args:
        material_type: Material category needed (e.g., 'Fabric_Body', 'Threads', 'Sewing_Trims').
    """
    from tools.directory_lookup import search_supplier_directory as run_lookup
    return run_lookup(material_type)


if __name__ == "__main__":
    mcp.run()
