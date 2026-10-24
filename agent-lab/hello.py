import ollama

MODEL = "llama3.1:8b"
messages = [{"role": "system", "content": "You are a helpful assistant."},
]

first = ollama.chat(
    model=MODEL,
    messages=messages
)

print(first.message)
messages.append({"role": "user", "content": "Give me a concrete example."})

second = ollama.chat(
    model=MODEL,
    messages=messages
)
print(second.message.content)
print("prompt tokens:", first.prompt_eval_count, "->", second.prompt_eval_count)