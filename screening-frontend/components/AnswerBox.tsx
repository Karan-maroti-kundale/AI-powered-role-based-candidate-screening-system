interface AnswerBoxProps {
  answer: string;
  onChange: (answer: string) => void;
}

export default function AnswerBox({ answer, onChange }: AnswerBoxProps) {
  return (
    <div className="mb-6">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Your Answer
      </label>
      <textarea
        value={answer}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type your answer here..."
        rows={6}
        className="w-full px-4 py-3 border border-gray-300 rounded-lg
          focus:outline-none focus:ring-2 focus:ring-indigo-500
          focus:border-transparent resize-none"
      />
      <p className="text-xs text-gray-500 mt-2">
        {answer.length} characters
      </p>
    </div>
  );
}
