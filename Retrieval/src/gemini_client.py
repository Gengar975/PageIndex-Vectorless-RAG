import time
import random
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def generate_answer(query, context):

    prompt = f"""
You are an enterprise RAG assistant.

Answer the user's question directly using only the retrieved context.

Rules:
- Do not say "Based on the provided context".
- Do not mention the context.
- Do not mention documents or retrieval.
- Give a concise professional answer.
- If the answer is not found, say "Information not found in the provided documents."

QUESTION:
{query}

CONTEXT:
{context}
"""

    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )

            return response.text

        except Exception as e:

            if "429" in str(e) or "503" in str(e):
                if attempt == 4:
                    return "The service is temporarily busy. Please try again."

                # Exponential backoff + jitter
                wait = min(30, (2 ** attempt) + random.random())

                print(
                    f"Gemini unavailable/rate limited. "
                    f"Retrying in {wait:.1f}s..."
                )

                time.sleep(wait)

            else:
                raise