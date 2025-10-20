export type SelectedProps = {
        dazniausiaiNaudNav: string;
        rusys: string;
     }
export type SavedPage = {
  id: string;        // e.g. notice_id
  title: string;     // rowValue.title or buyer name
  href: string;      // e.g. `/notices/4564565`
  createdAt: string; // ISO date string
  groupId: string;   // the folder id this page belongs to
};

export type SavedGroup = {
  id: string;
  name: string;
  isOpen?: boolean;  // collapsed/expanded in UI
};
