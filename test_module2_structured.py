from enum import Enum
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# 1. Add the missing fields to LogAnalysis with clear Field(description="...") hints:
class LogAnalysis(BaseModel):
    severity: SeverityLevel = Field(
    description=f"Overall incident severity level. Allowed values: {', '.join([e.value for e in SeverityLevel])}"
    )
    error_code: int = Field(description="HTTP or system error code found in the log, or -1 if none exists")
    is_compromised: bool = Field(description="True if active unauthorized access succeeded, false otherwise")
    summary: str = Field(description="One-sentence technical summary of the event")
    recommended_fix: list[str] = Field(description="Concrete remediation steps to resolve or mitigate the issue")

# 2. Improve this system prompt so the model accurately classifies SIEM logs
SYSTEM_PROMPT = """
You are an expert SIEM and Linux Security Log Analyst. 
Your task is to analyze raw server logs, extract precise technical details, 
determine if a breach or unauthorized access successfully occurred, assess the severity, 
and provide actionable remediation steps.
"""

def parse_server_log(raw_log: str) -> LogAnalysis:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"Analyze the following raw server log:\n{raw_log}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=LogAnalysis,
        ),
    )
    # Validate and deserialize JSON string directly into the Pydantic object
    return LogAnalysis.model_validate_json(response.text)

if __name__ == "__main__":
    sample = (
        "2026-10-15 02:11:44 [ALERT] sshd[9012]: Accepted password for root "
        "from 198.51.100.77 port 44122 ssh2 (ErrorCode=401 bypassed via PAM bug)"
    )
    print(parse_server_log(sample).model_dump_json(indent=2))

# --- Automated Unit Test (Run with: pytest test_module2_structured.py) ---
def test_ssh_breach_log_parsing():
    sample_log = (
        "2026-10-15 02:11:44 [ALERT] sshd[9012]: Accepted password for root "
        "from 198.51.100.77 port 44122 ssh2 (ErrorCode=401 bypassed via PAM bug)"
    )
    result = parse_server_log(sample_log)

    assert result.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
    assert result.error_code == 401
    assert result.is_compromised is True
    assert len(result.recommended_fix) >= 1