// components/InterviewPanel.tsx

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  submitTest,
  type MCQQuestion,
  type MCQStartResponse,
  type SelectedAnswer,
} from "@/lib/api";

type InterviewPanelProps = {
  sessionId: string;
};

type StoredSessionData = MCQStartResponse;
type AnswerMap = Record<string, "A" | "B" | "C" | "D">;

const TEST_DURATION_SECONDS = 45 * 60; // 45 minutes

function formatTime(totalSeconds: number) {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safeSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (safeSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export default function InterviewPanel({ sessionId }: InterviewPanelProps) {
  const router = useRouter();

  const [sessionData, setSessionData] = useState<StoredSessionData | null>(null);
  const [questions, setQuestions] = useState<MCQQuestion[]>([]);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAutoSubmitting, setIsAutoSubmitting] = useState(false);
  const [error, setError] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState<string>("");
  const [endTime, setEndTime] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(TEST_DURATION_SECONDS);

  const hasSubmittedRef = useRef(false);
  const autoSubmitTriggeredRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const possibleKeys = [
      `mcq_session_${sessionId}`,
      `interview_session_${sessionId}`,
      `session_${sessionId}`,
      `candidate_session_${sessionId}`,
    ];

    let parsed: StoredSessionData | null = null;

    for (const key of possibleKeys) {
      const raw = window.localStorage.getItem(key);
      if (!raw) continue;

      try {
        const data = JSON.parse(raw) as StoredSessionData;
        if (data?.session_id === sessionId && Array.isArray(data?.questions)) {
          parsed = data;
          break;
        }
      } catch {
        continue;
      }
    }

    if (parsed) {
      setSessionData(parsed);
      setQuestions(parsed.questions || []);
      setError("");
    } else {
      setError(
        "No MCQ test data found for this session. Please start the assessment again from the home page."
      );
    }
  }, [sessionId]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const endTimeKey = `mcq_endTime_${sessionId}`;
    const existing = window.localStorage.getItem(endTimeKey);

    if (existing) {
      const parsed = Number(existing);
      if (!Number.isNaN(parsed) && parsed > 0) {
        setEndTime(parsed);
        return;
      }
    }

    const newEndTime = Date.now() + TEST_DURATION_SECONDS * 1000;
    window.localStorage.setItem(endTimeKey, String(newEndTime));
    setEndTime(newEndTime);
  }, [sessionId]);

  useEffect(() => {
    if (!endTime) return;

    const tick = () => {
      const diff = Math.max(Math.floor((endTime - Date.now()) / 1000), 0);
      setRemainingSeconds(diff);

      if (diff <= 0 && !hasSubmittedRef.current && !autoSubmitTriggeredRef.current) {
        autoSubmitTriggeredRef.current = true;
        setIsAutoSubmitting(true);
        void handleSubmitTest(true);
      }
    };

    tick();
    const intervalId = window.setInterval(tick, 1000);

    return () => window.clearInterval(intervalId);
  }, [endTime]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!questions.length) return;

    const startedKey = `mcq_started_at_${sessionId}`;
    if (!window.localStorage.getItem(startedKey)) {
      window.localStorage.setItem(startedKey, String(Date.now()));
    }
  }, [questions, sessionId]);

  const answeredCount = useMemo(() => Object.keys(answers).length, [answers]);

  const handleSelect = (questionId: string, selected: "A" | "B" | "C" | "D") => {
    if (isSubmitting || isAutoSubmitting) return;

    setError("");
    setSuccessMessage("");
    setAnswers((prev) => ({
      ...prev,
      [questionId]: selected,
    }));
  };

  const handleSubmitTest = useCallback(
    async (autoSubmit = false) => {
      if (hasSubmittedRef.current) return;

      if (!sessionData) {
        setError("Session data not loaded.");
        return;
      }

      if (questions.length !== 30) {
        setError(`Expected 30 questions, but found ${questions.length}.`);
        return;
      }

      const unanswered = questions.filter((q) => !answers[q.question_id]);

      if (!autoSubmit && unanswered.length > 0) {
        setError(
          `Please answer all 30 questions before submitting. Remaining: ${unanswered.length}`
        );
        return;
      }

      hasSubmittedRef.current = true;
      setIsSubmitting(true);
      if (autoSubmit) setIsAutoSubmitting(true);
      setError("");
      setSuccessMessage(autoSubmit ? "Time's up! Auto-submitting..." : "Submitting test...");

      try {
        const payloadAnswers: SelectedAnswer[] = questions.map((q) => ({
          question_id: q.question_id,
          selected_answer: answers[q.question_id] ?? "",
        }));

        const result = await submitTest({
          session_id: sessionId,
          answers: payloadAnswers,
        });

        setSuccessMessage(result.message || "Test submitted successfully.");

        window.localStorage.setItem(
          `mcq_results_${sessionId}`,
          JSON.stringify(result)
        );

        router.push(`/results/${sessionId}`);
      } catch (err) {
        hasSubmittedRef.current = false;
        autoSubmitTriggeredRef.current = false;

        const message =
          err instanceof Error ? err.message : "Something went wrong while submitting.";
        setError(message);
        setSuccessMessage("");
      } finally {
        setIsSubmitting(false);
        setIsAutoSubmitting(false);
      }
    },
    [answers, questions, router, sessionData, sessionId]
  );

  const timerIsUrgent = remainingSeconds <= 300;

  if (!sessionData || !questions.length) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">MCQ Assessment</h1>
        <p className="mt-3 text-sm text-slate-600">{error || "Loading test..."}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <p className="text-sm font-medium uppercase tracking-wide text-indigo-600">
            Session ID: {sessionId}
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">
            {sessionData.role_name} Assessment
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Answer all 30 questions. Your test will be graded automatically after submission.
          </p>
        </div>

        <div className="space-y-5">
          {questions.map((question) => {
            const currentAnswer = answers[question.question_id];
            const disabled = isSubmitting || isAutoSubmitting || remainingSeconds <= 0;

            return (
              <div
                key={question.question_id}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-sm"
              >
                <div className="mb-3 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Question {question.question_number}
                    </p>
                    <h2 className="mt-1 text-lg font-semibold leading-7 text-slate-900">
                      {question.question_text}
                    </h2>
                  </div>

                  <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700">
                    {question.difficulty_level}
                  </span>
                </div>

                <div className="mt-4 grid gap-3">
                  {question.options.map((option) => {
                    const isSelected = currentAnswer === option.key;

                    return (
                      <label
                        key={option.key}
                        className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 transition ${
                          disabled
                            ? "cursor-not-allowed opacity-60"
                            : isSelected
                            ? "border-indigo-600 bg-indigo-50"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                        }`}
                      >
                        <input
                          type="radio"
                          name={question.question_id}
                          value={option.key}
                          checked={isSelected}
                          disabled={disabled}
                          onChange={() =>
                            handleSelect(question.question_id, option.key)
                          }
                          className="mt-1 h-4 w-4 accent-indigo-600"
                        />
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            {option.key}. {option.text}
                          </p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {error ? (
          <p className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
            {error}
          </p>
        ) : null}

        {successMessage ? (
          <p className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
            {successMessage}
          </p>
        ) : null}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-600">
            Answered:{" "}
            <span className="font-semibold text-slate-900">{answeredCount}</span> /{" "}
            <span className="font-semibold text-slate-900">{questions.length}</span>
          </p>

          <button
            type="button"
            onClick={() => void handleSubmitTest(false)}
            disabled={isSubmitting || isAutoSubmitting || remainingSeconds <= 0}
            className="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isAutoSubmitting
              ? "Time's up! Auto-submitting..."
              : isSubmitting
              ? "Submitting Test..."
              : "Submit Test"}
          </button>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Assessment Status</h3>

          <div className="mt-4 space-y-4">
            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Countdown Timer
              </p>
              <p
                className={`mt-2 text-3xl font-bold ${
                  timerIsUrgent ? "text-red-600" : "text-slate-900"
                }`}
              >
                {formatTime(remainingSeconds)}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {remainingSeconds <= 0
                  ? "Time is over."
                  : isAutoSubmitting
                  ? "Auto-submitting your test..."
                  : "45-minute test window"}
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                Candidate Profile
              </p>
              <p className="mt-2 text-sm text-slate-700">
                <span className="font-medium">Experience:</span>{" "}
                {sessionData.extracted_profile.years_of_experience} years
              </p>
              <p className="mt-1 text-sm text-slate-700">
                <span className="font-medium">Skills:</span>{" "}
                {sessionData.extracted_profile.skills.length
                  ? sessionData.extracted_profile.skills.join(", ")
                  : "Not extracted"}
              </p>
              <p className="mt-1 text-sm text-slate-700">
                <span className="font-medium">Technologies:</span>{" "}
                {sessionData.extracted_profile.technologies.length
                  ? sessionData.extracted_profile.technologies.join(", ")
                  : "Not extracted"}
              </p>
            </div>

            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Test Summary</p>
              <p className="mt-2 text-sm text-slate-700">
                <span className="font-medium">Role:</span> {sessionData.role_name}
              </p>
              <p className="mt-1 text-sm text-slate-700">
                <span className="font-medium">Questions:</span> {questions.length}
              </p>
              <p className="mt-1 text-sm text-slate-700">
                <span className="font-medium">Answered:</span> {answeredCount}
              </p>
            </div>

            <div className="rounded-xl border border-dashed border-slate-300 p-4">
              <p className="text-sm text-slate-600">
                The timer is stored in localStorage using an absolute end timestamp, so refreshes do not reset the test.
              </p>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}