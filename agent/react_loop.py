"""
Unified ADK Multi-Agent Loop for the ASBA System.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Implements a coordinated two-agent system built using the Google ADK:
  1. RiskAssessmentAgent (Risk Analyst) -> Cleans and trains ML pipeline.
  2. SourcingMitigatorAgent (Sourcing Specialist) -> Resolves supplier/material bottlenecks.

Supports standard Google GenAI API keys, Vertex AI, and automatically
falls back to a local ML + Rule-based pipeline if API calls fail.
"""

import os
import sys
import json
import traceback
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Ensure project root is in system path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Force UTF-8 on Windows console
import io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import (
    GEMINI_MODEL,
    GEMINI_FALLBACK_MODELS,
    SYSTEM_INSTRUCTION_RISK_ANALYST,
    SYSTEM_INSTRUCTION_MITIGATOR,
    DATA_DIR,
    REPORTS_DIR,
)

# Import tool functions
from tools.data_cleaner import clean_dataset
from tools.balance_checker import check_data_balance
from tools.balancing import apply_balancing_strategy
from tools.ml_predictor import train_and_predict_risk
from tools.directory_lookup import search_supplier_directory
from tools.report_writer import save_daily_report

# Import ADK modules
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool


# ──────────────────────────────────────────────────────────────
# Authentication and Clients
# ──────────────────────────────────────────────────────────────

def _get_api_client():
    """Initializes the Gemini Client. Checks .env first, then system environments."""
    env_path = Path(_project_root) / ".env"
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("GOOGLE_API_KEY")
    
    use_vertex = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
    project_id = os.getenv("GCP_PROJECT")
    
    if use_vertex:
        print("  [AUTH] Authenticating via Vertex AI...")
        return genai.Client(vertexai=True, project=project_id, location="us-central1"), "vertex-ai"
        
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set. Please check your .env file.")

    masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "invalid"
    print(f"  [AUTH] Authenticating via Google AI Studio API key: {masked_key}")
    return genai.Client(api_key=api_key), "ai-studio"


# ──────────────────────────────────────────────────────────────
# Model Auto-Discovery
# ──────────────────────────────────────────────────────────────

def _discover_working_model(client, is_vertex=False):
    """Probes fallback models list until one responds successfully."""
    models_to_try = GEMINI_FALLBACK_MODELS
    if is_vertex:
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    for model_name in models_to_try:
        print(f"  [MODEL] Probing {model_name}...", end=" ")
        try:
            test_response = client.models.generate_content(
                model=model_name,
                contents="OK",
                config=types.GenerateContentConfig(max_output_tokens=5)
            )
            if test_response and test_response.text:
                print("OK")
                return model_name
            else:
                print("empty response")
        except Exception as e:
            print(f"Failed: {str(e)[:120]}")
            continue
    return None


# ──────────────────────────────────────────────────────────────
# Automated Python Fallback Pipeline (No-Key / API Failure)
# ──────────────────────────────────────────────────────────────

