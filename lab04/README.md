# Lab 4 – From an Idea to an Agent

I used the same virtual environment as in Labs 2 and 3, and the .env file from the root of the repo. agent_core.py is my harness from Lab 3, unchanged. All the offline tests pass (pytest test_exp4_day.py test_exp5_tools.py test_homework_a.py test_homework_b.py: 24 passed), and none of them calls the model.

## Part 0: The proposal (trip planner)

| # | Question | My answer |
|---|---|---|
| 1 | What must the agent know before planning? Where does it come from? | From the **traveller**: origin, exact dates, number of travellers, total budget, interests, pace, things to avoid, and whether they have a destination in mind. From the **world**: today's date, flight and hotel prices, opening hours and entry slots, weather, events. From a **calculation**: number of nights, total cost, how much of the budget is left, whether a day schedule fits (durations + 30 min moves). |
| 2 | What are the tasks, in order? Which depend on each other? | (1) interview the traveller into a brief, (2) pick candidate destinations, (3) get flight and hotel prices for each candidate, (4) compute the total cost of each and keep the ones inside the budget, (5) the traveller picks one, (6) plan the days, (7) final approval, then booking. Task 3 is independent across destinations, so it can run in parallel; everything else depends on the step before it. |
| 3 | Which outputs must be exactly right, and how can code check them? | Dates (including the year), prices, totals, the budget check, and the schedule rules (entry slots, opening hours, moves). Code can check all of them: an exact calculator for totals, a deterministic verifier like check() for the schedule, date parsing for the dates, and the prices come from tools, not from the model. |
| 4 | Where can I trust what the model already knows? | Understanding what the traveller says in their own words, turning it into a structured brief, suggesting the kind of places that match their interests, and writing the descriptions. Not for today's date, prices, opening hours, events or arithmetic. |
| 5 | Where must a human decide or approve? | Confirming the brief and the destination, anything over budget, and above all before booking or paying, since that is irreversible (like the HITL gate from Lab 3). |
| 6 | What does one complete plan cost? | My first guess was ~10 calls. After measuring: about 6–8 calls for the interview, 2 calls + tools for the prices (plan + parallel), and 5 samples per day for a valid schedule, so 4 days = 20 calls. Roughly 30–35 calls and 1–2 minutes per complete plan. |

## Experiment 1: What does the model know?

The model **refused** the date, the flight price and the concerts in May 2027, so exactly the things that change over time. But it answered **confidently** about the Borghese Gallery (closed on Mondays, 9:00–19:00, booking required), basically from memory, with no source, so it could easily be outdated today; my agent would have to check it with a tool. It also recommended "resident_advisor.net", which can't even be a real domain (no underscores in domain names), so even the "safe" advice can contain invented details. About its own knowledge, it said it knows things up to January 2025, while it is actually November 2026, so it thinks it is still 2025.

## Experiment 2: The budget question

| Prompt | Correct (of 5) | Output tokens on average | What the vote picks |
|---|---|---|---|
| only the answer line | 0/5 | 10 | yes, 138 (wrong) |
| my prompt (work step by step, same last line) | 5/5 | 437 | yes, 34 (correct) |
| bonus 2: the model writes, code computes | 5/5 | 185 | — |

1. **Why the short answer fails:** the model writes token by token, and each token only sees what was written before it. With no room to work, it has to produce the result of five multiplications and additions in one go. It always got "yes" right, but the difference was different every time (132–164), never 34.
2. **When voting doesn't help:** when the wrong answers are all different. All five short answers disagreed, so each had one vote and the "winner" was just the first one, still wrong. Voting only helps when the correct answer appears more often than any wrong one.
3. **What I would put in a product:** the third row. It was 5/5 with 2.4× fewer tokens than step by step, and the arithmetic is done exactly by code, not "probably right" by the model.

## Experiment 3: Ask before you plan

**Step A (--vague):** the model said it didn't know my starting point, budget or style, but planned anyway: three full itineraries, two of them in the **USA** (Utah, Savannah). I counted about 10 assumptions: that I can fly anywhere, the budget (boutique hotels, car rental, upscale dinners), that I drive, the pace, the interests, the number of people, the exact days, a US visa, and so on. For a student from Iași with 1000 EUR it would have been useless: it gives the most common answer, not mine.

**Step B (--simulate):** the interviewer asked 6 questions, one at a time, and stopped because **my code** (missing_required) said the brief was complete, not the model.

1. **What it never found out:** that Ana hates early mornings. pace and avoid stayed empty because they weren't in REQUIRED, and Ana never volunteers extra facts. Yes, that could ruin her trip, for example a schedule that starts at 09:00.
2. **Is dates precise enough?** "12-16 May" has no year, and the model thinks it is 2025, and destination is just "Italy", not a city. My code should decide what "complete" means (for example a full YYYY-MM-DD date), because the model considers anything that sounds reasonable complete.

