# 🎓 StudyMate — AI Academic Companion

> **An AI-powered academic study assistant that helps university students understand course concepts, ask grounded questions, revise quickly, and test themselves with adaptive quizzes.**

StudyMate is built around the student's actual course subjects and study material. It combines a modern web interface with a Flask backend and an Azure AI Foundry agent connected to a retrieval-grounded knowledge base.

---

## ✨ What is StudyMate?

StudyMate is designed to act like a personal academic companion rather than a generic chatbot.

Students can:

- 💬 Ask questions about their course material
- 📚 Get answers grounded in uploaded/connected study resources
- 🎯 Select the subject they are currently studying
- 🧠 Revise concepts in simple, student-friendly language
- 📝 Generate multiple-choice quizzes from a selected subject and topic
- ⚙️ Choose quiz difficulty: Easy, Medium, or Hard
- 📊 Track quiz performance and identify questions/concepts that need revision
- 🔄 Generate another quiz for additional practice
- ❤️ Use a clean, responsive interface designed for focused studying

---

## 📚 Supported Subjects

StudyMate currently supports these six academic subjects:

1. **Programming Abstraction**
2. **CNDC**
3. **System Design**
4. **Backend Engineering**
5. **NALR**
6. **DNN — Deep Neural Networks**

---

# 🧩 Core Technology Stack

StudyMate is built around **four main technology pillars**:

### 1. 🌐 Frontend — HTML + Tailwind CSS + JavaScript

The frontend provides the complete student-facing experience.

- HTML5 for structure
- Tailwind CSS for responsive styling
- Vanilla JavaScript for application logic and API communication
- Responsive glassmorphism-based UI
- Interactive subject selection
- Chat interface
- Quiz interface
- Loading and error states
- Dynamic quiz rendering and scoring

The frontend communicates with the Flask backend through REST API endpoints.

---

### 2. 🐍 Backend — Python + Flask

The backend acts as the secure bridge between the browser and Azure AI Foundry.

Technologies:

- Python
- Flask
- Flask-CORS
- python-dotenv
- REST APIs

The backend handles:

- Chat requests
- Quiz generation requests
- Request validation
- JSON parsing and validation
- Azure authentication/client initialization
- Agent communication
- Health checks
- Error handling

Important: Azure credentials and authentication details are kept on the backend rather than exposed in the browser.

---

### 3. 🤖 AI Layer — Microsoft Azure AI Foundry

StudyMate uses an **Azure AI Foundry agent** as its main intelligence layer.

The backend sends student requests to the configured StudyMate agent and receives the generated response.

The current configuration supports:

- Azure AI Foundry project integration
- StudyMate agent reference
- Versioned agent configuration
- Azure identity-based authentication
- AI-generated academic explanations
- AI-generated quiz questions
- Structured JSON quiz responses

The backend currently references the StudyMate agent and its configured version through environment variables.

---

### 4. 🔎 RAG / Grounded Knowledge — Foundry IQ Knowledge Base

StudyMate uses retrieval-grounded generation so academic answers and quizzes can be based primarily on the student's connected course material.

The flow is:

```text
Student Question
       ↓
Frontend
       ↓
Flask Backend
       ↓
Azure AI Foundry Agent
       ↓
Foundry IQ / Connected Knowledge
       ↓
Relevant Course Material
       ↓
AI-generated Answer
       ↓
Frontend
```

This allows StudyMate to focus responses on the selected academic subject and the material available to the agent.

---

# 💬 AI Chat

The main StudyMate experience is the academic chat assistant.

A student selects a subject and asks something such as:

> "Explain the network layer in simple terms."

The frontend sends the request to:

```http
POST /api/chat
```

The Flask backend adds the selected subject and academic instructions before sending the request to the StudyMate agent.

The response is then returned to the browser and displayed in the chat interface.

### Chat design goals

- Simple explanations
- Course-focused answers
- Grounding in connected study material
- No Azure credentials in frontend code
- Clear loading and error states

---

# 📝 AI Quiz Generator

StudyMate also includes an active-recall quiz system.

Students select:

- Subject
- Topic
- Difficulty

The frontend sends the request to:

```http
POST /api/quiz
```

The backend asks the StudyMate agent to generate a structured quiz.

Each generated question contains:

```json
{
  "question": "Question text",
  "options": [
    "Option A",
    "Option B",
    "Option C",
    "Option D"
  ],
  "correct_answer": 0,
  "explanation": "Short explanation."
}
```

The quiz system validates the returned JSON before sending it to the frontend.

### Quiz features

- Multiple-choice questions
- Exactly four options per question
- One correct answer
- Difficulty selection
- Topic-specific generation
- Subject-specific generation
- Explanations after answering
- Automatic score calculation
- Incorrect-question tracking
- Weak-area/revision guidance
- Generate-new-quiz flow

