import os
import time
import json
import re

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
FRONTEND = os.path.join(ROOT, "frontend")

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(
    __name__,
    static_folder=FRONTEND,
    static_url_path=""
)

CORS(app)

FOUNDRY_ENDPOINT = os.getenv(
    "AZURE_AI_PROJECT_ENDPOINT",
    "https://krish-project-resource.services.ai.azure.com/api/projects/krish-project"
)

STUDYMATE_AGENT = os.getenv("STUDYMATE_AGENT_NAME", "StudyMate")
STUDYMATE_VERSION = os.getenv("STUDYMATE_AGENT_VERSION", "13")

project_client = None
openai_client = None


def get_openai_client():
    global project_client, openai_client

    if openai_client is None:
        project_client = AIProjectClient(
            endpoint=FOUNDRY_ENDPOINT,
            credential=DefaultAzureCredential(),
        )
        openai_client = project_client.get_openai_client()

    return openai_client


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


def extract_json(text):
    if not text:
        raise ValueError("StudyMate returned an empty response.")

    text = text.strip()

    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"StudyMate did not return JSON. Raw response: {text[:1000]}"
        )

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"StudyMate returned invalid JSON: {exc}. "
            f"Raw response: {text[:1000]}"
        )


@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "agent": STUDYMATE_AGENT,
        "version": STUDYMATE_VERSION,
        "message": "StudyMate backend is running."
    })


@app.post("/api/chat")
def chat():
    started = time.perf_counter()

    body = request.get_json(silent=True) or {}

    message = str(body.get("message") or "").strip()
    subject = str(body.get("subject") or "").strip()

    if not message:
        return jsonify({"error": "Message is required."}), 400

    prompt = f"""
You are StudyMate, a university AI study assistant.

Use the connected Foundry IQ knowledge base and uploaded course
materials as the primary source for academic questions.

Selected subject:
{subject or "Not specified"}

Student question:
{message}

Give a clear educational answer in simple language.
Keep the answer focused on the selected subject.
"""

    try:
        answer = call_studymate(prompt)

        return jsonify({
            "answer": answer,
            "sources": [],
            "latency_ms": round(
                (time.perf_counter() - started) * 1000
            )
        })

    except Exception as exc:
        return jsonify({
            "error": f"StudyMate request failed: {exc}"
        }), 502


@app.post("/api/quiz")
def generate_quiz():
    started = time.perf_counter()

    body = request.get_json(silent=True) or {}

    subject = str(body.get("subject") or "").strip()
    topic = str(body.get("topic") or "").strip()
    difficulty = str(body.get("difficulty") or "medium").strip()

    try:
        count = int(body.get("number_of_questions") or 5)
    except (TypeError, ValueError):
        count = 5

    count = max(1, min(count, 10))

    if not subject:
        return jsonify({"error": "Subject is required."}), 400

    selected_topic = topic or "All important topics in the selected subject"

    # IMPORTANT:
    # Keep the runtime prompt short and task-focused.
    # The detailed behavior belongs in the StudyMate agent instructions.
    prompt = f"""
Create a university multiple-choice quiz.

Subject: {subject}
Topic: {selected_topic}
Difficulty: {difficulty}
Number of questions: {count}

Generate the requested quiz now.

Use the connected course knowledge when relevant.
Keep every question within the selected subject and topic.

Return only valid JSON using exactly this structure:
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
      "explanation": "Short explanation."
    }}
  ]
}}

Rules:
- Exactly {count} questions.
- Exactly 4 options per question.
- correct_answer is 0, 1, 2, or 3.
- One correct answer per question.
- No markdown.
- No code fences.
- No text before or after the JSON.
"""

    raw_response = ""

    try:
        raw_response = call_studymate(prompt)

        print("\n========== STUDYMATE QUIZ RESPONSE ==========")
        print(raw_response)
        print("==============================================\n")

        data = extract_json(raw_response)

        if not isinstance(data, dict):
            raise ValueError("StudyMate returned an invalid JSON object.")

        questions = data.get("questions")

        if not isinstance(questions, list):
            raise ValueError(
                "StudyMate JSON does not contain a valid 'questions' array."
            )

        cleaned = []

        for q in questions:
            if not isinstance(q, dict):
                continue

            question_text = q.get("question")
            options = q.get("options")
            correct_answer = q.get("correct_answer")
            explanation = q.get("explanation", "")

            if not isinstance(question_text, str):
                continue

            if not isinstance(options, list) or len(options) != 4:
                continue

            if not all(isinstance(option, (str, int, float, bool)) for option in options):
                continue

            if not isinstance(correct_answer, int) or isinstance(correct_answer, bool):
                continue

            if correct_answer < 0 or correct_answer > 3:
                continue

            cleaned.append({
                "question": question_text.strip(),
                "options": [str(option).strip() for option in options],
                "correct_answer": correct_answer,
                "explanation": str(explanation).strip()
            })

            if len(cleaned) >= count:
                break

        if len(cleaned) != count:
            raise ValueError(
                f"StudyMate returned {len(cleaned)} valid questions; "
                f"{count} were requested."
            )

        return jsonify({
            "success": True,
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "questions": cleaned,
            "count": len(cleaned),
            "latency_ms": round(
                (time.perf_counter() - started) * 1000
            )
        })

    except Exception as exc:
        return jsonify({
            "error": f"Quiz generation failed: {exc}",
            "raw_response": raw_response[:3000]
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5001")),
        debug=True
    )
