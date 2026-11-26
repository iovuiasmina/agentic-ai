"""agent_core.py - the reusable agent harness built during Lab 3.

Ex1 builds run_agent() (the guarded ReAct loop).
Ex2 adds the approval policy layer (requires_approval + approver).
Ex3 reuses run_agent() for the orchestrator.
"""
import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()
client = genai.Client()
MODEL = os.getenv("LAB_MODEL", "gemini-3.5-flash-lite")  # fallback: gemini-3.1-flash-lite


# --------------------------------------------------------------------------
# Result object: what the caller gets back, whatever way the loop ended
# --------------------------------------------------------------------------
@dataclass
class AgentResult:
    answer: str
    stop_reason: str  # "done" | "max_steps" | "stuck" | "provider_error"
    steps: int
    prompt_tokens_per_step: list[int] = field(default_factory=list)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(self.prompt_tokens_per_step)


# --------------------------------------------------------------------------
# Ex2: the approval decision returned by a human (or a test)
# --------------------------------------------------------------------------
@dataclass
class Decision:
    approved: bool
    args: dict | None = None  # set when the operator EDITED the arguments
    feedback: str = ""        # free-text reason, sent back to the model


Approver = Callable[[str, dict], Decision]


def call_llm(contents, config, retries: int = 5):
    """One model call, with retry + exponential backoff on 429/5xx.
    Retries live in the client, NOT as loop steps (Course 2, slide 65)."""
    for attempt in range(retries):
        try:
            return client.models.generate_content(model=MODEL, contents=contents, config=config)
        except errors.APIError as e:
            if e.code in (429, 500, 503) and attempt < retries - 1:
                wait = 2 ** attempt * 5
                print(f"  .. provider error {e.code}, retrying in {wait}s")
                time.sleep(wait)
            else:
                raise


def execute_tool(tools_map: dict[str, Callable], name: str, args: dict) -> str:
    """Gate 1 (known tool?) + run. Every failure becomes a readable string, never a crash."""
    fn = tools_map.get(name)
    if fn is None:
        return f"ERROR: Unknown tool '{name}'. Available tools: {', '.join(tools_map)}."
    try:
        return str(fn(**args))
    except TypeError as e:  # wrong / missing arguments
        return f"ERROR: Bad arguments for {name}: {e}"
    except Exception as e:  # the tool itself failed
        return f"ERROR: {name} failed: {type(e).__name__}: {e}"


def run_agent(
    user_prompt: str,
    tools: list[Callable],
    system_instruction: str,
    max_steps: int = 8,
    requires_approval: frozenset[str] = frozenset(),
    approver: Approver | None = None,
    show_thoughts: bool = False,
    verbose: bool = True,
) -> AgentResult:
    tools_map = {fn.__name__: fn for fn in tools}
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        # Make the "Reason" in ReAct visible. flash-lite thinks minimally by default and returns
        # only an opaque thought_signature; thinking_level="high" + include_thoughts returns a summary.
        thinking_config=(types.ThinkingConfig(include_thoughts=True, thinking_level="high")
                         if show_thoughts else None),
        # No temperature override: Google recommends the default (1.0) for Gemini 3.
    )
    messages = [types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])]
    tokens: list[int] = []
    seen: Counter = Counter()

    for step in range(1, max_steps + 1):
        try:
            response = call_llm(messages, config)
        except errors.APIError as e:  # abnormal stop: report, don't crash (Course 2, slide 56)
            return AgentResult(f"STOPPED: provider error {e.code}: {e.message}", "provider_error", step, tokens)
        prompt_tokens = response.usage_metadata.prompt_token_count or 0
        tokens.append(prompt_tokens)
        if verbose:
            print(f"\n--- [Step {step}/{max_steps}] input tokens: {prompt_tokens:,} ---")

        content = response.candidates[0].content
        if verbose and content and content.parts:
            for part in content.parts:
                if part.thought and part.text:
                    print(f"  [Thought] {part.text.strip()[:300]}")

        # Stop condition A: no tool calls -> final answer
        if not response.function_calls:
            return AgentResult(response.text or "", "done", step, tokens)

        # 1. Append the model turn AS-IS (keeps Gemini 3 thought signatures)
        messages.append(content)

        # 2. Execute EVERY call, one function_response per call
        parts = []
        for call in response.function_calls:
            args = dict(call.args or {})
            if verbose:
                print(f"  -> [Tool Call] {call.name}({json.dumps(args)[:200]})")

            # Stuck-agent detector (Course 2, slide 65)
            key = (call.name, json.dumps(args, sort_keys=True))
            seen[key] += 1
            if seen[key] >= 3:
                return AgentResult(
                    f"STOPPED: '{call.name}' was called 3 times with the same arguments.",
                    "stuck", step, tokens,
                )
            if seen[key] == 2:
                output = "NOTE: Repeated call with identical arguments. Use the earlier result."
            # Ex2: policy layer - risky tools pause for a human BEFORE running
            elif call.name in requires_approval:
                decision = approver(call.name, args) if approver else Decision(False, feedback="no approver configured")
                if not decision.approved:
                    output = f"DENIED BY OPERATOR: {decision.feedback.rstrip('.') or 'no reason given'}. Adjust your plan."
                else:
                    final_args = decision.args or args
                    output = execute_tool(tools_map, call.name, final_args)
                    if decision.args:
                        output += f" (NOTE: the operator edited your arguments to {json.dumps(final_args)[:200]})"
            else:
                output = execute_tool(tools_map, call.name, args)

            if verbose:
                print(f"  <- [Tool Output] {output[:160]}")
            parts.append(types.Part(function_response=types.FunctionResponse(
                id=call.id, name=call.name, response={"result": output})))

        # 3. All results go back in ONE message. Gemini has no "tool" role:
        #    function responses travel in a role="user" turn (OpenAI would use role "tool").
        messages.append(types.Content(role="user", parts=parts))

    # Stop condition B: budget exhausted -> report partial progress, not a crash
    return AgentResult(
        f"STOPPED after {max_steps} steps without a final answer. "
        f"Tool calls made: {sum(seen.values())}. Raise max_steps or narrow the task.",
        "max_steps", max_steps, tokens,
    )