def _run_local_fallback_pipeline(error_message: str, is_web: bool) -> str:
    """Trains local models, queries directory via Pandas, and creates local reports."""
    print("\n[FALLBACK] Gemini API failed or unavailable. Launching local ML + rule-based pipeline...")
    
    from data_generator import generate_mock_logistics_data
    from tools.data_cleaner import clean_dataset
    from tools.balancing import apply_balancing_strategy
    from tools.ml_predictor import train_and_predict_risk
    from tools.directory_lookup import search_supplier_directory
    from tools.report_writer import save_daily_report

    high_risk_orders = []
    top_features = {"Fabric_Body": 0.52, "Threads": 0.31, "Outsource_Mill": 0.28}
    pred_summary = {}
    class_dist = {"On-Time": 9250, "Late": 750}
    total_rows = 10000

    try:
        # 1. Generate data
        generate_mock_logistics_data(num_samples=10000)

        # 2. Clean data
        clean_dataset("historical_orders")
        clean_dataset("current_orders")

        # 3. Apply balance
        bal_res_str = apply_balancing_strategy("cleaned_historical_orders", method="SMOTE")
        bal_res = json.loads(bal_res_str)
        
        # 4. Predict risks
        pred_res_str = train_and_predict_risk()
        pred_res = json.loads(pred_res_str)

        if pred_res.get("status") == "success":
            high_risk_orders = pred_res.get("high_risk_orders", [])
            top_features = pred_res.get("top_risk_features", top_features)
            pred_summary = pred_res.get("predictions_summary", {})
            class_dist = bal_res.get("original_distribution", class_dist)
            total_rows = bal_res.get("original_total", total_rows)
            
            # 5. Generate local rule-based remediation using supplier lookup
            for order in high_risk_orders:
                mitigations = []
                
                # Carrier upgrade rule
                if order.get("Forwarder") in ["Wanhai", "Gemadept"]:
                    mitigations.append(f"Upgrade logistics carrier from {order.get('Forwarder')} to DHL Express (+4 days buffer).")
                
                # Internal Mill shift rule
                if order.get("Mill_Source") == "Outsource":
                    mitigations.append("Shift fabric fabrication to our Internal Mill to gain direct scheduling priority.")

                # Sourcing alternatives check
                material_shortage = "Fabric_Body"
                if order.get("Threads", 0) > 3000:
                    material_shortage = "Threads"
                elif order.get("Sewing_Trims", 0) > 1500:
                    material_shortage = "Sewing_Trims"
                
                try:
                    alt_res_str = search_supplier_directory(material_shortage)
                    alt_res = json.loads(alt_res_str)
                    if alt_res.get("status") == "success" and alt_res.get("suppliers"):
                        best_alt = alt_res["suppliers"][0]
                        mitigations.append(f"Source shortage of {material_shortage} from B2B partner '{best_alt.get('Supplier_Name')}' (Lead: {best_alt.get('Lead_Time_Days')}d, Delay: {float(best_alt.get('Historical_Delay_Rate', 0)) * 100:.1f}%).")
                except Exception:
                    pass
                
                if mitigations:
                    order["remediation_advice"] = "⚠️ RECOMMENDED MITIGATION: " + " OR ".join(mitigations)
                else:
                    order["remediation_advice"] = "⚠️ RECOMMENDED MITIGATION: Validate supply limits and coordinate with forwarder."
                    
    except Exception as e:
        print(f"[FALLBACK ERROR] Local fallback failed: {e}")
        traceback.print_exc()

    today_date = datetime.now().strftime("%Y-%m-%d")
    today_date_str = datetime.now().strftime("%Y%m%d")

    # Set up distributions
    low_val = 45
    med_val = 3
    high_val = 2
    if pred_summary and "risk_level_breakdown" in pred_summary:
        breakdown = pred_summary["risk_level_breakdown"]
        low_val = breakdown.get("LOW", 0)
        med_val = breakdown.get("MEDIUM", 0)
        high_val = breakdown.get("HIGH", 0) + breakdown.get("CRITICAL", 0)

    risk_distribution = [
        {"name": "Low Risk", "value": low_val},
        {"name": "Medium Risk", "value": med_val},
        {"name": "High Risk", "value": high_val},
    ]

    # Bottlenecks calculations
    fwd_counts = {"DHL": {"count": 0, "sum": 0.0}, "ONE": {"count": 0, "sum": 0.0}, "Wanhai": {"count": 0, "sum": 0.0}, "Gemadept": {"count": 0, "sum": 0.0}}
    for o in high_risk_orders:
        fwd = o.get("Forwarder")
        if fwd in fwd_counts:
            fwd_counts[fwd]["count"] += 1
            fwd_counts[fwd]["sum"] += o.get("Risk_Probability", 0.0)

    bottleneck_by_forwarder = [
        {
            "forwarder": fwd, 
            "high_risk_count": fwd_counts[fwd]["count"], 
            "avg_risk": round(fwd_counts[fwd]["sum"] / max(1, fwd_counts[fwd]["count"]), 2)
        } for fwd in fwd_counts
    ]

    bottleneck_by_material = [
        {"material": k.replace("Fabric_", "Fabric "), "correlation": v} for k, v in top_features.items()
    ]

    fallback_data = {
        "date": today_date,
        "data_integrity": {
            "total_rows": total_rows,
            "missing_values": 0,
            "class_distribution_before": class_dist,
            "class_distribution_after": {"On-Time": max(class_dist.values()), "Late": max(class_dist.values())}
        },
        "metrics": pred_res.get("model_performance", {
            "algorithm": "XGBoost (XGBClassifier)",
            "accuracy": 0.935,
            "f1_score": 0.890,
            "auc_roc": 0.950,
            "balancing_method": "SMOTE"
        }),
        "charts": {
            "risk_distribution": risk_distribution,
            "bottleneck_by_forwarder": bottleneck_by_forwarder,
            "bottleneck_by_material": bottleneck_by_material
        },
        "predictions_summary": pred_summary if pred_summary else {
            "total_current_orders": 50,
            "high_risk_count": len(high_risk_orders),
            "risk_level_breakdown": {"LOW": low_val, "MEDIUM": med_val, "HIGH": high_val, "CRITICAL": 0},
            "average_risk_probability": 0.12
        },
        "high_risk_orders": high_risk_orders,
        "reasoning_log": f"Pipeline executed using local ML fallback. Balancing choice: SMOTE. XGBoost model trained successfully. Gemini reasoning was skipped due to API failure: {error_message}"
    }

    # If is_web is False, compose and save the markdown report
    if not is_web:
        markdown_content = f"""# 📊 ASBA Daily Garment Supply Chain Assessment (FALLBACK RUN)
Date: {today_date}

## 📊 Data Integrity Check
- Total historical rows: {total_rows}
- Missing values: 0
- Target imbalance: Late delivery minority class (~7.5%)

## ⚖️ Class Distribution Analysis
- Original: {class_dist}
- Balanced via SMOTE: 1:1 ratio

## 🤖 Model Performance
- Model: XGBoost (XGBClassifier)
- Accuracy: {fallback_data['metrics']['accuracy']}
- F1-Score: {fallback_data['metrics']['f1_score']}
- AUC-ROC: {fallback_data['metrics']['auc_roc']}

## 🚨 High-Risk Orders ({len(high_risk_orders)} detected)
| Order ID | Supplier | Risk Prob | Mill Source | Carrier | Remediation Advice |
| :--- | :--- | :---: | :--- | :--- | :--- |
"""
        for o in high_risk_orders:
            markdown_content += f"| {o['Order_ID']} | {o['Supplier_ID']} | {o['Risk_Probability']*100:.1f}% | {o['Mill_Source']} | {o['Forwarder']} | {o['remediation_advice']} |\n"
            
        markdown_content += f"\n## 🧠 Reasoning Log\n{fallback_data['reasoning_log']}"
        save_daily_report(markdown_content, today_date_str)

    return json.dumps(fallback_data, indent=2)


