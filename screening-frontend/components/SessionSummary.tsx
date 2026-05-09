"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Card from "./UI/Card";
import Button from "./UI/Button";

interface Result {
  score: number;
  feedback: string;
  strengths: string[];
  improvements: string[];
}

interface SessionSummaryProps {
  sessionId: string;
}

export default function SessionSummary({ sessionId }: SessionSummaryProps) {
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const response = await fetch(`/api/results/${sessionId}`);
        const data = await response.json();
        setResult(data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching results:", error);
        setLoading(false);
      }
    };

    fetchResult();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-600">Loading results...</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-gray-600">Results not available</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-center mb-8 text-gray-900">
          Interview Results
        </h1>

        <Card>
          <div className="text-center mb-8">
            <div className="inline-block">
              <div className="w-32 h-32 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <span className="text-5xl font-bold text-white">
                  {result.score}
                </span>
              </div>
            </div>
            <p className="text-gray-600 mt-4">Overall Score</p>
          </div>

          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Feedback
            </h2>
            <p className="text-gray-700 leading-relaxed">
              {result.feedback}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div>
              <h3 className="text-lg font-semibold text-green-700 mb-3">
                ✓ Strengths
              </h3>
              <ul className="space-y-2">
                {result.strengths.map((strength, index) => (
                  <li key={index} className="text-gray-700 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{strength}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-lg font-semibold text-orange-700 mb-3">
                ↑ Areas for Improvement
              </h3>
              <ul className="space-y-2">
                {result.improvements.map((improvement, index) => (
                  <li key={index} className="text-gray-700 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{improvement}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <Link href="/">
            <Button className="w-full">Start Another Interview</Button>
          </Link>
        </Card>
      </div>
    </div>
  );
}
