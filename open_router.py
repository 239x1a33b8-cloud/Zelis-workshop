import os
import json
import requests
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from flask_sqlalchemy import SQLAlchemy

# NOTE: For security, set your OpenRouter API key in the environment variable OPENROUTER_API_KEY.
# Example (Windows PowerShell):
#   $env:OPENROUTER_API_KEY = "sk-..."

API_KEY_ENV_VAR = "OPENROUTER_API_KEY"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-in-production")

# Simple SQLite storage for generated tests. Change DATABASE_URL to use a different backend.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class TestPaper(db.Model):
    __tablename__ = "test_paper"

    id = db.Column(db.Integer, primary_key=True)
    syllabus = db.Column(db.Text, nullable=False)
    complexity = db.Column(db.String(32), nullable=False)
    num_questions = db.Column(db.Integer, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    raw_output = db.Column(db.Text, nullable=False)

    questions = db.relationship(
        "MCQQuestion", back_populates="paper", cascade="all, delete-orphan"
    )


class MCQQuestion(db.Model):
    __tablename__ = "mcq_question"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("test_paper.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    choices_json = db.Column(db.Text, nullable=False)
    correct_choice_index = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.Text, nullable=True)

    paper = db.relationship("TestPaper", back_populates="questions")

    @property
    def choices(self):
        try:
            return json.loads(self.choices_json)
        except Exception:
            return []


class TestAttempt(db.Model):
    __tablename__ = "test_attempt"

    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey("test_paper.id"), nullable=False)
    responses_json = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    paper = db.relationship("TestPaper")


def initialize_db():
    """Ensure database tables exist."""
    with app.app_context():
        db.create_all()


def _get_api_key() -> str:
    """Get the OpenRouter API key from the environment."""
    key = os.getenv(API_KEY_ENV_VAR)
    if not key:
        raise RuntimeError(
            f"Missing required environment variable {API_KEY_ENV_VAR}. "
            "Set it to your OpenRouter API key and restart the app."
        )
    return key


def call_openrouter(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 1200) -> str:
    """Call the OpenRouter chat completions endpoint and return the assistant response."""
    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # OpenRouter returns an array of choices; take the first one
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def build_mcq_generation_prompt(syllabus: str, complexity: str, num_questions: int) -> str:
    """Create a prompt that asks the model to output a JSON list of MCQs."""
    complexity = complexity.strip().lower()
    if complexity not in {"easy", "medium", "hard"}:
        complexity = "medium"

    prompt = (
        "You are an expert educator and exam writer. "
        "Given the syllabus below, generate a set of well-crafted multiple-choice questions (MCQs). "
        "Each question should have 4 answer choices and one correct answer. "
        "Return the result as valid JSON only, with the following structure:\n\n"
        "{\n"
        "  \"syllabus\": \"...\",\n"
        "  \"complexity\": \"easy|medium|hard\",\n"
        "  \"questions\": [\n"
        "    {\n"
        "      \"question\": \"...\",\n"
        "      \"choices\": [\"A\", \"B\", \"C\", \"D\"],\n"
        "      \"correct_choice\": 0,  # index into the choices array\n"
        "      \"explanation\": \"...\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Syllabus:\n{syllabus.strip()}\n\n"
        "Requirements:\n"
        f"- Number of questions: {num_questions}\n"
        f"- Difficulty: {complexity}\n"
        "- Ensure the output is valid JSON only (do not add extraneous text).\n"
    )

    return prompt


