"""
Autonomous Supply Chain Bottleneck Agent (ASBA) - CLI Interface
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    python main.py --assess
    python main.py --mitigate <order_id> <logistics|mill|supplier> [<value>]
    python main.py --interactive
"""

import sys
import argparse
import json
import traceback
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows
import io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agent.react_loop import run_agent_loop, _get_api_client, _discover_working_model
from backend.mitigate_order import mitigate_active_order
from config import SYSTEM_INSTRUCTION_MITIGATOR, REPORTS_DIR


def print_banner():
    print()
    print("+" + "=" * 66 + "+")
    print("|    ASBA - Autonomous Supply Chain Bottleneck Agent               |")
    print("|    ----------------------------------------------------------    |")
    print("|    Daily Risk Assessment CLI Tool                                |")
    print(f"|    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<45} |")
    print("+" + "=" * 66 + "+")
    print()


def run_assessment():
    print("[INFO] Launching Multi-Agent Supply Chain Risk assessment pipeline...")
    
    try:
        final_response, reasoning_log = run_agent_loop(is_web=False)
        
        print("\n" + "=" * 68)
        print("✅ ASSIGNMENT DONE: ASBA pipeline completed.")
        print(f"Reasoning steps recorded: {len(reasoning_log)}")
        print(f"Report files saved in: {REPORTS_DIR.resolve()}")
        print("=" * 68)
        
        if final_response:
            print("\n📋 Executive Summary:")
            print(final_response[:1000] + ("..." if len(final_response) > 1000 else ""))
            
    except Exception as e:
        print(f"\n[FATAL] Pipeline failed: {e}")
        sys.exit(1)


def run_mitigation(order_id, mit_type, value):
    print(f"[INFO] Applying mitigation '{mit_type}' to order '{order_id}'...")
    res = mitigate_active_order(order_id, mit_type, value)
    
    if res.get("status") == "error":
        print(f"\n❌ Mitigation Failed: {res.get('message')}")
        sys.exit(1)
        
    print("\n✅ Mitigation Applied Successfully!")
    print(f"Action: {res.get('mitigation_applied')}")
    print(f"Risk Probability: {res.get('previous_probability')*100:.1f}% ➡️ {res.get('new_probability')*100:.1f}% ({res.get('new_risk_level')})")
    
    cost_comp = res.get("cost_comparison", [])
    if cost_comp:
        print("\n💵 Financial Risk & Cost Trade-off Comparison:")
        print(f"{'Mitigation Strategy':<28} | {'Shipping Cost':<13} | {'Sourcing Prem':<13} | {'Risk Exposure':<13} | {'Total Cost':<12}")
        print("-" * 88)
        for c in cost_comp:
            name = c.get("name")
            ship = f"${c.get('shipping'):,.2f}"
            prem = f"${c.get('premium'):,.2f}"
            exp = f"${c.get('exposure'):,.2f}"
            total = f"${c.get('total'):,.2f}"
            
            # Highlight original row vs current row
            if "Original" in name:
                print(f"\033[91m{name:<28} | {ship:<13} | {prem:<13} | {exp:<13} | {total:<12}\033[0m")
            elif res.get("mitigation_applied") in name or (mit_type == 'logistics' and 'DHL' in name) or (mit_type == 'mill' and 'Internal' in name) or (mit_type == 'supplier' and 'Partner' in name):
                print(f"\033[92m{name:<28} | {ship:<13} | {prem:<13} | {exp:<13} | {total:<12}\033[0m")
            else:
                print(f"{name:<28} | {ship:<13} | {prem:<13} | {exp:<13} | {total:<12}")


