interface QuestionCardProps {
  question: {
    id: string;
    text: string;
    type: string;
  };
}

export default function QuestionCard({ question }: QuestionCardProps) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-block px-3 py-1 bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-full">
          {question.type}
        </span>
      </div>
      <h2 className="text-2xl font-bold text-gray-900 leading-relaxed">
        {question.text}
      </h2>
    </div>
  );
}