def parse_mcq_output(raw: str):
    """Attempt to parse the model output as JSON. Return the parsed dict or None."""
    try:
        return json.loads(raw)
    except Exception:
        # Try to extract JSON block if the model wrapped it in markdown or text.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        syllabus = request.form.get("syllabus", "").strip()
        complexity = request.form.get("complexity", "medium").strip().lower()
        num_questions = int(request.form.get("num_questions", 5))

        if not syllabus:
            flash("Please provide a syllabus or topic list to generate tests.", "warning")
            return redirect(url_for("index"))

        prompt = build_mcq_generation_prompt(syllabus, complexity, num_questions)

        try:
            generated = call_openrouter(prompt)
            parsed = parse_mcq_output(generated)
        except Exception as e:
            flash(f"Error generating tests: {e}", "danger")
            return redirect(url_for("index"))

        paper = TestPaper(
            syllabus=syllabus,
            complexity=complexity,
            num_questions=num_questions,
            raw_output=generated,
        )
        db.session.add(paper)
        db.session.flush()  # get paper.id

        questions = []
        if parsed and isinstance(parsed.get("questions"), list):
            for q in parsed.get("questions", [])[:num_questions]:
                question_text = q.get("question") or ""
                choices = q.get("choices") or []
                correct_choice = q.get("correct_choice", 0)
                explanation = q.get("explanation") or ""

                mcq = MCQQuestion(
                    paper_id=paper.id,
                    question_text=question_text,
                    choices_json=json.dumps(choices),
                    correct_choice_index=int(correct_choice) if isinstance(correct_choice, int) else 0,
                    explanation=explanation,
                )
                db.session.add(mcq)
                questions.append(mcq)

        db.session.commit()

        return render_template(
            "results.html",
            paper=paper,
            parsed=parsed,
            questions=questions,
        )

    return render_template("index.html")


@app.route("/history")
def history():
    papers = (
        TestPaper.query.order_by(TestPaper.generated_at.desc()).limit(50).all()
    )
    return render_template("history.html", papers=papers)


@app.route("/paper/<int:paper_id>")
def view_paper(paper_id):
    paper = TestPaper.query.get_or_404(paper_id)
    return render_template("paper.html", paper=paper)


@app.route("/quiz/<int:paper_id>")
def quiz_start(paper_id):
    """Show all questions at once for student to answer."""
    paper = TestPaper.query.get_or_404(paper_id)
    return render_template(
        "quiz_all_questions.html",
        paper=paper,
        questions=paper.questions,
    )


@app.route("/quiz/<int:paper_id>/submit", methods=["POST"])
def quiz_submit(paper_id):
    """Evaluate all answers and show results."""
    paper = TestPaper.query.get_or_404(paper_id)
    score = 0
    total = len(paper.questions)
    details = []
    answers = {}

    for i, q in enumerate(paper.questions):
        selected_str = request.form.get(f"q{i}")
        try:
            selected = int(selected_str) if selected_str else None
        except ValueError:
            selected = None
        answers[str(i)] = selected

        correct = q.correct_choice_index
        is_correct = selected is not None and selected == correct
        if is_correct:
            score += 1

        details.append(
            {
                "question": q.question_text,
                "selected": selected,
                "correct": correct,
                "choices": q.choices,
                "is_correct": is_correct,
                "explanation": q.explanation,
            }
        )

    # Store the attempt
    attempt = TestAttempt(
        paper_id=paper.id,
        responses_json=json.dumps(answers),
        score=score,
        total=total,
    )
    db.session.add(attempt)
    db.session.commit()

    return render_template(
        "quiz_all_results.html",
        paper=paper,
        score=score,
        total=total,
        details=details,
        attempt=attempt,
    )


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """API endpoint to generate tests in structured JSON."""
    payload = request.get_json(force=True)
    syllabus = payload.get("syllabus", "").strip()
    complexity = payload.get("complexity", "medium").strip().lower()
    num_questions = int(payload.get("num_questions", 5))

    if not syllabus:
        return jsonify({"error": "Missing syllabus"}), 400

    prompt = build_mcq_generation_prompt(syllabus, complexity, num_questions)

    try:
        generated = call_openrouter(prompt)
        parsed = parse_mcq_output(generated)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    response = {
        "syllabus": syllabus,
        "complexity": complexity,
        "num_questions": num_questions,
        "raw": generated,
        "parsed": parsed,
    }

    # store to database
    paper = TestPaper(
        syllabus=syllabus,
        complexity=complexity,
        num_questions=num_questions,
        raw_output=generated,
    )
    db.session.add(paper)
    db.session.flush()

    if parsed and isinstance(parsed.get("questions"), list):
        for q in parsed.get("questions", [])[:num_questions]:
            mcq = MCQQuestion(
                paper_id=paper.id,
                question_text=q.get("question") or "",
                choices_json=json.dumps(q.get("choices") or []),
                correct_choice_index=int(q.get("correct_choice", 0)),
                explanation=q.get("explanation") or "",
            )
            db.session.add(mcq)

    db.session.commit()

    response["paper_id"] = paper.id
    return jsonify(response)


if __name__ == "__main__":
    # Run with: python open_router.py
    # Or for development: set FLASK_ENV=development
    initialize_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
