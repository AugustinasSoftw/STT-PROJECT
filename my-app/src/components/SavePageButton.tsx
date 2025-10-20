"use client";

import { useWorkspace } from "./providers/workspace";

export default function SavePageButton({
  id,
  title,
  href,
  defaultGroupId = "default",
}: {
  id: string;
  title: string;
  href: string;
  defaultGroupId?: string;
}) {
  const { savePage, createGroup, groups } = useWorkspace();

  const onSave = async () => {
    // simple prompt flow for now — later replace with a popover/select
    const names = groups.map(g => g.name).join(", ");
    const answer = window.prompt(
      `Save to which group?\nExisting: ${names}\n\nLeave blank for "Ungrouped" or type a new group name.`
    );

    // resolve group id
    let groupId = defaultGroupId;
    if (answer && answer.trim()) {
      const existing = groups.find(g => g.name.toLowerCase() === answer.toLowerCase());
      groupId = existing ? existing.id : createGroup(answer.trim());
    }

    savePage({ id, title, href, groupId });
  };

  return (
    <button
      onClick={onSave}
      className="rounded-md border border-zinc-700 px-3 py-1 text-sm hover:bg-zinc-800"
    >
      Save
    </button>
  );
}
