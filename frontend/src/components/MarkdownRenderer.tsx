import React from "react";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = "" }) => {
  if (!content) return null;

  // Split into blocks by double newlines or table boundary
  const lines = content.split("\n");
  const blocks: Array<{ type: "heading" | "table" | "list" | "p"; level?: number; items?: string[]; rows?: string[][]; text?: string }> = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // 1. Heading
    if (trimmed.startsWith("### ")) {
      blocks.push({ type: "heading", level: 3, text: trimmed.slice(4) });
      i++;
      continue;
    } else if (trimmed.startsWith("## ")) {
      blocks.push({ type: "heading", level: 2, text: trimmed.slice(3) });
      i++;
      continue;
    } else if (trimmed.startsWith("# ")) {
      blocks.push({ type: "heading", level: 1, text: trimmed.slice(2) });
      i++;
      continue;
    }

    // 2. Table detection (starts with | and contains |)
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2) {
        // Parse rows
        const parsedRows = tableLines.map((row) =>
          row
            .slice(1, -1)
            .split("|")
            .map((cell) => cell.trim())
        );

        // Filter out separator row (e.g. |---|---|)
        const headerRow = parsedRows[0];
        const dataRows = parsedRows.slice(1).filter((r) => !r.every((c) => /^[:\s-]+$/.test(c)));

        blocks.push({
          type: "table",
          rows: [headerRow, ...dataRows],
        });
        continue;
      }
    }

    // 3. Bullet list (- or *)
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const listItems: string[] = [];
      while (i < lines.length && (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* "))) {
        listItems.push(lines[i].trim().slice(2));
        i++;
      }
      blocks.push({ type: "list", items: listItems });
      continue;
    }

    // 4. Numbered list (e.g. "1. ")
    if (/^\d+\.\s/.test(trimmed)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        const itemText = lines[i].trim().replace(/^\d+\.\s*/, "");
        listItems.push(itemText);
        i++;
      }
      blocks.push({ type: "list", items: listItems });
      continue;
    }

    // 5. Normal paragraph
    const pLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("#") &&
      !(lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) &&
      !lines[i].trim().startsWith("- ") &&
      !lines[i].trim().startsWith("* ") &&
      !/^\d+\.\s/.test(lines[i].trim())
    ) {
      pLines.push(lines[i]);
      i++;
    }
    blocks.push({ type: "p", text: pLines.join(" ") });
  }

  // Helper for inline rendering (bold, code, inline badges, math symbols)
  const renderInline = (rawText: string) => {
    // Replace HTML entities
    let sanitized = rawText
      .replace(/&ge;/g, "≥")
      .replace(/&le;/g, "≤")
      .replace(/&times;/g, "×")
      .replace(/&plusmn;/g, "±");

    // Tokenize into bold (**), code (`), and badges ([CRITICAL], [WARN], etc.)
    const parts: React.ReactNode[] = [];
    let remaining = sanitized;
    let keyIdx = 0;

    // Regex matching: **bold**, `code`, or [BADGE]
    const tokenRegex = /(\*\*[^*]+\*\*|`[^`]+`|\[(?:CRITICAL|WARN|OK|FEASIBLE|MARGINAL|PENDING|HIGH|TOP RECOMMENDATION|P1|P2)\])/;

    while (remaining) {
      const match = remaining.match(tokenRegex);
      if (!match || match.index === undefined) {
        parts.push(remaining);
        break;
      }

      if (match.index > 0) {
        parts.push(remaining.slice(0, match.index));
      }

      const matchedToken = match[0];
      if (matchedToken.startsWith("**") && matchedToken.endsWith("**")) {
        parts.push(
          <strong key={keyIdx++} className="font-semibold text-white">
            {renderInline(matchedToken.slice(2, -2))}
          </strong>
        );
      } else if (matchedToken.startsWith("`") && matchedToken.endsWith("`")) {
        const codeText = matchedToken.slice(1, -1);
        parts.push(
          <code key={keyIdx++} className="bg-[#262634] text-teal-300 px-1 py-0.5 rounded text-[11px] font-mono border border-[#3b3b4d]">
            {codeText}
          </code>
        );
      } else if (matchedToken.startsWith("[") && matchedToken.endsWith("]")) {
        const tag = matchedToken.slice(1, -1);
        let badgeClass = "badge-neutral text-[10px] mx-0.5 border border-[#3b3b4d] px-1.5 py-0.2 rounded font-mono";
        if (tag === "CRITICAL" || tag === "P1") {
          badgeClass = "bg-red-950/80 text-red-300 border border-red-800 text-[10px] mx-0.5 px-1.5 py-0.5 rounded font-mono font-bold";
        } else if (tag === "WARN" || tag === "MARGINAL" || tag === "PENDING" || tag === "P2") {
          badgeClass = "bg-amber-950/80 text-amber-300 border border-amber-800 text-[10px] mx-0.5 px-1.5 py-0.5 rounded font-mono font-medium";
        } else if (tag === "OK" || tag === "FEASIBLE" || tag === "TOP RECOMMENDATION") {
          badgeClass = "bg-teal-950/80 text-teal-300 border border-teal-800 text-[10px] mx-0.5 px-1.5 py-0.5 rounded font-mono font-bold";
        }
        parts.push(
          <span key={keyIdx++} className={badgeClass}>
            [{tag}]
          </span>
        );
      }

      remaining = remaining.slice(match.index + matchedToken.length);
    }

    return parts;
  };

  return (
    <div className={`space-y-2.5 text-[11.5px] leading-relaxed text-[#eeece7] ${className}`}>
      {blocks.map((block, idx) => {
        if (block.type === "heading") {
          if (block.level === 1) {
            return (
              <h1 key={idx} className="text-sm font-bold text-white pt-2 pb-1 border-b border-[#2b2b36] font-mono uppercase tracking-wider">
                {renderInline(block.text || "")}
              </h1>
            );
          }
          if (block.level === 2) {
            return (
              <h2 key={idx} className="text-xs font-bold text-white pt-2 pb-0.5 font-mono tracking-wide">
                {renderInline(block.text || "")}
              </h2>
            );
          }
          return (
            <h3 key={idx} className="text-[12px] font-semibold text-cohere-action-blue pt-1.5 pb-0.5 font-mono">
              {renderInline(block.text || "")}
            </h3>
          );
        }

        if (block.type === "table" && block.rows && block.rows.length > 0) {
          const header = block.rows[0];
          const bodyRows = block.rows.slice(1);
          return (
            <div key={idx} className="overflow-x-auto my-2 rounded border border-[#33333d] bg-[#14141c]">
              <table className="w-full text-left border-collapse text-[11px] font-mono">
                <thead>
                  <tr className="bg-[#1f1f2b] border-b border-[#33333d]">
                    {header.map((col, cIdx) => (
                      <th key={cIdx} className="px-2.5 py-1.5 text-[#9e9ea7] font-semibold uppercase tracking-wider text-[10px]">
                        {renderInline(col)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#262633]">
                  {bodyRows.map((r, rIdx) => (
                    <tr key={rIdx} className="hover:bg-[#1a1a26] transition-colors">
                      {r.map((cell, cIdx) => (
                        <td key={cIdx} className="px-2.5 py-1.5 text-[#eeece7] whitespace-nowrap">
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        if (block.type === "list" && block.items) {
          return (
            <ul key={idx} className="space-y-1 pl-3.5 list-disc marker:text-[#8c8c99]">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx} className="leading-snug">
                  {renderInline(item)}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={idx} className="leading-relaxed">
            {renderInline(block.text || "")}
          </p>
        );
      })}
    </div>
  );
};
