import os
import requests
import argparse

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "Environment variable OPENROUTER_API_KEY is required. "
        "Set it to your OpenRouter API key before running this script."
    )

evaluation_questions = [
    "What is the capital of France?",
    "Explain quantum computing in simple terms.",
    "Write a short poem about AI.",
    "Solve: 2x + 3 = 7",
    "What are the benefits of renewable energy?",
    "Generate a Python function to calculate factorial.",
    "Debate: Should social media be regulated?",
    "Describe a day in the life of a software engineer.",
    "What is machine learning?",
    "Translate 'Hello, how are you?' to Spanish."
]

def get_response(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interact with GPT-4o via OpenRouter")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation questions")
    args = parser.parse_args()

    if args.evaluate:
        print("Running evaluation questions...\n")
        for i, question in enumerate(evaluation_questions, 1):
            print(f"Question {i}: {question}")
            response = get_response(question)
            print(f"Response: {response}\n")
    else:
        prompt = input("Enter your prompt: ")
        print(get_response(prompt))