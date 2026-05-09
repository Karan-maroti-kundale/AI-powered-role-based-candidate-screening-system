// app/results/[sessionId]/page.tsx

import SummaryPanel from "@/components/SummaryPanel";

type PageProps = {
  params: {
    sessionId: string;
  };
};

export default function ResultsPage({ params }: PageProps) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 px-4 py-8">
      <div className="mx-auto max-w-5xl">
        <SummaryPanel sessionId={params.sessionId} />
      </div>
    </main>
  );
}