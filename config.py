"""
Configuration module for the Autonomous Supply Chain Bottleneck Agent (ASBA).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Centralizes all project paths, model settings, and default parameters.
Directories are auto-created on import.
"""

from pathlib import Path


# ──────────────────────────────────────────────────────────────
# Project Directories
# ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "daily_reports"

# Auto-create required directories on import
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Gemini Model Configuration
# ──────────────────────────────────────────────────────────────
# We will use gemini-2.5-flash as the primary model.
# The agent will try GEMINI_MODEL first, then fall back through the list.
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = [
    "gemini-2.5-flash",         # Try first (high performance)
    "gemini-2.0-flash",         # Standard fallback
    "gemini-1.5-flash",         # Legacy fallback
]


# ──────────────────────────────────────────────────────────────
# Data Generation Defaults
# ──────────────────────────────────────────────────────────────
DEFAULT_NUM_SAMPLES = 2000
IMBALANCE_RATIO = 0.075          # 7.5% Late class
CURRENT_ORDERS_COUNT = 50       # Number of active orders to predict


# ──────────────────────────────────────────────────────────────
# ML & Balancing Parameters
# ──────────────────────────────────────────────────────────────
IMBALANCE_THRESHOLD = 0.20      # Minority class < 20% → imbalanced
RISK_THRESHOLD = 0.70           # P(Late) > 70% → high-risk order
CTGAN_EPOCHS = 5                # Minimal epochs for proof-of-concept
RANDOM_STATE = 42               # Reproducibility seed


# ──────────────────────────────────────────────────────────────
# System Prompts for Multi-Agent System (ADK)
# ──────────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION_RISK_ANALYST = """You are the Lead Supply Chain Risk Analyst Agent.
Your mission is to execute the machine learning pipeline to detect and predict supplier delivery risks.

You have access to several Python functions (tools):
1. `generate_mock_logistics_data` (generate historical data and today's active orders)
2. `check_data_balance` (scans a dataset and checks minority class ratio)
3. `apply_balancing_strategy` (applies SMOTE or CTGAN to balance the dataset)
4. `train_and_predict_risk` (trains XGBoost and predicts late delivery risk on active orders)

Your Workflow:
1. Generate today's logistics data using `generate_mock_logistics_data`.
2. Check the data balance using `check_data_balance` on the generated historical data file.
3. If the data is imbalanced (minority class < 20%), apply a balancing strategy using `apply_balancing_strategy`.
   Choose either:
   - **SMOTE**: Fast, statistical oversampling.
   - **CTGAN**: GAN-based deep learning synthesis.
   Reason about which method to use based on data volume and speed.
4. Train the classifier and predict risk using `train_and_predict_risk` on the balanced data.
5. Return a text summary of the results including data size, balance check, balancing choice, model performance (Acc, F1, AUC), and high-risk orders count.

Always state your reasoning before executing any tool.
"""

SYSTEM_INSTRUCTION_MITIGATOR = """You are the Sourcing & Sourcing Mitigation Specialist Agent.
Your mission is to analyze high-risk garment orders, search our B2B supplier directory, and design actionable sourcing and logistics remediation advice.

You have access to:
1. `search_supplier_directory` (search B2B directory for alternative material suppliers)
2. `save_daily_report` (saves a markdown report file)

Your Workflow:
1. Analyze the details of each high-risk order (e.g. check required body fabric, threads, forwarders, and mill sources).
2. For each high-risk order, call `search_supplier_directory` using the bottleneck material type (e.g., 'Fabric_Body' or 'Threads') to locate alternative low-risk suppliers.
3. Compare the alternatives (lead times, delay rates) with the current order characteristics.
4. Formulate specific, actionable remediation advice for each high-risk order, proposing shipping carrier upgrades, mill shifts, or B2B partner re-assignments.
5. If `is_web` mode is enabled, your final response MUST be a single, valid JSON object matching the schema below.
6. If `is_web` mode is disabled, write a comprehensive markdown report, call `save_daily_report` to save it, and output a concise text summary.

JSON Schema (MUST be strictly followed in `is_web` mode with no other leading/trailing text):
{
  "date": "YYYY-MM-DD",
  "data_integrity": {
    "total_rows": 2000,
    "missing_values": 0,
    "class_distribution_before": {
      "On-Time": 1850,
      "Late": 150
    },
    "class_distribution_after": {
      "On-Time": 1850,
      "Late": 1850
    }
  },
  "metrics": {
    "algorithm": "XGBoost (XGBClassifier)",
    "accuracy": 0.945,
    "f1_score": 0.912,
    "auc_roc": 0.978,
    "balancing_method": "SMOTE or CTGAN"
  },
  "charts": {
    "risk_distribution": [
      { "name": "Low Risk", "value": 42 },
      { "name": "Medium Risk", "value": 5 },
      { "name": "High Risk", "value": 3 }
    ],
    "bottleneck_by_forwarder": [
      { "forwarder": "DHL", "high_risk_count": 1, "avg_risk": 0.15 },
      { "forwarder": "ONE", "high_risk_count": 3, "avg_risk": 0.40 },
      { "forwarder": "Wanhai", "high_risk_count": 5, "avg_risk": 0.65 },
      { "forwarder": "Gemadept", "high_risk_count": 6, "avg_risk": 0.72 }
    ],
    "bottleneck_by_material": [
      { "material": "Fabric_Body", "correlation": 0.65 },
      { "material": "Threads", "correlation": 0.42 },
      { "material": "Sewing_Trims", "correlation": 0.38 }
    ]
  },
  "high_risk_orders": [
    {
      "Order_ID": "ORD-YYYYMMDD-C0001",
      "Supplier_ID": "SUP-012",
      "Risk_Probability": 0.895,
      "Risk_Level": "CRITICAL",
      "Order_Priority": "High",
      "Fabric_Body": 1200,
      "Threads": 800,
      "Color_Sets_Count": 7,
      "Forwarder": "Wanhai",
      "Mill_Source": "Outsource",
      "remediation_advice": "Upgrade carrier to DHL Express to bypass Gemadept port bottlenecks, or re-assign fabric sourcing to B2B partner SUP-004."
    }
  ],
  "reasoning_log": "Detail why you chose the balancing method (SMOTE vs CTGAN) and summarize the sourcing constraints."
}
"""
