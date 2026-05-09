// components/SummaryPanel.tsx

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchMCQSummary, type ResultsResponse } from "@/lib/api";

type SummaryPanelProps = {
  sessionId: string;
};

export default function SummaryPanel({ sessionId }: SummaryPanelProps) {
  const router = useRouter();
  const [summary, setSummary] = useState<ResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const loadSummary = async () => {
      try {
        setLoading(true);
        setError("");
        const data = await fetchMCQSummary(sessionId);
        setSummary(data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load results.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    loadSummary();
  }, [sessionId]);

  const handleStartNewInterview = () => {
    router.push("/");
  };

  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Assessment Results</h1>
        <p className="mt-3 text-sm text-slate-600">Loading final report...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Assessment Results</h1>
        <p className="mt-3 text-sm font-medium text-red-600">{error}</p>

        <button
          onClick={handleStartNewInterview}
          className="mt-6 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
        >
          Start New Interview
        </button>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <p className="text-sm font-medium uppercase tracking-wide text-indigo-600">
            Final Score
          </p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">
            {summary.role_name} Assessment Results
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Session ID: {summary.session_id}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-xs uppercase tracking-wide text-slate-500">
              Score
            </p>
            <p className="mt-2 text-4xl font-bold text-slate-900">
              {summary.score_text}
            </p>
          </div>

          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-xs uppercase tracking-wide text-slate-500">
              Percentage
            </p>
            <p className="mt-2 text-4xl font-bold text-slate-900">
              {summary.percentage}%
            </p>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            AI Evaluation Report
          </p>
          <p className="mt-3 text-sm leading-7 whitespace-pre-line text-slate-700">
            {summary.report_text}
          </p>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={handleStartNewInterview}
            className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            Start New Interview
          </button>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Strengths</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {summary.strengths?.length ? (
              summary.strengths.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
                >
                  {item}
                </span>
              ))
            ) : (
              <p className="text-sm text-slate-500">No strengths recorded.</p>
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Improvement Focus</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {summary.improvement_focus?.length ? (
              summary.improvement_focus.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700"
                >
                  {item}
                </span>
              ))
            ) : (
              <p className="text-sm text-slate-500">No focus areas recorded.</p>
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Recommendation</h2>
          <p className="mt-3 text-sm leading-7 text-slate-700">
            {summary.recommendation || "No recommendation available."}
          </p>
        </div>
      </aside>
    </div>
  );
}