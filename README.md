# AI-powered role-based candidate screening system

A full-stack, AI-powered role-based candidate screening system that transforms a candidate’s resume and selected role into a personalized, timed, 30-question multiple-choice test in real time.

The platform is designed to simulate a modern technical screening workflow:
- resume upload and parsing
- skill extraction
- dynamic MCQ generation
- cheat-proof 45-minute assessment timer
- auto-grading
- AI-generated performance analysis

Built with a clean separation between frontend, backend, AI services, persistence, and retrieval layers.

---

## Overview

This project is an end-to-end **AI-powered role-based candidate screening system** for role-based candidate screening.

A student uploads a resume and selects a target role such as:
- Backend Engineer
- AI/ML Engineer
- Data Scientist
- Full Stack Developer
- Frontend Developer
- DevOps Engineer

The backend then:
1. extracts the resume text,
2. parses skills and technologies,
3. generates a personalized 30-question MCQ test,
4. stores the test in SQLite,
5. starts a strict 45-minute timer on the frontend,
6. auto-grades the submitted answers,
7. generates a final AI report with strengths and improvement areas.

The system is built to be resilient:
- OpenAI-powered generation is used first
- if quota or API access fails, it falls back to a curated high-quality local MCQ pool
- the assessment still runs end-to-end without breaking

---

## Key Features

### Dynamic 30-Question MCQ Generation
The system generates a unique test for every session based on:
- candidate resume skills
- extracted technologies
- selected role
- candidate experience level

### Cheat-Proof 45-Minute Timer
The test timer:
- stores an absolute end timestamp in `localStorage`
- survives refreshes
- auto-submits when the timer expires
- disables answer changes after time is up

### Auto-Grading
When the test is submitted:
- each answer is matched against the backend answer key
- score is computed automatically
- results are stored in the database

### AI Performance Report
After grading, the system generates a report that includes:
- final score
- percentage
- strengths
- improvement focus areas
- recommendation

---

## Project Structure

### Frontend
```bash
screening-frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── interview/[sessionId]/page.tsx
│   └── results/[sessionId]/page.tsx
├── components/
│   ├── InterviewPanel.tsx
│   ├── SummaryPanel.tsx
│   ├── UploadResume.tsx
│   └── ...
├── lib/
│   ├── api.ts
│   ├── types.ts
│   └── utils.ts
├── styles/
│   └── globals.css
└── .env.local
```

### Backend
```bash
screening-backend/
├── app/
│   ├── main.py
│   ├── db/
│   ├── services/
│   ├── vectorstore/
│   ├── scripts/
│   └── ...
├── data/
│   ├── knowledge_base/
│   └── uploads/
├── chroma_db/
├── .env
└── candidate_screening.db
```

## Setup Instructions

### 1) Backend Setup

**Create and activate virtual environment**
```bash
cd screening-backend
python -m venv venv
```

**Activate virtual environment**

Windows (PowerShell)
```powershell
venv\Scripts\Activate.ps1
```

Windows (Command Prompt)
```cmd
venv\Scripts\activate.bat
```

macOS / Linux
```bash
source venv/bin/activate
```

**Install dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Run the backend**
```bash
uvicorn app.main:app --reload
```

The backend will typically run at: `http://127.0.0.1:8000`

### 2) Frontend Setup

```bash
cd screening-frontend
npm install
npm run dev
```

The frontend will typically run at: `http://localhost:3000`

## How the System Works

### 1. 📤 Upload Resume
The candidate uploads a PDF resume and selects a role.

### 2. 🔍 Parse and Extract Profile
The backend:
- Extracts raw resume text
- Identifies skills
- Identifies technologies
- Estimates experience

### 3. 🧠 Generate 30 MCQs
The backend generates a personalized 30-question test:
- Each question has 4 options
- Each has 1 correct answer
- Questions are unique to the session

### 4. ⏱️ Start the Timer
The frontend creates a fixed 45-minute session timer:
- Stored in localStorage
- Survives refreshes
- Auto-submits at 00:00

### 5. 📝 Submit Test
The candidate completes the test and submits answers.

### 6. ✅ Grade Automatically
The backend compares selected answers against the answer key.

### 7. 📊 Generate Report
The backend returns:
- Score
- Percentage
- Strengths
- Improvement focus
- Recommendation

## Demo Video

[🎬 Watch the Full End-to-End System Demo (Google Drive)](https://drive.google.com/file/d/1yWQlGlz4YTLAiEvwfrhGkbOJIT4Aq08U/view?usp=sharing)

*This video demonstrates the complete workflow: resume upload, dynamic 30-MCQ generation, the cheat-proof timer, auto-grading, and the final AI evaluation report.*
