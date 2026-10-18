import type { ComponentProps } from "react";

const variants = {
  primary: "bg-blue-700 text-white hover:bg-blue-800",
  secondary: "border border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800",
  danger: "bg-red-700 text-white hover:bg-red-800",
  "danger-outline": "border border-red-300 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950",
};

export default function Button({ variant = "secondary", type = "button", className = "", ...props }: ComponentProps<"button"> & {
  variant?: keyof typeof variants;
}) {
  return (
    <button
      type={type}
      className={`rounded-md px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
