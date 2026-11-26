"""Lab 4 - Experiment 3: ask before you plan.

    python exp3_interview.py              # you answer the questions
    python exp3_interview.py --vague      # step A: what happens when nobody asks
    python exp3_interview.py --simulate   # a simulated traveler with a hidden profile answers
"""
import sys
from typing import Literal

from pydantic import BaseModel, Field

from llm import ask

FIRST_MESSAGE = "Plan me a nice 4-day trip in May."
MAX_QUESTIONS = 8


class TravelBrief(BaseModel):
    origin: str | None = Field(None, description="City the trip starts from")
    destination: str | None = Field(None, description="City or region, or 'open' if the traveler wants suggestions")
    dates: str | None = Field(None, description="Arrival and departure dates, e.g. '12-16 May'")
    travelers: int | None = Field(None, description="How many people travel")
    budget_eur: int | None = Field(None, description="Total budget for the whole trip, in EUR")
    interests: list[str] = Field(default_factory=list, description="What they enjoy doing")
    pace: Literal["relaxed", "balanced", "packed"] | None = None
    avoid: list[str] = Field(default_factory=list, description="Things they do not want")


class InterviewTurn(BaseModel):
    brief: TravelBrief = Field(description="Everything learned so far; unknown fields stay null")
    next_question: str = Field(description="ONE short question about the most important unknown, or '' when done")


REQUIRED = ["origin", "destination", "dates", "travelers", "budget_eur", "interests"]

INTERVIEWER = """\
You are the intake assistant of a trip-planning platform. Your ONLY job is to collect the traveler's
requirements into the brief. You do NOT plan the trip, you do NOT suggest destinations, hotels or activities.

Rules:
- Fill the brief ONLY with what the traveler actually said in the conversation. Never guess, never invent
  defaults, never "assume something reasonable". If a field was not stated, leave it null (or an empty list).
- Keep every fact learned in earlier turns; update a field only when the traveler corrects it.
- "May" alone is not a date: dates must be the exact arrival and departure days (e.g. "12-16 May").
- budget_eur is the TOTAL budget for the whole trip, in EUR. If the traveler gives it per person, multiply.
- If the traveler has no destination in mind and wants a suggestion, set destination to "open".
- Ask exactly ONE short, friendly question per turn, about the most important thing still unknown,
  in this order of importance: origin, dates, travelers, budget, destination, interests, pace, things to avoid.
- When origin, destination, dates, travelers, budget and interests are all known, set next_question to "".
"""


def _empty(value) -> bool:
    return value is None or value == "" or value == []


def missing_required(brief: TravelBrief) -> list[str]:
    """The harness decides when the brief is complete, not the model."""
    return [name for name in REQUIRED if _empty(getattr(brief, name))]


# --- A simulated traveler for hands-free testing ---------------------------
PERSONA = (
    "You are Ana, a student from Iasi. Hidden facts about your trip: 2 people (you and a friend), "
    "12-16 May, total budget 1000 EUR, you love street food and old history, you hate early mornings, "
    "you have no destination in mind and want a suggestion in Italy. "
    "Answer ONLY the question asked, in one short sentence, like a real person would. Never volunteer extra facts."
)


def simulated_answer(transcript: str, question: str) -> str:
    return ask(f"Conversation so far:\n{transcript}\nThe planner asks: {question}\nYour reply:",
               system=PERSONA, temperature=0.7).text.strip()


def interview(first_message: str, answer_fn) -> tuple[TravelBrief, int]:
    transcript = f"Traveler: {first_message}"
    brief = TravelBrief()
    for asked in range(MAX_QUESTIONS):
        turn: InterviewTurn = ask(f"Conversation so far:\n{transcript}",
                                  system=INTERVIEWER, schema=InterviewTurn).parsed
        brief = turn.brief
        missing = missing_required(brief)
        # The HARNESS decides: complete means nothing required is missing, whatever the model says.
        if not missing:
            return brief, asked
        question = turn.next_question.strip()
        if not question:  # the model thinks it is done, but the harness disagrees
            question = f"Could you tell me your {missing[0].replace('_eur', ' in EUR').replace('_', ' ')}?"
        print(f"\n[Planner] {question}")
        reply = answer_fn(transcript, question)
        print(f"[Traveler] {reply}")
        transcript += f"\nPlanner: {question}\nTraveler: {reply}"
    return brief, MAX_QUESTIONS


if __name__ == "__main__":
    if "--vague" in sys.argv:
        print(ask(FIRST_MESSAGE).text)
        sys.exit()
    answer_fn = simulated_answer if "--simulate" in sys.argv else (lambda _t, _q: input("> ").strip())
    print(f"[Traveler] {FIRST_MESSAGE}")
    brief, questions = interview(FIRST_MESSAGE, answer_fn)
    print(f"\n[Brief after {questions} questions] missing: {missing_required(brief) or 'nothing'}")
    print(brief.model_dump_json(indent=2))
