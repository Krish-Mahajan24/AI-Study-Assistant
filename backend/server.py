import os
import time
import json
import re

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


# ============================================================
# PATHS & ENVIRONMENT
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
FRONTEND = os.path.join(ROOT, "frontend")

load_dotenv(os.path.join(BASE_DIR, ".env"))


# ============================================================
# FLASK APP
# ============================================================

app = Flask(
    __name__,
    static_folder=FRONTEND,
    static_url_path=""
)

CORS(app)


# ============================================================
# AZURE AI FOUNDRY CONFIGURATION
# ============================================================

FOUNDRY_ENDPOINT = os.getenv(
    "AZURE_AI_PROJECT_ENDPOINT",
    "https://krish-project-resource.services.ai.azure.com/api/projects/krish-project"
)

STUDYMATE_AGENT = os.getenv(
    "STUDYMATE_AGENT_NAME",
    "StudyMate"
)

# Current StudyMate agent version
STUDYMATE_VERSION = os.getenv(
    "STUDYMATE_AGENT_VERSION",
    "15"
)

project_client = None
openai_client = None


# ============================================================
# QUIZ HISTORY
# ============================================================
# Stores questions generated during the current server session.
# This prevents Easy / Medium / Hard quizzes for the same
# subject + topic from reusing the same questions.
#
# Important:
# This is in-memory. Restarting the server clears the history.
# A database can be added later for permanent user history.
# ============================================================

quiz_history = {}


def normalize_text(text):
    """Normalize text for duplicate detection."""
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def quiz_history_key(subject, topic):
    """Create a stable history key for subject + topic."""
    return (
        normalize_text(subject),
        normalize_text(topic)
    )


def get_previous_questions(subject, topic, limit=40):
    """Return previously generated question texts."""
    key = quiz_history_key(subject, topic)
    return quiz_history.get(key, [])[-limit:]


def save_quiz_history(subject, topic, questions):
    """Store newly generated questions in memory."""
    key = quiz_history_key(subject, topic)

    if key not in quiz_history:
        quiz_history[key] = []

    for question in questions:
        question_text = question.get("question", "").strip()

        if question_text:
            quiz_history[key].append(question_text)

    # Prevent unlimited memory growth.
    quiz_history[key] = quiz_history[key][-40:]


def build_previous_question_block(previous_questions):
    """Format previous questions for the agent prompt."""
    if not previous_questions:
        return """
There are no previously generated questions for this
subject/topic.

Generate a completely fresh set.
"""

    previous_text = "\n".join(
        f"- {question}"
        for question in previous_questions
    )

    return f"""
PREVIOUSLY GENERATED QUESTIONS

The following questions have already been generated for this
subject/topic.

You MUST NOT reuse them at ANY difficulty level.

Do NOT:
- Copy them.
- Trivially reword them.
- Keep the same scenario and only change names.
- Keep the same structure and only change options.
- Change only numerical values.
- Ask the same underlying concept in nearly identical form.

Previously generated questions:

{previous_text}
"""


# ============================================================
# AZURE CLIENT
# ============================================================

def get_openai_client():
    global project_client
    global openai_client

    if openai_client is None:
        project_client = AIProjectClient(
            endpoint=FOUNDRY_ENDPOINT,
            credential=DefaultAzureCredential(),
        )

        openai_client = project_client.get_openai_client()

    return openai_client


# ============================================================
# CALL STUDYMATE AGENT
# ============================================================