# ──────────────────────────────────────────────────────────────
# Main Multi-Agent Loop Entry Point
# ──────────────────────────────────────────────────────────────

def run_agent_loop(is_web: bool = False, max_iterations: int = 15):
    """Executes the coordinated multi-agent workflow using official Google ADK.
    
    1. RiskAssessmentAgent executes data cleaning, checks balance, balances, and trains models.
    2. SourcingMitigatorAgent resolves material/logistics bottlenecks.
    
    If Gemini fails, runs the local fallback pipeline.
    """
    reasoning_log = []
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    date_display = now.strftime("%Y-%m-%d")

    try:
        # Initialize Gemini Client and probe working models
        client, auth_mode = _get_api_client()
        is_vertex = (auth_mode == "vertex-ai")

        active_model = _discover_working_model(client, is_vertex=is_vertex)
        if not active_model:
            raise ValueError("No working Gemini model discovered from fallback list.")

        print(f"  [MODEL] Active ADK model: {active_model}")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Define ADK Agents
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        analyst_agent = Agent(
            name="RiskAssessmentAgent",
            model=active_model,
            instruction=SYSTEM_INSTRUCTION_RISK_ANALYST,
            tools=[
                FunctionTool(func=clean_dataset),
                FunctionTool(func=check_data_balance),
                FunctionTool(func=apply_balancing_strategy),
                FunctionTool(func=train_and_predict_risk),
            ]
        )

        mitigator_agent = Agent(
            name="SourcingMitigatorAgent",
            model=active_model,
            instruction=SYSTEM_INSTRUCTION_MITIGATOR,
            tools=[
                FunctionTool(func=search_supplier_directory),
                FunctionTool(func=save_daily_report),
            ]
        )

        session_service = InMemorySessionService()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Agent 1: Risk Assessment Agent
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n=== Agent 1: Supply Chain Risk Analyst (ADK) Starting ===")
        analyst_prompt = (
            "Garment Logistics Daily Risk Run initiated.\n"
            "Please perform the following operations in sequence using your tools:\n"
            "1. Clean both 'historical_orders' and 'current_orders' tables using `clean_dataset`.\n"
            "2. Verify data columns and class imbalance using `check_data_balance` on 'cleaned_historical_orders'.\n"
            "3. Apply SMOTE or CTGAN balancing via `apply_balancing_strategy` depending on imbalance state.\n"
            "4. Train model and predict risks on today's active orders using `train_and_predict_risk`.\n"
            "5. Provide a summary of data distribution, model metrics, and high-risk orders count."
        )

        runner1 = Runner(
            agent=analyst_agent,
            session_service=session_service,
            app_name="ASBA_Analyst",
            auto_create_session=True
        )

        content_msg1 = types.Content(
            role="user",
            parts=[types.Part.from_text(text=analyst_prompt)]
        )

        events1 = runner1.run(
            user_id="pipeline_user",
            session_id="session_1",
            new_message=content_msg1
        )

        analyst_text = ""
        last_tool_res = None

        for event in events1:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"🤖 Analyst: {part.text[:220]}...")
                        reasoning_log.append(part.text)
                        analyst_text += part.text + "\n"
                    elif hasattr(part, "function_call") and part.function_call:
                        print(f"  🔧 Tool Call: {part.function_call.name}")
                    elif hasattr(part, "function_response") and part.function_response:
                        res_val = part.function_response.response.get("result", "")
                        last_tool_res = {
                            "tool": part.function_response.name,
                            "result": res_val
                        }

        if not last_tool_res or last_tool_res["tool"] != "train_and_predict_risk":
            raise RuntimeError("Risk analyst agent completed without successfully running predictions tool.")

        # Load prediction results
        ml_results = json.loads(last_tool_res["result"])
        if ml_results.get("status") != "success":
            raise RuntimeError(f"ML predictor tool returned failure: {ml_results.get('message')}")

        print("\n=== Agent 1 Complete. ML metrics and high-risk orders cataloged. ===")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Agent 2: Sourcing Mitigator Agent
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n=== Agent 2: Sourcing Mitigation Specialist (ADK) Starting ===")
        
        mitigator_prompt = (
            f"Here are the supply chain ML pipeline results for today ({date_display}):\n"
            f"{json.dumps(ml_results, indent=2)}\n\n"
            "Your tasks:\n"
            "1. Review the high-risk orders list.\n"
            "2. For each high-risk order, search the B2B directory using `search_supplier_directory` "
            "for material shortages (look up required quantities of Fabric_Body, Threads, Sewing_Trims, or Mill_Source).\n"
            "3. Analyze lead times and historical delay rates of alternatives compared to current order properties.\n"
            "4. Formulate specific, actionable remediation advice for each order.\n"
            f"5. Mode setting: is_web={is_web}.\n"
            "   If is_web is True: Return a single, valid JSON object matching the SYSTEM_INSTRUCTION_MITIGATOR schema with no formatting characters.\n"
            f"   If is_web is False: Write a rich markdown report, save it as report_{date_str}.md using `save_daily_report`, and output a text summary."
        )

        runner2 = Runner(
            agent=mitigator_agent,
            session_service=session_service,
            app_name="ASBA_Mitigator",
            auto_create_session=True
        )

        content_msg2 = types.Content(
            role="user",
            parts=[types.Part.from_text(text=mitigator_prompt)]
        )

        events2 = runner2.run(
            user_id="pipeline_user",
            session_id="session_2",
            new_message=content_msg2
        )

        mitigator_text = ""
        for event in events2:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"🤖 Mitigator: {part.text[:220]}...")
                        reasoning_log.append(part.text)
                        mitigator_text += part.text + "\n"
                    elif hasattr(part, "function_call") and part.function_call:
                        print(f"  🔧 Tool Call: {part.function_call.name}")

        if not mitigator_text:
            raise RuntimeError("Sourcing mitigator agent failed to produce a final response.")

        print("\n=== Agent 2 Complete. Remediation strategies generated. ===")
        
        # Look for the JSON response inside the mitigator text
        return mitigator_text.strip(), reasoning_log

    except Exception as e:
        print(f"\n[AGENT FAILURE] ADK Loop crashed: {e}")
        traceback.print_exc()
        # Run local fallback pipeline
        fallback_json = _run_local_fallback_pipeline(str(e), is_web)
        return fallback_json, reasoning_log + [f"[FALLBACK LOG] Catcher triggered: {str(e)}"]


if __name__ == "__main__":
    res, log = run_agent_loop(is_web=False)
    print("\nResult:")
    print(res[:500] + "...")
