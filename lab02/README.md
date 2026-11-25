# Lab 2 – Model Literacy, Prompt Engineering, Structured Outputs & Tool Calling

## Part 0: Warm-up

**1. 70B model in 4-bit.** Using the formula, VRAM ≈ (70 × 4/8) × 1.2 = 35 × 1.2 = 42 GB, so it doesn't fit on a single 24 GB GPU like an RTX 3090/4090. Actually even the weights alone are 35 GB, so the overhead doesn't even matter here. It could run on two 24 GB GPUs, with CPU offload in Ollama (but much slower), or with a ~2-bit quantization, with some quality loss. As a sanity check, qwen2.5:1.5b from Lab 1 gives 1.5 × 0.5 × 1.2 ≈ 0.9 GB, which matches its ~1 GB download.

**2. Mistral-7B-v0.3 vs Mistral-7B-Instruct-v0.3.** I would choose the Instruct one, since the base model only predicts the next token from web text and was never trained to follow a system prompt, respect roles or emit tool calls. For an agent that has to call JSON tools, those are exactly the abilities I need.

## Setup

I created a free Gemini API key in Google AI Studio and kept it in a .env file, which I added to .gitignore right away, so the key never ends up on GitHub. The smoke test answered "Telemetry online." I also had to install httpx manually (pip install httpx), because my version of google-genai didn't bring it as a dependency anymore.

## Module 1: Prompt engineering (module1_prompting.py)

I replaced the naive prompt with one built on the four pillars: role (Senior Linux Kernel & Cybersecurity Auditor), context with few-shot examples, hard constraints and an output contract. The user input is wrapped in <command> tags and the prompt says everything inside them is untrusted data, so the carbonara request is treated as a prompt injection, not as an instruction. I put the refusal string on its own line, without quotes, and added an example where the output is exactly the refusal, because otherwise the model tends to paraphrase it.

Result: the curl | sudo bash command was rated CRITICAL with exactly 3 bullet points, and the carbonara injection returned exactly "ACCESS DENIED: Scope limited to Linux Security Auditing.", so the assertion passed.

## Module 2: Structured outputs (test_module2_structured.py)

I extended LogAnalysis with severity (enum), error_code (int, -1 if there is none), is_compromised (bool) and recommended_fix (list), and wrote the rules both in the field descriptions and in the system prompt. Since the response_schema forces the model to follow the schema, the output is always valid JSON with the right types, but whether the values are correct still depends on the prompt, which is why the test checks the values and not just the parsing.

Result: severity CRITICAL, error_code 401, is_compromised true, and pytest passed (1 passed).

## Module 3: Tool calling (module3_tools.py)

I completed the round-trip: the model asked for lookup_cve_details with CVE-2024-3094, my code ran the function locally, and I sent the result back as a role="user" message (Gemini has no "tool" role), after appending the model's turn unchanged so the thought_signature is kept. The final answer used the data from my function (xz-utils 5.6.0 and 5.6.1, CVSS 10.0). What I noticed is that the model also added details that weren't in my function (like who discovered the backdoor), basically from its own training data, so a stricter prompt would be needed if I wanted it to rely only on the tools.

## Homework: David vs. Goliath

I ran each configuration 3 times:

| Model | Naive | Engineered | Engineered + --predecode |
|---|---|---|---|
| gemini-3.5-flash-lite | 3/3 | 3/3 | not needed |
| qwen2.5:1.5b | 0/3 | 0/3 (injection 3/3, severity 3/3, decode 0/3) | 3/3 |

With the naive prompt, qwen just copied the hex string, didn't detect the injection and set severity to LOW, so it basically did exactly what the attacker asked in user_note. Gemini passed even with the naive prompt, since it is a thinking model.

With the engineered prompt and schema (reasoning_trace first, decisions before the long decode, enum for severity, few-shot as real chat turns with a different payload and injection), qwen detected the injection and set HIGH in all 3 runs, but it still couldn't decode the hex and wrote an invented SSH banner instead (SSH-2.0-OpenSSH_8.1 or 7.6), probably because of dpt=22 in the log. Interestingly, the output wasn't identical in every run, even at temperature 0.

With --predecode, the hex is decoded by my Python code (bytes.fromhex) and passed to the model as a [harness] line, and then qwen passed in all 3 runs. Even then the hex_walkthrough was still wrong, but the decoded_payload was correct because the model copied it from the harness line.

**Why --predecode is safe:** the decoded line is produced by my own code from bytes that are already in the log, so it doesn't add any new attacker-controlled instructions, only a faithful transformation of data the model already sees. It is placed outside the <log> tags and labeled [harness], so the model can tell trusted output apart from untrusted input.

## Running

```
pip install google-genai pydantic python-dotenv pytest httpx
python smoke_test.py
python module1_prompting.py
pytest test_module2_structured.py
python module3_tools.py
python homework_naive.py [gemini-3.5-flash-lite]
python homework_david_vs_goliath.py [ollama::qwen2.5:1.5b] [--predecode]
```

A .env file with GEMINI_API_KEY is needed in this folder, and Ollama must be running for the qwen runs.