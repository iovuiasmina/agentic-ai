# Lab 1 – Local Inference & the OpenAI Protocol

## What I did

I installed Ollama (version 0.40.16) and pulled the qwen2.5:1.5b model, and after that I checked with curl.exe that the local server answers on http://localhost:11434/v1/chat/completions. I got back a chat.completion object, with the model's answer in choices[0].message.content and the token counts in usage, which basically confirms that Ollama speaks the same protocol as OpenAI.

I chose the Python track. In client_test.py I sent a single request to the model (39 prompt tokens, 33 completion tokens). The answer about the difference between a process and a thread sounded plausible, but it wasn't quite accurate, since a thread isn't "a single execution of a program", but an execution unit inside a process that shares memory with the other threads. This showed me that the model's answers need to be checked, especially with such a small model.

## The chat loop (chat_loop.py)

Since the model doesn't remember anything between requests, the conversation memory has to be kept by my program. I keep a list called history that starts with the system message, and at every step I add the user's message before the request (otherwise the model wouldn't receive the current question) and the assistant's reply after the request (otherwise the next request would be missing what the model said). On every request I send the whole list, not just the last message.

## Running

```
ollama pull qwen2.5:1.5b
pip install -r requirements.txt
python chat_loop.py
```

## Verification

```
User: My project name is Project Chimera.
Assistant: Project Chimera sounds intriguing! ...
  [47 prompt tokens, 3 messages in history]
User: What is the name of my project?
Assistant: The name of your project is Project Chimera.
  [92 prompt tokens, 5 messages in history]
User: exit
['system', 'user', 'assistant', 'user', 'assistant']
Bye!
```

The model correctly answered Project Chimera, and the list of roles at the end shows that the history has exactly the order system, user, assistant, user, assistant. I added this check because the project name test alone wouldn't be enough: the name is in a user message, so the model would have found it even if I had forgotten to add the assistant's replies.

What I found interesting is that the number of prompt tokens went up from 47 to 92, because the second request re-sent the whole conversation so far. Basically, the longer the conversation gets, the bigger every request becomes, even if the new question is short.