import google.generativeai as genai
genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")
model = genai.GenerativeModel("gemini-1.5-flash")

chat = model.start_chat(
    history=[

    ]
)
response = chat.send_message("Có bao nhiêu chữ K trong văn bản")
print(response.text)