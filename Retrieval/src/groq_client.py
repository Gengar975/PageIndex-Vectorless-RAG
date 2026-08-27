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
You are an enterprise RAG question-answering assistant.

Your task is to answer the user's question using ONLY information explicitly
stated in the provided context.

IMPORTANT RULES:
1. Never infer, guess, or combine facts that are not explicitly stated.
2. Answer every part of the question.
3. If the context does not contain enough information to answer every part,
   say exactly:
   "Information not found in the provided documents."
4. Do not mention retrieval, context, chunks, documents, or search results.
5. Do not explain your reasoning.
6. Give a concise, direct answer.
7. Preserve names, job titles, project names, and business-unit names exactly
   as stated in the context.

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