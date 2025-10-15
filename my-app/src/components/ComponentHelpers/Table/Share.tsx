import { useEffect, useState } from "react";
import { RiCloseLargeFill } from "react-icons/ri";
import { BiLogoGmail } from "react-icons/bi";
import { FaFacebookMessenger } from "react-icons/fa";
import { BsTelegram, BsWhatsapp } from "react-icons/bs";
import NavigationGmail from "../Navigation/NavigationGmail";
import { IoMdClose } from "react-icons/io";

type Row = {
  id: string | number;
  pavadinimas: string;
  istaigos_nr: string;
  priemimo_data: string;
  ai_risk_score: any;
};

type ShareProps = {
  selectedFromIds: Row[];
  openShare: boolean;
  setOpenShare: React.Dispatch<React.SetStateAction<boolean>>;
};

export default function Share({
  selectedFromIds,
  openShare,
  setOpenShare,
}: ShareProps) {
  const [openGmail, setOpenGmail] = useState(false);

  // reset Gmail step when popover closes
  useEffect(() => {
    if (!openShare) setOpenGmail(false);
  }, [openShare]);

  if (!openShare) return null;

  return (
    <>
      {/* backdrop (outside click) */}
      <div
        className="fixed inset-0 z-[90] bg-black/0"
        onClick={() => setOpenShare(false)}
      />

      {/* popover container (top-right example; adjust position as you like) */}
      <div
        className="relative flex justify-end z-[90]"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          role="dialog"
          aria-label="Share menu"
          className={`absolute mt-2 max-h-[72vh] overflow-hidden rounded-xl bg-zinc-800/95 text-zinc-100
                      shadow-2xl ring-1 ring-white/10 backdrop-blur
                      ${openGmail ? "w-[420px]" : "w-[350px]"}`}
        >
          {/* header */}
          <div className="sticky top-0 z-10 flex items-center gap-2 h-14 px-4 border-b border-white/10 bg-zinc-800/80 backdrop-blur">
            <h2 className="text-xl font-semibold">
              {openGmail ? "Siųsti naudojant „Gmail“" : "Bendrinti"}
            </h2>
            {!openGmail ? (
              <div className="ml-auto flex items-center gap-1">
                <button
                  onClick={() => setOpenShare(false)}
                  className="rounded-md px-2 py-1 hover:bg-white/10"
                  aria-label="Uždaryti"
                >
                  <IoMdClose />
                </button>
              </div>
            ) : (
              <div className="ml-auto flex items-center gap-1">
                {openGmail && (
                  <button
                    onClick={() => setOpenGmail(false)}
                    className="rounded-md px-2 py-1 hover:bg-white/10"
                  >
                    Atgal
                  </button>
                )}
              </div>
            )}
          </div>

          {/* body swaps between menu and Gmail */}
          <div className="p-2">
            {openGmail ? (
              <NavigationGmail
                rows={selectedFromIds}
                onCancel={() => setOpenGmail(false)}
                onDone={() => setOpenShare(false)}
              />
            ) : (
              <>
                <MenuItem
                  icon={<BiLogoGmail />}
                  text="Siųsti naudojant „Gmail“"
                  onClick={() => setOpenGmail(true)}
                />
                <MenuItem
                  icon={<FaFacebookMessenger />}
                  text="Siųsti per „Messenger“"
                />
                <MenuItem icon={<BsWhatsapp />} text='Bendrinti "WhatsApp"' />
                <MenuItem icon={<BsTelegram />} text='Bendrinti "Telegram"' />
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function MenuItem({
  icon,
  text,
  onClick,
}: {
  icon: React.ReactNode;
  text: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 rounded-xl px-3 py-2 hover:bg-white/5 text-left transition"
    >
      <span className="text-lg">{icon}</span>
      <span className="text-sm">{text}</span>
    </button>
  );
}
