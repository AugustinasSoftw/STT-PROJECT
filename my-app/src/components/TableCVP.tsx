"use client";

import type { RowData } from "@tanstack/react-table";

declare module "@tanstack/react-table" {
  interface TableMeta<TData extends RowData> {
    offset: number;
  }
}
//reactIcons
import { FaRegFile } from "react-icons/fa";
import { MdKeyboardArrowDown } from "react-icons/md";
import { MdKeyboardArrowUp } from "react-icons/md";
import { MdKeyboardArrowRight } from "react-icons/md";
import { FaFilter } from "react-icons/fa";
import { PiShareFatLight } from "react-icons/pi";
import { IoMdCloseCircleOutline } from "react-icons/io";
//Components
import Checkbox from "./ComponentHelpers/Table/Checkbox";
import Navigator from "./ComponentHelpers/Table/Navigator";
import Paggination from "./ComponentHelpers/Table/Pagination";
import Share from "./ComponentHelpers/Table/Share";
// Util
import { useEffect, useRef, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  getExpandedRowModel,
  PaginationState,
} from "@tanstack/react-table";

// ✅ type-only import so client bundle doesn’t pull server code
import type { CVPRow } from "@/app/db/schema";
import type { SelectedProps } from "@/app/types/types";
import { usePathname } from "next/navigation";
import Link from "next/link";

const columns: ColumnDef<CVPRow>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllRowsSelected()}
        indeterminate={table.getIsSomeRowsSelected()}
        onChange={table.getToggleAllRowsSelectedHandler()}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        indeterminate={row.getIsSomeSelected?.()}
        onChange={row.getToggleSelectedHandler()}
      />
    ),
    size: 35,
    enableSorting: false,
    enableHiding: false,
  },
  {
    id: "eil_nr",
    header: "Eil_nr",
    cell: ({ row, table }) => {
      const offs = table.options.meta?.offset ?? 0;
      return offs + row.index + 1;
    },
  },
  {
    accessorKey: "notice_id",
    header: "Notice ID",
    cell: ({ row }) => {
      const id = row.original.notice_id; // string | null

      if (!id) {
        return <span className="text-zinc-500 italic">—</span>; // or "No ID"
      }

      return (
        <Link
          target="_blank"
          href={`/notices/${encodeURIComponent(id)}`}
          prefetch
          className="text-blue-400 underline hover:opacity-80"
          onClick={(e) => e.stopPropagation()}
        >
          {id}
        </Link>
      );
    },
  },
  { accessorKey: "title", header: "Title" },

  { accessorKey: "publish_date", header: "Priėmimo data" },

  {
    id: "notice_url",
    header: " Notice url",
    cell: ({ row }) => {
      const value = row.original.notice_url;

      if (!value) return null;

      const fullurl = `https://www.e-tar.lt/${value}`;

      return (
        <a
          className="flex items-center justify-center"
          href={fullurl}
          target="_blank"
        >
          {" "}
          <FaRegFile />
        </a>
      );
    },
  },

  {
    id: "lot_no",
    header: "Korupcijos rizika",
    cell: ({ row }) => {
      const raw = row.original.lot_no;
      const score = raw == null ? NaN : parseFloat(raw);

      return (
        <div
          className={`border w-4 h-4 border-black rounded-full inline-flex items-center justify-center
      ${
        score >= 0.7
          ? "bg-red-700"
          : score >= 0.5
          ? "bg-yellow-400"
          : "bg-green-500"
      }
      `}
        ></div>
      );
    },
  },

  {
    id: "actions",
    header: "Analizė",
    cell: ({ row }) => (
      <button
        type="button"
        onClick={() => row.toggleExpanded()}
        aria-expanded={row.getIsExpanded()}
        title={row.getIsExpanded() ? "Collapse" : "Expand"}
        className="cursor-pointer"
      >
        {row.getIsExpanded() ? <MdKeyboardArrowDown /> : <MdKeyboardArrowUp />}
      </button>
    ),
  },
];

