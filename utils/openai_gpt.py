import openai
import os

# Убедитесь, что ключ установлен в Render как переменная среды
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_gpt_response(prompt):
    if not prompt:
        return "Извините, я не расслышал. Повторите, пожалуйста."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Произошла ошибка: {str(e)}"