def call_studymate(prompt):
    client = get_openai_client()

    response = client.responses.create(
        input=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        extra_body={
            "agent_reference": {
                "name": STUDYMATE_AGENT,
                "version": STUDYMATE_VERSION,
                "type": "agent_reference"
            }
        },
    )

    return response.output_text


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):
    if not text:
        raise ValueError(
            "StudyMate returned an empty response."
        )

    text = text.strip()

    # Remove accidental Markdown code fences.
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```",
        "",
        text
    ).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"StudyMate did not return JSON. "
            f"Raw response: {text[:1000]}"
        )

    try:
        return json.loads(
            text[start:end + 1]
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"StudyMate returned invalid JSON: {exc}. "
            f"Raw response: {text[:1000]}"
        )


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def index():
    return send_from_directory(
        FRONTEND,
        "index.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "agent": STUDYMATE_AGENT,
        "version": STUDYMATE_VERSION,
        "message": "StudyMate backend is running."
    })


# ============================================================
# NORMAL CHAT
# ============================================================

@app.post("/api/chat")
def chat():

    started = time.perf_counter()

    body = request.get_json(
        silent=True
    ) or {}

    message = str(
        body.get("message") or ""
    ).strip()

    subject = str(
        body.get("subject") or ""
    ).strip()

    if not message:
        return jsonify({
            "error": "Message is required."
        }), 400

    prompt = f"""
You are StudyMate, a university AI study assistant.

Use the connected Foundry IQ knowledge base and uploaded
course materials as the primary source.

Selected subject:
{subject or "Not specified"}

Student question:
{message}

IMPORTANT SYLLABUS RULES:

- The selected subject is a HARD syllabus boundary.
- Answer ONLY if the requested topic is covered by the
  selected subject's CHOs/course material.
- Do NOT answer an out-of-syllabus topic simply because
  retrieved context or general knowledge matches it.
- Do NOT cross into another subject.
- If the topic is outside the selected subject's CHOs,
  say that it is not part of the selected subject's syllabus.
- If the topic is in the selected subject's CHOs and the
  topic contains a formula, automatically include the
  relevant formula and explain its variables, use, and
  calculation steps when applicable.
- Give a detailed, structured explanation based on the
  selected course material.
- Do not invent course-specific facts.
"""

    try:

        answer = call_studymate(
            prompt
        )

        return jsonify({
            "answer": answer,
            "sources": [],
            "latency_ms": round(
                (
                    time.perf_counter()
                    - started
                ) * 1000
            )
        })

    except Exception as exc:

        return jsonify({
            "error":
                f"StudyMate request failed: {exc}"
        }), 502


# ============================================================
# DIFFICULTY RULES
# ============================================================

DIFFICULTY_RULES = {

    "easy": """
EASY LEVEL

Questions must test fundamental understanding.

Use:
- Basic definitions
- Direct concept recognition
- Simple examples
- One-step applications
- Straightforward calculations

Avoid:
- Complex multi-step reasoning
- Challenging edge cases
- Combining many concepts
- Highly tricky scenarios

Easy must feel introductory while still being academically correct.
""",

    "medium": """
MEDIUM LEVEL

Questions must require actual application of knowledge.

Use:
- Concept application
- Comparisons
- Moderate reasoning
- Short scenarios
- Interpretation of situations
- Two-step reasoning
- Moderate calculations where supported by the CHOs

Medium must be meaningfully harder than Easy.

Do NOT take an Easy question and simply reword it.
""",

    "hard": """
HARD LEVEL

Questions must genuinely challenge a university student.

Use:
- Multi-step reasoning
- Analysis
- Complex scenarios
- Combining multiple related concepts
- Challenging calculations where supported by the CHOs
- Edge cases and constraints when supported by the course material
- Interpretation of results
- Applying concepts to unfamiliar situations

Hard must not be a definition-only question.

Hard must NOT be an Easy or Medium question with different wording.

Hard questions must require deeper reasoning and stronger
understanding of the selected syllabus.
"""
}


# ============================================================
# QUIZ PROMPT BUILDER
# ============================================================

def build_quiz_prompt(
    subject,
    selected_topic,
    difficulty,
    count,
    previous_questions
):
    difficulty_rules = DIFFICULTY_RULES[
        difficulty
    ]

    previous_question_block = (
        build_previous_question_block(
            previous_questions
        )
    )

    return f"""
BACKEND QUIZ GENERATION REQUEST

You are StudyMate, a university AI study assistant.

This request comes from the StudyMate application's
backend.

This is NOT an interactive student quiz.

Generate the complete quiz immediately.

Do NOT:
- ask the student questions
- wait for a student response
- conduct an interactive quiz
- hide the answer key
- refuse a normal quiz-generation request
- switch subjects
- switch topics
- return Markdown
- return code fences
- return text outside the JSON

============================================================
SELECTED INPUT
============================================================

Subject:
{subject}

Topic:
{selected_topic}

Difficulty:
{difficulty}

Number of questions:
{count}

============================================================
STRICT SUBJECT / CHO SCOPE
============================================================

The selected subject is a HARD constraint.

Every question MUST belong to:
{subject}

Use only the selected subject's CHOs/course material.

Do NOT:
- mix another subject
- use unrelated knowledge from another CHO
- create questions just because a concept appears somewhere
  else in the broader knowledge base

The selected topic is also a HARD constraint.

Every question MUST focus on:
{selected_topic}

If the topic is not supported by the selected subject's CHOs,
do not silently move to another topic.

============================================================
DIFFICULTY
============================================================

{difficulty_rules}

============================================================
FRESHNESS / NO REPEATS
============================================================

Easy, Medium, and Hard are genuinely different difficulty
levels.

Questions must be fresh and meaningfully different.

Do NOT:
- duplicate a previous question
- trivially reword a previous question
- use the same scenario with superficial changes
- keep the same question structure and change only options
- change only numbers in a numerical question
- reuse an Easy question in Medium
- reuse an Easy question in Hard
- reuse a Medium question in Hard

A harder question must be conceptually harder, not merely
worded in a more complicated way.

{previous_question_block}

============================================================
QUESTION RULES
============================================================

Generate exactly {count} questions.

For every question:

- Exactly 4 options
- Exactly 1 correct answer
- 3 plausible incorrect options
- Match the selected subject
- Match the selected topic
- Match the requested difficulty
- Be suitable for a university student
- Prefer understanding/application over pure memorization
- Avoid ambiguity
- Avoid multiple technically correct answers
- Do not use "All of the above"
- Do not use "None of the above"

============================================================
EXPLANATION
============================================================

Each question must have an explanation.

The explanation should:
- Explain why the correct answer is correct
- Stay within the selected subject/topic
- Be appropriate for the requested difficulty

============================================================
JSON FORMAT
============================================================

Return ONLY valid JSON.

Use exactly:

{{
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "correct_answer": 0,
      "explanation": "Explanation."
    }}
  ]
}}

correct_answer MUST be:
0 = Option A
1 = Option B
2 = Option C
3 = Option D

============================================================
FINAL VALIDATION
============================================================

Before returning the response, verify:

- Exactly {count} questions
- Exactly 4 options per question
- Exactly 1 correct answer per question
- correct_answer is 0, 1, 2, or 3
- Every question matches {subject}
- Every question matches {selected_topic}
- Every question matches {difficulty}
- No question duplicates the previous question list
- No question is a trivial rewording of another question
- No Easy/Medium/Hard question is reused
- Every explanation matches its correct answer
- Response is valid JSON
- There is NO text outside the JSON object

RETURN ONLY THE JSON OBJECT.
"""


# ============================================================
# CLEAN / VALIDATE QUIZ QUESTIONS
# ============================================================

def clean_quiz_questions(
    raw_questions,
    count,
    previous_questions
):

    if not isinstance(
        raw_questions,
        list
    ):
        raise ValueError(
            "StudyMate JSON does not contain "
            "a valid 'questions' array."
        )

    cleaned = []

    seen_questions = set()

    previous_signatures = {
        normalize_text(question)
        for question in previous_questions
    }

    for q in raw_questions:

        if not isinstance(q, dict):
            continue

        question_text = q.get(
            "question"
        )

        options = q.get(
            "options"
        )

        correct_answer = q.get(
            "correct_answer"
        )

        explanation = q.get(
            "explanation",
            ""
        )

        # ----------------------------------------------------
        # QUESTION TEXT
        # ----------------------------------------------------

        if not isinstance(
            question_text,
            str
        ):
            continue

        question_text = (
            question_text.strip()
        )

        if not question_text:
            continue

        question_signature = (
            normalize_text(
                question_text
            )
        )

        # Duplicate inside current quiz
        if question_signature in seen_questions:
            continue

        # Duplicate from previous quizzes
        if question_signature in previous_signatures:
            continue

        # ----------------------------------------------------
        # OPTIONS
        # ----------------------------------------------------

        if (
            not isinstance(
                options,
                list
            )
            or len(options) != 4
        ):
            continue

        if not all(
            isinstance(
                option,
                (
                    str,
                    int,
                    float,
                    bool
                )
            )
            for option in options
        ):
            continue

        # ----------------------------------------------------
        # CORRECT ANSWER
        # ----------------------------------------------------

        if (
            not isinstance(
                correct_answer,
                int
            )
            or isinstance(
                correct_answer,
                bool
            )
        ):
            continue

        if (
            correct_answer < 0
            or correct_answer > 3
        ):
            continue

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        cleaned.append({
            "question":
                question_text,

            "options": [
                str(option).strip()
                for option in options
            ],

            "correct_answer":
                correct_answer,

            "explanation":
                str(explanation).strip()
        })

        seen_questions.add(
            question_signature
        )

        if len(cleaned) >= count:
            break

    if len(cleaned) != count:

        raise ValueError(
            f"StudyMate returned "
            f"{len(cleaned)} unique valid questions; "
            f"{count} were requested."
        )

    return cleaned


# ============================================================
# QUIZ GENERATION
# ============================================================

@app.post("/api/quiz")
def generate_quiz():

    started = time.perf_counter()

    body = request.get_json(
        silent=True
    ) or {}

    subject = str(
        body.get("subject") or ""
    ).strip()

    topic = str(
        body.get("topic") or ""
    ).strip()

    difficulty = str(
        body.get("difficulty")
        or "medium"
    ).strip().lower()

    try:

        count = int(
            body.get(
                "number_of_questions"
            )
            or 5
        )

    except (
        TypeError,
        ValueError
    ):

        count = 5

    count = max(
        1,
        min(count, 10)
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not subject:

        return jsonify({
            "error":
                "Subject is required."
        }), 400

    if difficulty not in DIFFICULTY_RULES:

        return jsonify({
            "error":
                "Difficulty must be easy, medium, or hard."
        }), 400

    selected_topic = (
        topic
        or
        "All important topics in the selected subject"
    )

    # --------------------------------------------------------
    # PREVIOUS QUESTIONS
    # --------------------------------------------------------

    previous_questions = (
        get_previous_questions(
            subject,
            selected_topic,
            limit=40
        )
    )

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    prompt = build_quiz_prompt(
        subject=subject,
        selected_topic=selected_topic,
        difficulty=difficulty,
        count=count,
        previous_questions=previous_questions
    )

    raw_response = ""

    # A few attempts help if the model accidentally
    # returns duplicates or malformed JSON.
    max_attempts = 3

    try:

        for attempt in range(
            1,
            max_attempts + 1
        ):

            # On retry, refresh history because a prior attempt
            # may have already produced valid questions that must
            # be excluded.
            current_history = (
                get_previous_questions(
                    subject,
                    selected_topic,
                    limit=40
                )
            )

            prompt = build_quiz_prompt(
                subject=subject,
                selected_topic=selected_topic,
                difficulty=difficulty,
                count=count,
                previous_questions=current_history
            )

            raw_response = (
                call_studymate(
                    prompt
                )
            )

            print(
                "\n========== STUDYMATE QUIZ RESPONSE =========="
            )
            print(
                f"Attempt: {attempt}"
            )
            print(
                raw_response
            )
            print(
                "==============================================\n"
            )

            data = extract_json(
                raw_response
            )

            if not isinstance(
                data,
                dict
            ):
                raise ValueError(
                    "StudyMate returned "
                    "an invalid JSON object."
                )

            try:

                cleaned = (
                    clean_quiz_questions(
                        raw_questions=data.get(
                            "questions"
                        ),
                        count=count,
                        previous_questions=current_history
                    )
                )

                # Success
                break

            except ValueError:

                if attempt == max_attempts:
                    raise

                # Try again with the updated exclusion list.
                continue

        # ----------------------------------------------------
        # SAVE HISTORY
        # ----------------------------------------------------

        save_quiz_history(
            subject,
            selected_topic,
            cleaned
        )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success":
                True,

            "subject":
                subject,

            "topic":
                topic,

            "difficulty":
                difficulty,

            "questions":
                cleaned,

            "count":
                len(cleaned),

            "latency_ms":
                round(
                    (
                        time.perf_counter()
                        - started
                    ) * 1000
                )

        })

    except Exception as exc:

        return jsonify({

            "error":
                f"Quiz generation failed: {exc}",

            "raw_response":
                raw_response[:3000]

        }), 502


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5001"
            )
        ),
        debug=True
    )
