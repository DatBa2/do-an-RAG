import google.generativeai as genai  # Use Google's Gemini API library instead of OpenAI's

genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")

def query_llama_index(index, question):
    if index is None:
        print("Chỉ mục không được tải đúng cách.")
        return []
    query_engine = index.as_query_engine()
    response = query_engine.query(question)
    # return [response.response]
    return [node.node.text for node in response.source_nodes]

def generate_gemini_answer(context, question):
    input_text = f"Context: {context}\n\nQuestion: {question}"

    # Start a chat with Gemini's model; use 'gemini-1.5-flash' or correct model name
    model = genai.GenerativeModel("gemini-1.5-flash")
    chat = model.start_chat(history=[{
        "role": "model",
        "parts": [
            {
                "text": "You are a helpful AI assistant. Always respond in Vietnamese."
            }
        ]
    }])
    response = chat.send_message(input_text)
    return response.text
