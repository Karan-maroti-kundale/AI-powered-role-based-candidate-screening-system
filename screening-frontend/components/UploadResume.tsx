"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Button from "./UI/Button";
import Card from "./UI/Card";
import RoleSelector from "./RoleSelector";
import { startInterview } from "@/lib/api"; // <-- Import our FastAPI helper

export default function UploadResume() {
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!file || !role) {
      setError("Please select a role and upload a resume (PDF only)");
      return;
    }

    setLoading(true);
    try {
      // 1. Send to our FastAPI backend using the helper from lib/api.ts
      const data = await startInterview(file, role);

      // 2. CRITICAL: Save the response so the Interview Panel can find the first question!
      localStorage.setItem(`interview_session_${data.session_id}`, JSON.stringify(data));

      // 3. Route to the live interview screen
      if (data.session_id) {
        router.push(`/interview/${data.session_id}`);
      }
    } catch (err: any) {
      console.error("Error uploading resume:", err);
      setError(err.message || "Failed to connect to the backend. Is the FastAPI server running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Job Role
          </label>
          <RoleSelector value={role} onChange={setRole} />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Upload Resume (PDF)
          </label>
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded file:border-0
              file:text-sm file:font-semibold
              file:bg-indigo-50 file:text-indigo-700
              hover:file:bg-indigo-100"
            required
          />
          {file && (
            <p className="mt-2 text-sm text-gray-600">
              Selected: {file.name}
            </p>
          )}
        </div>

        {error && <p className="text-sm text-red-600 font-medium">{error}</p>}

        <Button type="submit" disabled={loading || !file}>
          {loading ? "Analyzing Profile & Generating Questions..." : "Start Interview"}
        </Button>
      </form>
    </Card>
  );
}