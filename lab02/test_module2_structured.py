from enum import Enum
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

load_dotenv()
# Free tier returns 429/503 under load: let the SDK retry with exponential backoff.
client = genai.Client(
    http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=6, initial_delay=2.0))
)


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LogAnalysis(BaseModel):
    severity: SeverityLevel = Field(
        description="LOW=routine, MEDIUM=suspicious but no impact, "
        "HIGH=attack in progress or failed privilege escalation, "
        "CRITICAL=successful unauthorized access or root compromise"
    )
    error_code: int = Field(
        description="Numeric HTTP/system error code literally present in the log "
        "(e.g. ErrorCode=401 -> 401, status 503 -> 503). Use -1 if no code appears."
    )
    is_compromised: bool = Field(
        description="true ONLY if the log shows unauthorized access that SUCCEEDED "
        "(e.g. 'Accepted password' for an attacker, auth bypass). false for failed/blocked attempts."
    )
    summary: str = Field(description="One-sentence technical summary of the event")
    recommended_fix: list[str] = Field(
        description="Concrete remediation steps, each an actionable command or config change"
    )


SYSTEM_PROMPT = """\
You are a SIEM triage engine for a Linux production fleet. You receive one raw log line
and return a structured incident record that matches the JSON schema exactly.

Rules:
- severity: CRITICAL if an attacker or untrusted IP successfully authenticated, gained root,
  or bypassed authentication; HIGH for active attacks or failed privilege escalation;
  MEDIUM for suspicious but contained activity; LOW for routine events.
- error_code: copy the numeric code that appears in the log (ErrorCode=, status=, code=, HTTP xxx).
  If no code is present, use -1. Never invent a code.
- is_compromised: true only when unauthorized access actually succeeded.
- summary: exactly one sentence, technical, no speculation beyond the log.
- recommended_fix: 2-4 concrete steps (commands or config changes), most urgent first.

Example:
Log: 2026-03-02 10:00:01 sshd[311]: Failed password for invalid user admin from 203.0.113.9 port 5022 ssh2
Output: {"severity": "MEDIUM", "error_code": -1, "is_compromised": false,
"summary": "Failed SSH password login for non-existent user 'admin' from external IP 203.0.113.9.",
"recommended_fix": ["Enable fail2ban for sshd", "Set PasswordAuthentication no in /etc/ssh/sshd_config"]}
"""


def parse_server_log(raw_log: str) -> LogAnalysis:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"Analyze the following raw server log:\n<log>{raw_log}</log>",
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