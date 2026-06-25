import sys
import os
import json
import traceback
from pathlib import Path

# Force UTF-8 on Windows
import io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agent.react_loop import _get_api_client, _discover_working_model
from agent.tool_definitions import MITIGATOR_TOOLS
from config import SYSTEM_INSTRUCTION_MITIGATOR

# Import ADK modules
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.events import Event
from google.genai import types


def run_chat_turn(message: str, history: list) -> dict:
    """Runs a single chat turn with SourcingMitigatorAgent using the ADK Runner."""
    reasoning_log = []
    
    try:
        # Initialize Gemini Client
        client, auth_mode = _get_api_client()
        is_vertex = (auth_mode == "vertex-ai")
        
        active_model = _discover_working_model(client, is_vertex)
        if not active_model:
            raise ValueError("No working Gemini model discovered.")
            
        # Build ADK Agent
        mitigator_agent = Agent(
            name="SourcingMitigatorAgent",
            model=active_model,
            instruction=SYSTEM_INSTRUCTION_MITIGATOR,
            tools=[FunctionTool(func=tool) for tool in MITIGATOR_TOOLS]
        )
        
        session_service = InMemorySessionService()
        runner = Runner(
            agent=mitigator_agent,
            session_service=session_service,
            app_name="ASBA_Chat",
            auto_create_session=True
        )
        
        # Initialize or fetch the session
        session = session_service.create_session_sync(
            app_name="ASBA_Chat",
            user_id="pipeline_user",
            session_id="chat_session"
        )
        
        # Reconstruct the conversation history into ADK session events
        for h in history:
            role = h.get("role", "user")
            text = h.get("text", "")
            if role in ["assistant", "model"]:
                role = "model"
                author = "SourcingMitigatorAgent"
            else:
                role = "user"
                author = "user"
            
            session.events.append(Event(
                content=types.Content(role=role, parts=[types.Part.from_text(text=text)]),
                author=author,
                invocation_id="seeded_history"
            ))
            
        # Run agent turn
        content_msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)]
        )
        
        events = runner.run(
            user_id="pipeline_user",
            session_id="chat_session",
            new_message=content_msg
        )
        
        final_text = ""
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text += part.text + "\n"
                        reasoning_log.append(f"[Reasoning] {part.text}")
                    elif hasattr(part, "function_call") and part.function_call:
                        func_name = part.function_call.name
                        func_args = dict(part.function_call.args) if part.function_call.args else {}
                        reasoning_log.append(f"[Tool Call] Called {func_name}({json.dumps(func_args)})")
                    elif hasattr(part, "function_response") and part.function_response:
                        res_val = part.function_response.response.get("result", "")
                        reasoning_log.append(f"[Tool Response] {part.function_response.name}: {res_val[:200]}")
                        
        return {
            "status": "success",
            "response": final_text.strip(),
            "reasoning_steps": reasoning_log
        }
        
    except Exception as e:
        # Rule-based local fallback for chat if API fails
        print(f"[CHAT FALLBACK] Gemini error: {e}", file=sys.stderr)
        
        lower_msg = message.lower()
        response_text = ""
        
        # Local supplier database fallback logic
        from tools.directory_lookup import search_supplier_directory
        
        if "fabric" in lower_msg:
            try:
                alts = json.loads(search_supplier_directory("Fabric_Body"))
                suppliers = alts.get("suppliers", [])
                formatted_alts = "\n".join([f"- **{a['Supplier_Name']}** ({a['Supplier_ID']}): delay rate {float(a['Historical_Delay_Rate']) * 100:.1f}%, lead time {a['Lead_Time_Days']} days" for a in suppliers])
                response_text = f"Gemini is offline, but my local rules fallback scanned the B2B Directory for **Fabric** alternatives:\n\n{formatted_alts}\n\nI recommend switching to a partner with an internal mill."
            except Exception:
                response_text = "I recommend checking Apex Fabrics Ltd (ALT-SUP-101) as a B2B partner for fabric body shortages."
        elif "threads" in lower_msg or "thread" in lower_msg:
            try:
                alts = json.loads(search_supplier_directory("Threads"))
                suppliers = alts.get("suppliers", [])
                formatted_alts = "\n".join([f"- **{a['Supplier_Name']}** ({a['Supplier_ID']}): delay rate {float(a['Historical_Delay_Rate']) * 100:.1f}%, lead time {a['Lead_Time_Days']} days" for a in suppliers])
                response_text = f"Gemini is offline, but my local rules fallback scanned the B2B Directory for **Threads** alternatives:\n\n{formatted_alts}"
            except Exception:
                response_text = "I recommend CoreThreads Textiles (ALT-SUP-108) as a B2B partner for threads shortages."
        elif "trim" in lower_msg or "trims" in lower_msg:
            try:
                alts = json.loads(search_supplier_directory("Sewing_Trims"))
                suppliers = alts.get("suppliers", [])
                formatted_alts = "\n".join([f"- **{a['Supplier_Name']}** ({a['Supplier_ID']}): delay rate {float(a['Historical_Delay_Rate']) * 100:.1f}%, lead time {a['Lead_Time_Days']} days" for a in suppliers])
                response_text = f"Gemini is offline, but my local rules fallback scanned the B2B Directory for **Sewing Trims** alternatives:\n\n{formatted_alts}"
            except Exception:
                response_text = "I recommend checking ALT-SUP-105 for packing and sewing trim bottlenecks."
        else:
            response_text = "Hello! I am your Sourcing Mitigation Specialist. Gemini is currently unavailable, but I can help you query material shortages. Try asking me about 'fabric alternative suppliers' or 'threads'."
            
        return {
            "status": "partial_success",
            "response": response_text,
            "reasoning_steps": [f"Local fallback triggered: {str(e)}"]
        }


def main():
    try:
        # Read JSON from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"status": "error", "message": "No input received."}))
            return
            
        payload = json.loads(input_data)
        message = payload.get("message", "")
        history = payload.get("history", [])
        
        result = run_chat_turn(message, history)
        print(f"===CHAT_START===\n{json.dumps(result, indent=2)}\n===CHAT_END===")
        
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }))


if __name__ == "__main__":
    main()