---

# 🧠 Quiz Flow

```text
Select Subject
      ↓
Enter Topic
      ↓
Select Difficulty
      ↓
Generate Quiz
      ↓
Azure AI Foundry Agent
      ↓
Grounded Course Knowledge
      ↓
Structured JSON Quiz
      ↓
Frontend Validation
      ↓
Answer Questions
      ↓
Calculate Score
      ↓
Identify Incorrect / Weak Areas
      ↓
Revision Guidance
```

---

# 🔐 Security & Configuration

Sensitive Azure configuration should **never** be placed directly in the frontend.

The backend uses environment variables for configuration, including the Azure AI Foundry project endpoint and StudyMate agent configuration.

Example:

```env
AZURE_AI_PROJECT_ENDPOINT=your-project-endpoint
STUDYMATE_AGENT_NAME=StudyMate
STUDYMATE_AGENT_VERSION=13
```

Authentication is handled through Azure Identity rather than exposing credentials in `index.html`.

> **Never commit `.env` or Azure credentials to GitHub.**

---

# 📁 Project Structure

```text
StudyMate/
│
├── frontend/
│   └── index.html              # Main StudyMate web application
│
├── backend/
│   ├── server.py               # Flask API + Azure Foundry integration
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment configuration template
│   └── .venv/                   # Local virtual environment (not committed)
│
├── stitch-original/
│   ├── code.html               # Original generated frontend
│   ├── DESIGN.md
│   └── screen.png
│
├── DESIGN.md                   # UI/design documentation
├── screen.png                  # Project screenshot
├── .gitignore
└── README.md
```

---

# 🚀 Run Locally

## 1. Clone the repository

```bash
git clone https://github.com/Krish-Mahajan24/AI-Study-Assistant.git
cd AI-Study-Assistant
```

## 2. Create a virtual environment

```bash
cd backend
python3 -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

```bash
cp .env.example .env
```

Add your Azure AI Foundry configuration to `.env`.

## 5. Start Flask

```bash
python server.py
```

The application will be available at:

```text
http://localhost:5000
```

---

# 🔌 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Serves the StudyMate frontend |
| `GET` | `/api/health` | Checks backend/agent configuration |
| `POST` | `/api/chat` | Sends an academic question to StudyMate |
| `POST` | `/api/quiz` | Generates a structured academic quiz |

---

# 🏗️ Architecture

```text
┌───────────────────────────────┐
│        StudyMate UI           │
│ HTML + Tailwind + JavaScript  │
└───────────────┬───────────────┘
                │ REST API
                ▼
┌───────────────────────────────┐
│        Python / Flask         │
│   API + Validation + CORS     │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│      Azure AI Foundry         │
│       StudyMate Agent         │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│     Foundry IQ / RAG          │
│   Course Knowledge Base       │
└───────────────┬───────────────┘
                │
                ▼
         Grounded Response
                │
                ▼
          StudyMate UI
```

---

# 🎨 UI / UX

StudyMate uses a modern academic-product aesthetic inspired by premium AI and music-app interfaces.

Key design characteristics:

- Dark theme
- Glassmorphism cards
- Purple/cyan accent gradients
- Responsive layouts
- Smooth transitions
- Clear visual hierarchy
- Interactive controls
- Student-focused information density

---

# 🛠️ Current Functionality

### Academic Assistant

- [x] Subject selection
- [x] Course-focused AI chat
- [x] Backend API integration
- [x] Azure AI Foundry agent integration
- [x] RAG/knowledge-base grounding
- [x] Backend health check
- [x] Error handling

### Active Recall Quiz

- [x] Subject selection
- [x] Topic selection
- [x] Difficulty selection
- [x] AI quiz generation
- [x] Four-option MCQs
- [x] Answer validation
- [x] Explanations
- [x] Score calculation
- [x] Incorrect-question tracking
- [x] Weak-area/revision guidance
- [x] New quiz generation

---

# 🔮 Future Scope

Potential extensions include:

- 📈 Student progress dashboard
- 🧠 Personalized revision plans
- ⏰ Spaced-repetition reminders
- 📊 Subject-wise performance analytics
- 📄 Automatic notes and summaries from uploaded material
- 🎯 Personalized question difficulty based on previous performance
- 🗂️ Topic-level mastery tracking
- 🔍 More detailed RAG source/citation display
- ☁️ Cloud deployment with a production API

---

# 👨‍💻 Project

**StudyMate — AI Academic Companion**

Built as an academic AI project using **Microsoft Azure AI Foundry, RAG/Foundry IQ, Python Flask, and a modern HTML/Tailwind/JavaScript frontend.**

---

## 📌 Note

StudyMate is an educational project. AI-generated responses can contain mistakes, so students should verify important academic information against their official course material and instructor-provided resources.
