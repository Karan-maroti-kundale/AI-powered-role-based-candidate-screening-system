"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type StartInterviewResponse = {
  success: boolean;
  message: string;
  session_id: string;
  role_name: string;
  filename?: string;
  text_length: number;
  extracted_profile: {
    skills: string[];
    technologies: string[];
    years_of_experience: number;
  };
  first_question: {
    question_id: string;
    question_number: number;
    question_text: string;
    question_type: string;
    difficulty_level: string;
    retrieved_topics?: string[];
    rationale?: string;
  };
};

const ROLES = [
  "Backend Engineer",
  "AI/ML Engineer",
  "Data Scientist",
  "Full Stack Developer",
  "Frontend Developer",
  "DevOps Engineer",
];

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedRole, setSelectedRole] = useState<string>("AI/ML Engineer");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string>("");

  const backendUrl = useMemo(
    () => process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000",
    []
  );

  const handleFile = (file: File | null) => {
    setError("");
    if (!file) return;

    if (file.type !== "application/pdf") {
      setError("Please upload a PDF resume only.");
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0] || null;
    handleFile(file);
  };

  const handleUpload = async () => {
  if (!selectedFile) {
    setError("Please choose a PDF resume.");
    return;
  }

  if (!selectedRole) {
    setError("Please select a role.");
    return;
  }

  setIsUploading(true);
  setError("");

  try {
    const formData = new FormData();

    // MUST match FastAPI parameter name: resume_file
    formData.append("resume_file", selectedFile);

    // MUST match FastAPI parameter name: role_name
    formData.append("role_name", selectedRole);

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"}/interview/start`,
      {
        method: "POST",
        body: formData,
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data?.detail || data?.message || "Failed to start interview.");
    }

    localStorage.setItem(`mcq_session_${data.session_id}`, JSON.stringify(data));
    router.push(`/interview/${data.session_id}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Something went wrong.";
    setError(message);
  } finally {
    setIsUploading(false);
  }
};

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50">
      <div className="mx-auto flex min-h-screen max-w-7xl items-center px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid w-full gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <section className="flex flex-col justify-center">
            <div className="inline-flex w-fit rounded-full border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700">
              AI-Powered Candidate Screening
            </div>

            <h1 className="mt-5 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
              Upload a resume, choose a role, and start a smart interview in seconds.
            </h1>

            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
              The system extracts resume skills, searches a role-specific knowledge base,
              and generates interview questions that adapt to the candidate’s background.
            </p>

            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-900">1. Upload Resume</p>
                <p className="mt-2 text-sm text-slate-600">
                  Send a PDF resume and let the backend parse it.
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-900">2. Extract Skills</p>
                <p className="mt-2 text-sm text-slate-600">
                  The AI builds a structured candidate profile.
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-900">3. Start Interview</p>
                <p className="mt-2 text-sm text-slate-600">
                  A role-aware first question appears immediately.
                </p>
              </div>
            </div>

            <p className="mt-8 text-sm text-slate-500">
              Supported roles are tuned for fast demoing: Backend, AI/ML, Data Science,
              Full Stack, Frontend, and DevOps.
            </p>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/50">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-slate-900">Start New Interview</h2>
              <p className="mt-2 text-sm text-slate-600">
                Upload a resume and select the target role.
              </p>
            </div>

            <div className="space-y-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Select Role
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {ROLES.map((role) => {
                    const active = selectedRole === role;
                    return (
                      <button
                        key={role}
                        type="button"
                        onClick={() => setSelectedRole(role)}
                        className={`rounded-xl border px-3 py-3 text-sm font-medium transition ${
                          active
                            ? "border-indigo-600 bg-indigo-600 text-white shadow-sm"
                            : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        {role}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`cursor-pointer rounded-2xl border-2 border-dashed p-6 transition ${
                  dragActive
                    ? "border-indigo-500 bg-indigo-50"
                    : "border-slate-300 bg-slate-50 hover:bg-slate-100"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => handleFile(e.target.files?.[0] || null)}
                />

                <div className="text-center">
                  <p className="text-sm font-semibold text-slate-900">
                    Drag and drop your PDF resume here
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    or click to browse files
                  </p>

                  <div className="mt-4 inline-flex rounded-full bg-white px-4 py-2 text-xs font-medium text-slate-700 shadow-sm">
                    {selectedFile ? selectedFile.name : "No file selected"}
                  </div>
                </div>
              </div>

              {selectedFile ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-medium text-slate-900">Selected file</p>
                  <p className="mt-1 text-sm text-slate-600">{selectedFile.name}</p>
                </div>
              ) : null}

              {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                  <p className="text-sm font-medium text-red-700">{error}</p>
                </div>
              ) : null}

              <button
                type="button"
                onClick={handleUpload}
                disabled={isUploading}
                className="inline-flex w-full items-center justify-center rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isUploading ? "Launching Interview..." : "Start Interview"}
              </button>

              <p className="text-center text-xs text-slate-500">
                Your first question will open automatically after upload.
              </p>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}