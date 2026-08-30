import time
import random
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MAX_REQUESTS = int(os.getenv("GROQ_MAX_REQUESTS", "100"))


def generate_answer(query, context):

    prompt = f"""
You are an enterprise Retrieval-Augmented Generation assistant.

Answer ONLY from the provided context.

RULES:

- Use only information explicitly present in the context.
- Do not use external knowledge.
- Do not guess or infer missing facts.
- If the answer is not clearly present in the context, reply exactly:

Information not found in the provided documents.

- Preserve names, numbers, dates, project names, and job titles exactly.
- Answer directly and concisely.
- If multiple relevant facts exist, include all of them.

QUESTION:
{query}

CONTEXT:
{context}

ANSWER:
"""

    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise enterprise RAG assistant. "
                            "Never invent information."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            error = str(e)

            if "429" in error or "503" in error:
                if attempt == 4:
                    return "The service is temporarily busy. Please try again."

                wait = min(30, (2 ** attempt) + random.random())

                print(
                    f"Groq unavailable/rate limited. "
                    f"Retrying in {wait:.1f}s..."
                )

                time.sleep(wait)
            else:
                raise