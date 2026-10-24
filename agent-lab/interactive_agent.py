import ollama

MODEL = "llama3.1:8b"

messages = []

while True:
    try:
        line = input("you> ")
    except (EOFError, KeyboardInterrupt):
        print()
        break

    line = line.strip()
    if not line:
        break
    if line == "/reset":
        messages.clear()
        print("Conversation reset.")
        continue

    messages.append({"role": "user", "content": line})
    response = ollama.chat(model=MODEL, messages=messages)
    messages.append(response.message)

    print("ollama>", response.message.content)
    print((f"  [prompt tokens: {response.prompt_eval_count}, "
          f"reply tokens: {response.eval_count}, history: {len(messages)} messages]"))