## Experiment 4: A day that actually works

| Variant | Valid (of 5) | Output tokens on average |
|---|---|---|
| plain | 0/5 | 211 |
| hint in the prompt, JSON only | 0/5 | 197 |
| hint + a field to plan in | 3/5 | 1,287 |

All the failures were the same mistake: a 2-hour item at 09:00, plus 30 minutes of moving, and the next one at 11:30, but the Colosseum and the Borghese Gallery only accept entries on the hour.

1. **Did the hint with pure JSON change anything?** No. The prompt asks it to plan first, but the schema only lets it write items, so it has nowhere to plan and goes straight to the answer. Only when I added a plan field declared **before** items did it go up to 3/5, since the model writes the fields in order.
2. **What does the verifier know that the model doesn't?** Not more rules, they both know them. The difference is that the verifier applies them exactly, minute by minute, every time, while the model knows "entry only on the hour" but breaks it when it just adds times.
3. **Without the verifier,** I would have shown the traveller the first schedule, which looked convincing but was invalid. The verifier turned 15 attempts into one schedule I know is valid, and best() picked the one starting latest.

## Experiment 5: Three ways to use the same tools

I implemented execute() (homework C): a step is ready when all its @s references have results; it runs the ready steps one by one, or all at once with a ThreadPoolExecutor, and if nothing is ready it runs the first pending step as-is so it never hangs.

| question | mode | correct | LLM calls | input tokens | tool seconds | total seconds |
|---|---|---|---|---|---|---|
| 1 | loop | 1/1 | 2 | 1,150 | 4.0 | 9.8 |
| 1 | plan | 1/1 | 2 | 368 | 4.0 | 12.9 |
| 1 | parallel | 1/1 | 2 | 396 | 1.0 | 6.5 |
| 2 | loop | 1/1 | 2 | 967 | 3.0 | 8.1 |
| 2 | plan | 1/1 | 2 | 216 | 3.0 | 7.1 |
| 2 | parallel | 1/1 | 2 | 216 | 1.0 | 5.7 |
| 3 | loop | 1/1 | 3 | 1,749 | 4.0 | 8.8 |
| 3 | plan | 0/1 | 2 | 295 | 3.0 | 7.7 |
| 3 | parallel | 0/1 | 2 | 302 | 2.0 | 4.3 |
| 4 | loop | 1/1 | 3 | 1,566 | 3.0 | 6.6 |
| 4 | plan | 1/1 | 2 | 338 | 3.0 | 6.8 |
| 4 | parallel | 1/1 | 2 | 338 | 2.0 | 3.8 |

