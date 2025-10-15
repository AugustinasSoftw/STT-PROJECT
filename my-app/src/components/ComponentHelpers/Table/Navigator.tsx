"use client";

import { useId, useState } from "react";
import { IoMdClose } from "react-icons/io";
import type { SelectedProps } from "@/app/types/navigation";
import { IoIosArrowDown } from "react-icons/io";
import { MdKeyboardArrowRight } from "react-icons/md";

type NavigatorProps = {
  openFilter: boolean;
  setOpenFilter: React.Dispatch<React.SetStateAction<boolean>>;
  sorting: SelectedProps | null;
  setSorting: React.Dispatch<React.SetStateAction<SelectedProps | null>>;
};

export default function Navigator({
  setSorting,
  sorting,
  openFilter,
  setOpenFilter,
}: NavigatorProps) {
  const rusys = ["Įsakymas", "Potvarkis", "Nutarimas", "Dekretas", "Rezoliucija"];
  const dazniausiaiNaudNavigatoriai = ["Aukšta korupcijos rizika"];

  const [selected, setSelected] = useState(false);
  const [DNNopen, setDNNOpen] = useState(false);
  const [Ropen, setROpen] = useState(false);
  

  if (!openFilter) return null;
  console.log(sorting);
  return (
    <>
     <div className="fixed inset-0" onClick={() => setOpenFilter(false)} />
    <div className="relative z-[90]">
      {/* Panel */}
      <div className="absolute mt-2 w-[420px] max-h-[72vh] overflow-hidden rounded-xl bg-zinc-800/95 text-zinc-100 shadow-2xl ring-1 ring-white/10 backdrop-blur -ml-1">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center gap-2 h-14 px-4 border-b border-white/10 bg-zinc-800/80 backdrop-blur">
          <span className="text-xl font-semibold">Filtrai</span>
          <button
            onClick={() => setOpenFilter(false)}
            className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white/30"
            aria-label="Uždaryti"
          >
            <IoMdClose />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto p-2 pr-3">
          {/* Section: DNN */}
          <div className="mb-2">
            <button
              onClick={() => setDNNOpen((p) => !p)}
              aria-expanded={DNNopen}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-base hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-white/20"
            >
              <span className="font-medium">Dažniausiai naudojami navigatoriai</span>
              <IoIosArrowDown
                className={`transition-transform ${DNNopen ? "-rotate-90" : "rotate-0"}`}
                aria-hidden
              />
            </button>

            <div
              className={`overflow-hidden rounded-lg border border-white/10 bg-zinc-700/50 transition-all ${
                DNNopen ? "mt-1 max-h-[480px] opacity-100" : "max-h-0 opacity-0"
              }`}
            >
              <ul className="py-1 ">
                {dazniausiaiNaudNavigatoriai.map((r) => (
                  <label
                    key={r}
                    htmlFor={r}
                    className="flex items-center gap-3 px-3 py-2 hover:bg-white/5 cursor-pointer"
                  >
                     <input
                          id={r}
                          type="checkbox"
                          className="h-4 w-4 accent-white/80 "
                          checked={sorting?.dazniausiaiNaudNav === r}   
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                            setSorting((prev:any) => ({
                              ...prev,
                              dazniausiaiNaudNav: e.target.checked ? r : undefined, 
                            }));
                          }}
                        />
                    <span className="text-base">{r}</span>
                  </label>
                ))}
              </ul>
            </div>
          </div>

          {/* Section: Rušys */}
          <div className="mb-2">
            <button
              onClick={() => setROpen((p) => !p)}
              aria-expanded={Ropen}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-base hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-white/20"
            >
              <span className="font-medium">Rušys</span>
              <IoIosArrowDown
                className={`transition-transform ${Ropen ? "-rotate-90" : "rotate-0"}`}
                aria-hidden
              />
            </button>

            <div
              className={`overflow-hidden rounded-lg border border-white/10 bg-zinc-700/50 transition-all ${
                Ropen ? "mt-1 max-h-[480px] opacity-100" : "max-h-0 opacity-0"
              }`}
            >
              <ul className="py-1">
                {rusys.map((r) => (
                  <label
                    key={r}
                    htmlFor={r}
                    className="flex items-center gap-3 px-3 py-2 hover:bg-white/5 cursor-pointer"
                  >
                    <input
                      id={r}
                      type="checkbox"
                      className="h-4 w-4 accent-white/80"
                      checked={sorting?.rusys === r} 
                     onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                            setSorting((prev:any) => ({
                              ...prev,
                              rusys: e.target.checked ? r : undefined, 
                            }));
                          }}
                    />
                    <span className="text-base">{r}</span>
                  </label>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

     
     
    </div>
    
      </>
  );
}
