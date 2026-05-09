import { ReactNode } from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  disabled?: boolean;
}

export default function Button({
  children,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={`px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg
        hover:bg-indigo-700 transition-colors duration-200
        disabled:bg-gray-400 disabled:cursor-not-allowed
        focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2
        ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
