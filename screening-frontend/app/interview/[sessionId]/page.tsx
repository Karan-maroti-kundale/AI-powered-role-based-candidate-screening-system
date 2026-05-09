// app/interview/[sessionId]/page.tsx

import InterviewPanel from "@/components/InterviewPanel";

type PageProps = {
  params: {
    sessionId: string;
  };
};

export default function InterviewPage({ params }: PageProps) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 px-4 py-8">
      <div className="mx-auto max-w-5xl">
        <InterviewPanel sessionId={params.sessionId} />
      </div>
    </main>
  );
}