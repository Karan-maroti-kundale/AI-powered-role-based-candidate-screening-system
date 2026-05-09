// lib/api.ts

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export type MCQOption = {
  key: "A" | "B" | "C" | "D";
  text: string;
};

export type MCQQuestion = {
  question_id: string;
  question_number: number;
  question_text: string;
  options: MCQOption[];
  difficulty_level: "easy" | "medium" | "hard" | string;
};

export type ExtractedProfile = {
  skills: string[];
  technologies: string[];
  years_of_experience: number;
};

export type MCQStartResponse = {
  success: boolean;
  message: string;
  session_id: string;
  role_name: string;
  filename?: string;
  text_length: number;
  extracted_profile: ExtractedProfile;
  questions: MCQQuestion[];
};

export type SelectedAnswer = {
  question_id: string;
  selected_answer: "A" | "B" | "C" | "D" | string;
};

export type SubmitTestRequest = {
  session_id: string;
  answers: SelectedAnswer[];
};

export type QuestionGrade = {
  question_id: string;
  question_number: number;
  selected_answer: string | null;
  correct_answer: string;
  is_correct: boolean;
  explanation?: string | null;
};

export type SubmitTestResponse = {
  success: boolean;
  message: string;
  session_id: string;
  total_questions: number;
  correct_count: number;
  score_text: string;
  percentage: number;
  results: QuestionGrade[];
};

export type ResultsResponse = {
  success: boolean;
  session_id: string;
  role_name: string;
  score_text: string;
  percentage: number;
  total_questions: number;
  correct_count: number;
  report_text: string;
  strengths: string[];
  improvement_focus: string[];
  recommendation: string;
};

export async function submitTest(
  payload: SubmitTestRequest
): Promise<SubmitTestResponse> {
  const response = await fetch(`${BACKEND_URL}/interview/submit-test`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || "Failed to submit test.");
  }

  return data as SubmitTestResponse;
}

export async function fetchMCQSummary(
  sessionId: string
): Promise<ResultsResponse> {
  const response = await fetch(
    `${BACKEND_URL}/interview/${sessionId}/results`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || "Failed to fetch results.");
  }

  return data as ResultsResponse;
}

/*
  Optional helper if you still want to keep a typed start API call on the frontend.
  This is useful if your upload screen directly calls the backend and then stores
  the response in localStorage.
*/
export async function startMCQInterview(formData: FormData): Promise<MCQStartResponse> {
  const response = await fetch(`${BACKEND_URL}/interview/start`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || "Failed to start interview.");
  }

  return data as MCQStartResponse;
}