1. **Question 2:** tool seconds were 3.0 for loop and plan but 1.0 for parallel, since the three cities don't depend on each other, so they all run at once. The total time is a poor comparison because it also includes the model's time, which varies a lot between calls (for question 1, plan took 12.9 s in total with the same 4 s of tools as loop).
2. **Question 4:** the flights can't start together with nearest_airport because they depend on its result (origin=@s1): you don't know where you fly from until you know the airport. That's why parallel took 2.0 s, not 1.0.
3. **Question 3:** the first flight search said there is no direct flight and to connect via Bucharest. loop read it and asked for the two flights in the next step, so it got 428 right. plan and parallel wrote their whole plan before seeing any result, so they couldn't react, and the solver could only say what was missing. So loop adapts, while plan is 4–6× cheaper in tokens but rigid.
4. **The year:** the plans used date=2024-05-12, a date in the past, which connects to Experiment 1 (the model thinks it's 2024–2025). The fix is one sentence in the system prompt: "Today is 26 November 2026; a date without a year means its next occurrence (12 May = 2027-05-12)", ideally with today's date filled in by code (datetime.date.today()) instead of written by hand.

## Part 6: Back to the proposal

| Task | Information comes from | How I would build it | How it is checked | Rough cost |
|---|---|---|---|---|
| Collect what the traveller wants | the traveller | an interviewer with a structured brief, one question at a time (Exp 3) | code decides when the brief is complete, with strict rules (full dates, pace and avoid required) | 6–8 calls |
| Total cost of a candidate trip | tools + calculation | tools for every price, the model only writes the expression, code computes it (Exp 2 bonus, sum_eur) | exact calculator in code | 1 call + tools |
| A valid day schedule | rules + model | structured output with a plan field first, 5 samples (Exp 4) | deterministic verifier check(), then best() picks the latest start | 5 calls per day |
| Prices for 5 destinations | tools | plan + parallel, since the destinations are independent (Exp 5) | prices come only from tools; a loop as fallback when a tool returns a surprise (Exp 5, question 3) | 2 calls, ~1 s of tools |
| Today's date | code | datetime.date.today() put in every system prompt | — | 0 calls |
| Booking | the traveller | HITL approval gate (Lab 3) | the human approves the final plan and the total | 0 calls |

**The planner as boxes and arrows:**

```
Traveller ──► [Interviewer] ──► brief ──► code: is the brief complete? ──(no)──► next question
                                                │ (yes)
                                                ▼
                                  [Orchestrator (ReAct loop)]  ◄── today's date from code
                                   │            │            │
                    ┌──────────────┘            │            └──────────────┐
                    ▼                           ▼                           ▼
     [Price worker: plan + parallel]   [Cost: model writes expression,   [Schedule worker:
      flights + hotels for each         code computes the total]           5 samples + check()
      destination (tools)]                                                 + best()]
                    └──────────────┬────────────┴─────────────┬──────────────┘
                                   ▼                          ▼
                       code: inside the budget?      code: every day valid?
                                   └────────────┬─────────────┘
                                                ▼
                                 [HITL: traveller approves] ──► booking
```

The orchestrator only gets compact results from the workers (Lab 3), code checks everything that can be checked, and a human approves before anything irreversible.

**Where it would still go wrong:** it can miss things the traveller never says (like Ana's early mornings), and the descriptions and suggestions are still the model's opinion, which nobody checks. I would notice the first by making pace and avoid required, and the second only through the traveller's feedback at the approval step, since there is no code check for "would she like this place".

**Another project idea, question 1 (study planner):** from the **student**: the subjects, the exam dates, how many hours a day they can study, and which subjects they find hardest. From the **world**: the syllabus and the official exam calendar (from documents, not from the model's memory), and today's date. From a **calculation**: the days left until each exam, the total hours available, and how to split them so that every subject gets enough time before its exam, which code can check like the schedule verifier.

## Homework A: The voucher puzzle

| vouchers | approach | result | model calls | tokens (in + out) |
|---|---|---|---|---|
| 4 9 10 13 | direct (5 tries) | 4/5 | 5 | 717 |
| 4 9 10 13 | search | solved | 9 | 1,113 |
| 1 5 5 5 | direct (5 tries) | 5/5 | 5 | 727 |
| 1 5 5 5 | search | failed | 18 | 2,280 |

Direct was right 9 times out of 10, and my exact checker caught the only mistake (13 + 10 + 9 - 4 = 28). Surprisingly, the "hard" puzzle 1 5 5 5 was 5/5, probably because it is a famous puzzle that the model has seen many times, so it remembers the answer instead of computing it. In the search, the model only proposes and rates, while my code does every calculation with exact fractions and checks the final 24.

Here the search was not worth it: 2–3× more calls and tokens, and it failed on 1 5 5 5. The problem was in **propose**, not in value: the solution needs 1/5 as the first step (5 × (5 − 1/5) = 24), but the model only proposed 5/5, 5−1 and 5×5, so that branch was never even rated. A search can't find a path that nobody proposes. It would be worth it for new problems the model hasn't seen, but only with good proposals; when the answer can be checked by code, asking directly a few times and keeping the first answer that passes the check is cheaper.

## Homework B: Learn from a failed test

The generated code runs in a separate process (python -I) in a temporary folder, with a 10 s timeout, never inside my harness. My tests: same day, a normal stay, across a month end, across a year end, a leap year, check-out before check-in (must raise), a badly formatted date and an impossible date (both must raise).

| strategy | solved | attempts per run | avg attempts | avg tokens |
|---|---|---|---|---|
| plain retries | 0/3 | [3, 3, 3] | 3.0 | 430 |
| with lessons | 3/3 | [3, 3, 2] | 2.7 | 1,000 |

With plain retries, the model failed the same test 9 times out of 9: it returned a negative number instead of raising an error when check-out is before check-in. Asking again with no new information just gives the same most likely answer. With lessons it solved all 3 runs, at about 2.3× the tokens.

The lessons were all correct about the problem, but in runs 1 and 2 the first lesson was imprecise ("check that check-out is after check-in"), and the model applied it too strictly (d2 <= d1 raised an error), which broke the same-day case. The second lesson fixed that. In run 3 the first lesson already said "on or after", so it passed on the second attempt. So a lesson can be right and still introduce a new bug if it isn't precise, and only the tests catch it.

## What all the experiments have in common

Every time, the reliable part was not the model alone but the code around it: code computed the totals, checked the schedules, decided when the brief was complete, ran the tools in parallel, checked the vouchers and ran the tests. The model was useful for understanding text and proposing things, and code was what made the results trustworthy.

## Running

```
pytest test_exp4_day.py test_exp5_tools.py test_homework_a.py test_homework_b.py -v
python exp1_knowledge.py
python exp2_budget.py
python exp2_budget.py --code
python exp3_interview.py --vague
python exp3_interview.py --simulate
python exp4_day.py
python exp5_tools.py --verbose
python homework_a_voucher.py
python homework_b_lessons.py --runs 3
```
