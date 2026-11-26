# Lab 3 – The ReAct Loop, Human-in-the-Loop & Orchestrator-Workers

I reused the virtual environment from Lab 2 and moved the .env file to the root of the repo, since load_dotenv() also searches the parent folders, so both lab02 and lab03 find it.

## Exercise 1: The guarded ReAct loop

In agent_core.py I built run_agent(), which basically repeats the same cycle: the model decides what it needs, asks for tools, my code runs them and appends the results to the history, until the model answers in text. Every failure (unknown tool, bad arguments, an exception inside the tool) becomes an "ERROR: ..." string instead of a crash, so the model can read it and fix its next call. All the calls from one turn are executed and their results go back in one role="user" message, each paired with its call id. I also added the stuck detector (2nd identical call gets a NOTE, 3rd one stops the loop with "stuck").

Result: 4 steps, input tokens [309, 402, 615, 1246], and the final answer named db-prod-01 (xz-utils, CVE-2024-3094) and web-edge-01 (log4j-core, CVE-2021-44228).

- **API calls vs tool calls:** 4 API calls and 13 tool calls (1 + 3 + 9). Each API call is a full round trip to the model, while a local tool runs instantly, so the parallel calls let 12 lookups fit in just 2 steps.
- **Why the tokens grow:** on every step the whole history is sent again (system prompt, tool declarations, the question, every previous model turn and tool result), since the API is stateless.
- **Why openssh-server 9.6 is missing:** CVE-2024-6387 has CVSS 8.1, below the 9.0 threshold, so the model filtered it out.

What I found interesting is that the model never asked for the packages of ci-runner-03, since it saw from list_hosts that it is staging and excluded it before acting.

## Exercise 2: Human-in-the-Loop & sandbox

The sandbox resolves the path first and then checks with is_relative_to() that it is still inside the sandbox folder, which blocks "..", absolute paths and C:/ paths on Windows. The approval check lives in run_agent and not in write_file, so the tool stays simple and the policy is just a set of tool names. All 11 tests passed, without any LLM call.

When I ran the agent, it wanted to overwrite sshd_config. I rejected it with "No, company policy forbids overwriting sshd_config. Write to sshd_config.hardened instead.", and on the next step it wrote to sshd_config.hardened, which I approved. It changed its plan only because it read my rejection as the result of its tool call. In my run the injected SYSTEM_NOTE line was dropped from the new file, but this isn't guaranteed, which is why the human reading the diff should catch it.

With --attack, the agent actually tried read_file("../canary_secret.txt") because the user asked for it, but got SECURITY VIOLATION, and the canary never appeared in the report. This shows why the sandbox is needed even if the model usually ignores injections: "usually" isn't a guarantee, while the sandbox is code that blocks it every time, and the tests prove it.

## Exercise 3: Orchestrator-workers

| mode | orchestrator input tokens per step | orchestrator total | worker total | grand total |
|---|---|---|---|---|
| single | [296, 58,501, 59,565] | 118,362 | 0 | 118,362 |
| orchestrator | [316, 701, 1,266] | 2,283 | 58,235 | 60,518 |

**Why the grand total also drops:** in single mode the log (~58k tokens) enters the history at step 2 and is sent again on every following step, so it was sent twice. In orchestrator mode the log is sent only once, inside the worker's separate request, and the orchestrator only carries the short JSON. So the orchestrator context dropped about 50 times and the grand total almost halved, and the difference would be even bigger with more steps.

The trade-off is that the orchestrator only knows what the worker reported, so if the worker misses something, the report will be confidently wrong. Also, the worker read attacker-controlled text, so its JSON is still data and the report writer stays behind the approval gate.

## Running

```
python lab3_ex1_react.py
pytest test_lab3_ex2.py -v
python lab3_ex2_hitl.py [--attack]
python lab3_ex3_orchestrator.py single --auto-approve
python lab3_ex3_orchestrator.py orchestrator --auto-approve
```