def run_interactive_chat():
    from google.genai import types
    from agent.tool_definitions import TOOL_DISPATCH, MITIGATOR_TOOLS
    import re
    
    print_banner()
    print("[INFO] Starting interactive Sourcing Specialist Agent chat session...")
    
    try:
        client, auth_mode = _get_api_client()
        is_vertex = (auth_mode == "vertex-ai")
        active_model = _discover_working_model(client, is_vertex)
        if not active_model:
            print("❌ No working Gemini model discovered. Exiting.")
            return
            
        print(f"[OK] Agent Ready (Model: {active_model}, Auth: {auth_mode})")
        print("Type 'exit' or 'quit' to terminate the session.")
        print("-" * 68)

        # Introduction prompt to establish context
        print("\n🤖 Agent: Initializing dashboard overview...")
        intro_prompt = (
            "You are the Sourcing Mitigation Specialist. Establish contact with the user, introduce yourself briefly, "
            "and tell them you are ready to analyze bottlenecks or search the supplier directory for high-risk orders. "
            "Expose the list of available material Specialties they can query (Fabric_Body, Threads, Sewing_Trims)."
        )
        
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_MITIGATOR,
            tools=MITIGATOR_TOOLS,
            temperature=0.4,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        
        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=intro_prompt)])
        ]
        
        # Run agent introduction
        response = client.models.generate_content(
            model=active_model,
            contents=contents,
            config=config
        )
        
        contents.append(response.candidates[0].content)
        if response.text:
            print(f"\n🤖 Agent:\n{response.text}")
            
        while True:
            try:
                user_msg = input("\n👤 User > ")
                if not user_msg.strip():
                    continue
                if user_msg.lower() in ["exit", "quit"]:
                    print("\n[INFO] Chat session terminated.")
                    break
                    
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])
                )
                
                # Execute conversational agent ReAct loop for this message
                for iteration in range(1, 10):
                    response = client.models.generate_content(
                        model=active_model,
                        contents=contents,
                        config=config
                    )
                    
                    candidate = response.candidates[0]
                    contents.append(candidate.content)
                    
                    if not response.function_calls:
                        if response.text:
                            print(f"\n🤖 Agent:\n{response.text}")
                        break
                        
                    # Process function calls
                    func_response_parts = []
                    for func_call in response.function_calls:
                        func_name = func_call.name
                        func_args = dict(func_call.args) if func_call.args else {}
                        
                        print(f"  🔧 Tool: {func_name}({json.dumps(func_args)})")
                        
                        if func_name in TOOL_DISPATCH:
                            try:
                                tool_res = TOOL_DISPATCH[func_name](**func_args)
                            except Exception as te:
                                tool_res = json.dumps({"status": "error", "message": str(te)})
                        else:
                            tool_res = json.dumps({"status": "error", "message": f"Unknown tool {func_name}"})
                            
                        func_response_parts.append(
                            types.Part.from_function_response(
                                name=func_name,
                                response={"result": tool_res}
                            )
                        )
                        
                    contents.append(
                        types.Content(role="tool", parts=func_response_parts)
                    )
                    
            except KeyboardInterrupt:
                print("\n[INFO] Use 'exit' to quit.")
                continue
                
    except Exception as e:
        print(f"\n❌ Agent connection failed: {e}")
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="ASBA Supply Chain Risk Agent CLI Interface")
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument("--assess", action="store_true", help="Trigger the daily supply chain risk assessment pipeline")
    group.add_argument("--mitigate", nargs=2, metavar=("ORDER_ID", "MITIGATION_TYPE"), help="Apply mitigation (logistics, mill, or supplier)")
    group.add_argument("--interactive", action="store_true", help="Start an interactive chat session with the sourcing agent")
    
    parser.add_argument("--value", help="Alternative supplier ID (required if mitigation type is 'supplier')")
    
    args = parser.parse_args()
    
    if args.assess:
        print_banner()
        run_assessment()
    elif args.mitigate:
        order_id, mit_type = args.mitigate
        run_mitigation(order_id, mit_type, args.value)
    elif args.interactive:
        run_interactive_chat()


if __name__ == "__main__":
    main()
