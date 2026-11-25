"""Lab 1 - a stateful terminal chat loop against a local Ollama model."""
from openai import OpenAI

# Ollama speaks the OpenAI protocol on /v1. The SDK requires an API key; Ollama ignores it.
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "qwen2.5:1.5b"

SYSTEM_PROMPT = (
    "You are a patient academic mentor for computer science students. "
    "Answer in at most 3 sentences and remember what the student tells you."
)


def main() -> None:
    # Req. 1 + 2: the conversation lives HERE, in our process, starting with the system prompt.
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Chat started. Type 'exit' or 'quit' to leave.")

    while True:
        # Req. 3: read one line from stdin. Ctrl+D / Ctrl+Z ends the chat cleanly.
        try:
            user_input = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):  # Req. 8
            break

        # Req. 4: append the user turn BEFORE the request
        history.append({"role": "user", "content": user_input})

        # Req. 5: send the WHOLE history; the server remembers nothing between requests
        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            temperature=0.7,
        )
        reply = response.choices[0].message.content or ""

        # Req. 6: show the answer
        print(f"Assistant: {reply}")
        print(f"  [{response.usage.prompt_tokens} prompt tokens, "
              f"{len(history) + 1} messages in history]")

        # Req. 7: append the assistant turn, otherwise the next request has a "hole"
        history.append({"role": "assistant", "content": reply})

    # Check-off: history must contain system, user, assistant, user, assistant
    print([m["role"] for m in history])
    print("Bye!")


if __name__ == "__main__":
    main()