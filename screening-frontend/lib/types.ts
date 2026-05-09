export interface Question {
  id: string;
  text: string;
  type: "technical" | "behavioral" | "situational";
  difficulty: "easy" | "medium" | "hard";
}

export interface InterviewSession {
  id: string;
  candidateName: string;
  role: string;
  resumePath: string;
  startedAt: Date;
  completedAt?: Date;
  status: "active" | "completed" | "abandoned";
}

export interface Answer {
  questionId: string;
  text: string;
  timestamp: Date;
}

export interface InterviewResult {
  sessionId: string;
  score: number;
  feedback: string;
  strengths: string[];
  improvements: string[];
  answers: Array<{
    question: string;
    answer: string;
    score: number;
  }>;
}

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface InterviewResponse {
  sessionId: string;
  questions: Question[];
  totalQuestions: number;
}