export default function TableCVP() {
  // Declarations //
  const [data, setData] = useState<CVPRow[]>([]);
  const [expanded, setExpanded] = useState({});
  //Selection
  const [rowSelection, setRowSelection] = useState({});

  //Pagination declarations
  const [totalRows, setTotalRows] = useState(0);
  const [pageIndex, setPageIndex] = useState(0);
  const [offset, setOffset] = useState(0);
  //Navigation declars
  const [sorting, setSorting] = useState<SelectedProps | null>(null);
  const filterParams = new URLSearchParams(
    Object.entries(sorting ?? {}).filter(([_, value]) => value)
  );
  const qs = filterParams.toString();
  const prevQsRef = useRef(qs);
  //Loading
  const [isLoading, setIsLoading] = useState(true);
  const [isFirstLoad, setisFirstLoad] = useState(true);
  const pageSize = 10;
  const rowHeight = 74;
  const pathname = usePathname();
  const inFlight = useRef(0);
  // Filter hook
  const [openFilter, setOpenFilter] = useState(false);
  const [openShare, setOpenShare] = useState(false);

  // Declarations //

  //Fetching
  useEffect(() => {
    // If you need to reset the page on qs change, do it but DON'T return
    if (prevQsRef.current !== qs && pageIndex !== 0) {
      setPageIndex(0);
      prevQsRef.current = qs;
    }

    const controller = new AbortController();
    const reqId = ++inFlight.current; // mark this request as latest

    setIsLoading(true); // always show skeleton first

    (async () => {
      try {
        const newOffset = pageIndex * pageSize;
        setOffset(newOffset);

        const res = await fetch(
          `/api/cvp?limit=${pageSize}&offset=${newOffset}`,
          {
            signal: controller.signal,
            cache: "no-store",
          }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const json = await res.json();

        if (reqId !== inFlight.current) return; // stale response, ignore

        setData(json.rows ?? []);
        setTotalRows(json.totalRows ?? 0);
        prevQsRef.current = qs;
      } catch (e: any) {
        if (e.name !== "AbortError") console.error(e);
      } finally {
        if (reqId === inFlight.current) {
          // ONLY latest request clears loading
          setIsLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [pageIndex, pageSize, pathname, qs]);
  //Fetching \\

  const table = useReactTable({
    data,
    columns,
    state: { expanded, rowSelection },
    onExpandedChange: setExpanded,
    getRowCanExpand: () => true,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    meta: {
      offset,
    },
  });
  console.log(isLoading);
  const selectedFromIds = table
    .getSelectedRowModel()
    .flatRows.map((r) => r.original);

  return (
    <>
      <div className="flex flex-col rounded-lg max-w-[1350px] min-w-[1250px] mx-auto">
        <div className="w-full bg-[oklch(0.205_0_0)] rounded-t-xl p-2 dark:border-[oklch(1_0_0_/_10%)] border border-gray-800">
          <div className="mx-auto max-w-[1400px] h-20 grid grid-cols-3 items-center px-4 ">
            {/* left column: filter + chips */}
            <div className="col-start-1 flex items-center gap-3 overflow-x-auto">
              <button
                onClick={() => setOpenFilter((p) => !p)}
                className="inline-flex items-center gap-2 rounded-lg bg-[oklch(0.205_0_0)] text-white border dark:border-[oklch(1_0_0_/_30%)]
                   px-3 py-2 shadow-sm hover:bg-[oklch(0.145_0_0)] transition cursor-pointer"
                aria-label="Filtrai"
              >
                <FaFilter className="text-base" />
                <span className="hidden sm:inline mr-1">Filtrai</span>
              </button>

              {sorting && Object.values(sorting).some((v) => v) && (
                <div className="text-white p-2 text-sm flex items-center gap-2 flex-wrap">
                  {Object.entries(sorting ?? {}).map(([key, value], i) =>
                    value ? (
                      <div
                        onClick={() =>
                          setSorting((prev) =>
                            prev ? { ...prev, [key]: "" } : prev
                          )
                        }
                        key={i}
                        className="flex items-center gap-1 border border-gray-400 rounded-lg px-3 py-1 cursor-pointer bg-[oklch(0.205_0_0)]"
                      >
                        <span>{String(value)}</span>
                        <IoMdCloseCircleOutline size={18} />
                      </div>
                    ) : null
                  )}
                </div>
              )}
            </div>

            {/* center column: pagination */}
            <div className="col-start-2 justify-self-center">
              <Paggination
                pageIndex={pageIndex}
                isLoading={isLoading}
                pageSize={pageSize}
                totalRows={totalRows}
                setPageIndex={setPageIndex}
              />
            </div>

            {/* right column: share */}
            <div className="col-start-3 justify-self-end">
              <button
                type="button"
                onClick={() => setOpenShare((p) => !p)}
                className="inline-flex items-center gap-2 rounded-lg bg-[oklch(0.205_0_0)] text-white border dark:border-[oklch(1_0_0_/_30%)]
                   px-3 py-2 shadow-sm ring-white/10 hover:bg-[oklch(0.145_0_0)] transition cursor-pointer"
                aria-label="Bendrinti"
              >
                <PiShareFatLight size={24} />
                <span className="hidden sm:inline">Bendrinti</span>
              </button>
            </div>
          </div>

          {openFilter && (
            <Navigator
              {...{ openFilter, setOpenFilter, sorting, setSorting }}
            />
          )}
        </div>

        <table className="w-full table-fixed font-sans text-center dark:bg-[oklch(0.205_0_0)] text-sm">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    className={`border border-t-0 p-1 border-black dark:border-[oklch(1_0_0_/_10%)] border: 
              ${h.column.id === "pavadinimas" ? "  w-[470px] " : undefined}
              ${h.column.id === "select" ? "  w-[85px] " : undefined}
               ${h.column.id === "eil_nr" ? " w-[85px]" : undefined}
              `}
                  >
                    {h.isPlaceholder
                      ? null
                      : flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          {isLoading ? (
            <tbody className="">
              {Array.from({ length: pageSize }).map((_, i) => (
                <tr key={i} style={{ height: rowHeight }}>
                  {table.getAllLeafColumns().map((col) => (
                    <td key={col.id} className="px-3">
                      <div className="h-3 w-3/4 rounded bg-gray-500 animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : (
            <tbody>
              {table.getRowModel().rows.flatMap((row) =>
                [
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={`
              px-4 py-2 border border-b-0 dark:border-[oklch(1_0_0_/_10%)] border-gray-800
              ${
                cell.column.id === "pavadinimas"
                  ? "text  font-medium w-[470px]"
                  : undefined
              }
              ${
                cell.column.id === "eil_nr"
                  ? " font-medium w-[85px]"
                  : undefined
              }`}
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>,

                  row.getIsExpanded() && (
                    <tr
                      className="dark:border-[oklch(1_0_0_/_10%)] border "
                      key={`${row.id}-exp`}
                    >
                      <td
                        colSpan={table.getVisibleLeafColumns().length}
                        className="p-0 bg-white dark:bg-[oklch(0.205_0_0)] border-none "
                      >
                        <div className="border-t bg-[oklch(0.205_0_0)] ">
                          <div className=" mb-3 rounded-b-xl border border-black dark:border-[oklch(1_0_0_/_55%)] overflow-hidden border-t-0  p-6 shadow-sm ">
                            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                              {/* Summary */}
                              <div className="min-w-0 md:max-w-[80%]">
                                <p className="text-base font-semibold uppercase tracking-wider text-gray-500 dark:text-[oklch(0.930_0_0)]">
                                  Dirbtinio intelekto išvada
                                </p>
                                <p className="mt-2 text-lg leading-relaxed text-gray-800 whitespace-pre-line dark:text-[oklch(0.930_0_0)]">
                                  {row.original.lot_no ?? "—"}
                                </p>
                              </div>

                              {/* Risk panel */}
                              <div className="shrink-0 md:text-right">
                                <p className="text-base font-semibold uppercase tracking-wider text-gray-500 font-mono dark:text-[oklch(0.930_0_0)]">
                                  Rizika
                                </p>

                                {/* score badge */}
                                <span
                                  className={`mt-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset
                ${
                  !row.original.lot_no
                    ? "bg-gray-100 text-gray-700 ring-gray-200"
                    : parseFloat(row.original.lot_no) >= 0.7
                    ? "bg-red-100 text-red-700 ring-red-200"
                    : parseFloat(row.original.lot_no) >= 0.5
                    ? "bg-yellow-100 text-yellow-800 ring-yellow-200"
                    : "bg-green-100 text-green-700 ring-green-200"
                }`}
                                >
                                  {Number.isFinite(
                                    parseFloat(row.original.lot_no ?? "")
                                  )
                                    ? parseFloat(row.original.lot_no!).toFixed(
                                        3
                                      )
                                    : "—"}
                                </span>

                                {/* progress bar (width via Tailwind fractions, no inline style) */}
                                <div className="mt-2 h-2 w-40 rounded-full bg-gray-200">
                                  <div
                                    className={`h-2 rounded-full
                  ${
                    !row.original.lot_no
                      ? "w-0 bg-gray-300"
                      : parseFloat(row.original.lot_no) >= 0.9
                      ? "w-full bg-red-500"
                      : parseFloat(row.original.lot_no) >= 0.7
                      ? "w-4/5 bg-red-500"
                      : parseFloat(row.original.lot_no) >= 0.5
                      ? "w-3/5 bg-yellow-400"
                      : parseFloat(row.original.lot_no) >= 0.3
                      ? "w-2/5 bg-green-500"
                      : "w-1/5 bg-green-500"
                  }`}
                                  />
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ),
                ].filter(Boolean)
              )}
            </tbody>
          )}
        </table>

        <div className=" bg-[oklch(0.205_0_0)] rounded-t-none rounded-lg w-full border h-24 offset  dark:border-[oklch(1_0_0_/_10%)] flex items-center justify-center mb-10">
          <Paggination
            pageIndex={pageIndex}
            isLoading={isLoading}
            totalRows={totalRows}
            pageSize={pageSize}
            setPageIndex={setPageIndex}
          />
        </div>
      </div>
    </>
  );
}
