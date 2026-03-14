# OpenRouter Chat

This Python project demonstrates how to call the OpenRouter AI API (GPT-4o) from Python, and includes a simple full-stack app that generates test questions from a given syllabus and complexity level.

## Features

- Calls OpenRouter GPT-4o via API
- Provides a command-line demo (`openrouter_chat.py`)
- Includes a full-stack Flask web app (`open_router.py`) that generates test questions + answers based on a syllabus and difficulty

## Setup

1. Ensure you have Python installed (version 3.8 or higher recommended).
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set your OpenRouter API key as an environment variable:
   - Windows (PowerShell):
     ```powershell
     $env:OPENROUTER_API_KEY = "sk-..."
     ```
   - macOS / Linux (bash):
     ```bash
     export OPENROUTER_API_KEY="sk-..."
     ```

## Usage

### Command-line Chat (existing)

1. Run the script:
   ```
   python openrouter_chat.py
   ```
2. When prompted, enter your message for the GPT-4o model.

### Evaluation Mode (existing)

Run the script with the `--evaluate` flag to test the model with a set of predefined questions:

```bash
python openrouter_chat.py --evaluate
```

### Web App / Full-stack Test Generator (new)

1. Start the Flask server:
   ```bash
   python open_router.py
   ```
2. Open `http://localhost:8000/` in a browser.
3. Enter a syllabus (topics) and choose a complexity level.
4. Click **Generate test** to generate multiple-choice questions (MCQs) and answers.
5. Use the **History** page to view saved test papers and revisit previous generations.

## Security Notes

- The web app reads the OpenRouter API key from the `OPENROUTER_API_KEY` environment variable. Do not check your API key into source control.

## Troubleshooting

- If you encounter connection errors, check your internet connection.
- Ensure the API key is valid and has sufficient credits.
- For API-related errors, refer to the OpenRouter documentation: https://openrouter.ai/docs