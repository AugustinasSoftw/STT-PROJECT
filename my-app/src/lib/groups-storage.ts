"use client";

export type RowData = { id: string | number; [k: string]: any };
export type Groups = Record<string, RowData[]>;

export const GROUPS_KEY = "groups:v1";
export const GROUPS_UPDATE = "groups:update";

// ---- read / write -------------------------------------------------
export function readGroups(): Groups {
  try {
    const raw = localStorage.getItem(GROUPS_KEY);
    return raw ? (JSON.parse(raw) as Groups) : {};
  } catch {
    return {};
  }
}

export function writeGroups(next: Groups) {
  try {
    localStorage.setItem(GROUPS_KEY, JSON.stringify(next));
  } finally {
    // notify same-tab listeners
    window.dispatchEvent(new Event(GROUPS_UPDATE));
  }
}

// ---- mutations (use these everywhere) ------------------------------
export function addToGroup(name: string, row: RowData) {
  const groups = readGroups();
  const key = name.trim();
  if (!key) return;

  const list = groups[key] ?? [];
  if (!list.some((r) => r.id === row.id)) {
    groups[key] = [...list, row];
    writeGroups(groups);
  }
}

export function removeItem(name: string, id: RowData["id"]) {
  const groups = readGroups();
  const list = groups[name] ?? [];
  const next = list.filter((r) => r.id !== id);
  if (next.length) groups[name] = next;
  else delete groups[name];
  writeGroups(groups);
}

export function removeGroup(name: string) {
  const groups = readGroups();
  delete groups[name];
  writeGroups(groups);
}
