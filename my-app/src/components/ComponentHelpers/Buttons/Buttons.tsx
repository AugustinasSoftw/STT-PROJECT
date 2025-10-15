import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MoreHorizontalIcon,
} from "lucide-react";

type ButtonProps = {
  disabled?: boolean;
};

export function NextButton({ disabled }: ButtonProps) {
  return (
    <span
      className={`inline-flex dark:border-[oklch(1_0_0_/_30%)] border items-center justify-center rounded-md bg-[oklch(0.205_0_0)] h-9 w-9 text-zinc-200 shadow-sm   transition-all duration-160 hover:bg-[oklch(0.145_0_0)]
        ${
          disabled
            ? "opacity-45 cursor-not-allowed hover:bg-[oklch(0.145_0_0)]"
            : ""
        }`}
    >
      <ChevronRightIcon className="h-4 w-4" />
    </span>
  );
}
export function NextNextButton({ disabled }: ButtonProps) {
  return (
    <span
      className={`inline-flex dark:border-[oklch(1_0_0_/_30%)] border items-center justify-center rounded-md bg-[oklch(0.205_0_0)] h-9 w-9 text-zinc-200 shadow-sm   transition-all duration-160 hover:bg-[oklch(0.145_0_0)]
        ${
          disabled
            ? "opacity-45 cursor-not-allowed hover:bg-[oklch(0.145_0_0)]"
            : ""
        }`}
    >
      <ChevronRightIcon className="h-4 w-4" />
      <ChevronRightIcon className="h-4 w-4 -ml-3" />
    </span>
  );
}
export function BacktButton({ disabled }: ButtonProps) {
  return (
    <span
      className={`inline-flex dark:border-[oklch(1_0_0_/_30%)] border items-center justify-center rounded-md bg-[oklch(0.205_0_0)] h-9 w-9 text-zinc-200 shadow-sm   transition-all duration-160 hover:bg-[oklch(0.145_0_0)]
        ${
          disabled
            ? "opacity-45 cursor-not-allowed hover:bg-[oklch(0.145_0_0)]"
            : ""
        }`}
    >
      <ChevronLeftIcon className="h-4 w-4" />
    </span>
  );
}
export function BackBackButton({ disabled }: ButtonProps) {
  return (
    <span
      className={`inline-flex dark:border-[oklch(1_0_0_/_30%)] border items-center justify-center rounded-md bg-[oklch(0.205_0_0)] h-9 w-9 text-zinc-200 shadow-sm   transition-all duration-160 hover:bg-[oklch(0.145_0_0)]
        ${
          disabled
            ? "opacity-45 cursor-not-allowed hover:bg-[oklch(0.145_0_0)]"
            : ""
        }`}
    >
      <ChevronLeftIcon className="h-4 w-4" />
      <ChevronLeftIcon className="h-4 w-4 -ml-3" />
    </span>
  );
}
