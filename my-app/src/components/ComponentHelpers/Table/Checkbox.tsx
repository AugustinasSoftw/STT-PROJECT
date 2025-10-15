import { useEffect, useRef } from "react";

export default function CheckBoxs({
  checked,
  indeterminate,
  onChange,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: React.ChangeEventHandler<HTMLInputElement>;
}) {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = Boolean(indeterminate) && !checked;
    }
  }, [indeterminate, checked]);

  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className={`
        h-4 w-4 rounded border 
         focus:ring-offset-1
        disabled:opacity-50 disabled:cursor-not-allowed
        cursor-pointer
      `}
    />
  );
}
