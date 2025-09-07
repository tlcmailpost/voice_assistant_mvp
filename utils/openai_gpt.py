import os
import openai

def get_gpt_response(prompt: str) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")

    if not prompt:
        return "Извините, я не расслышал. Повторите, пожалуйста."

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Ошибка вызова модели: {e}"


