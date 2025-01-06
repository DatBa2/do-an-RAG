from openai import OpenAI
from pyexpat.errors import messages

c = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

messages = []

while True:
    user_input = input("You: ")
    if user_input == "exit":
        break
    messages.append({"role":"user", "content": user_input})
    response = c.chat.completions.create(
        model="gemma2:9b",
        stream=True,
        messages=messages
    )

    bot_reply = ""
    for chuck in response:
        bot_reply += chuck.choices[0].delta.content or ""
        print(chuck.choices[0].delta.content or "",end="",flush=True)
    print("\n")
    messages.append({"role": "assistant", "content": bot_reply})