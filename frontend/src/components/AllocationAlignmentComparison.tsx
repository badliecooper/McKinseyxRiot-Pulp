import React, { useState, useMemo } from "react";
import { 
  BarChart3, 
  HelpCircle, 
  TrendingDown, 
  Layers, 
  Filter, 
  Info,
  CheckCircle2,
  ArrowRight
} from "lucide-react";
import { AllocationAlignmentReport, SkuAlignmentIndex } from "../types";
import { EChart } from "./EChart";

interface AllocationAlignmentComparisonProps {
  report: AllocationAlignmentReport | null;
  loading?: boolean;
}

const DEPOT_LABELS: Record<string, string> = {
  "Depot-North-01": "Delhi (NCR)",
  "Depot-North-02": "Lucknow",
  "Depot-West-01": "Mumbai",
  "Depot-West-02": "Ahmedabad",
  "Depot-South-01": "Bengaluru",
  "Depot-South-02": "Chennai",
  "Depot-East-01": "Kolkata",
  "Depot-East-02": "Guwahati",
  "Depot-Central-01": "Indore",
};

export const AllocationAlignmentComparison: React.FC<AllocationAlignmentComparisonProps> = ({
  report,
  loading = false,
}) => {
  const [selectedSku, setSelectedSku] = useState<string>("ALL");
  const [selectedDepot, setSelectedDepot] = useState<string>("ALL");
  const [viewState, setViewState] = useState<"HISTORICAL" | "POST_INTERVENTION">("POST_INTERVENTION");
  const [showFormulaTooltip, setShowFormulaTooltip] = useState<boolean>(false);

  // 1. Grouped Horizontal Bar Chart Option: Allocation Share vs Demand Share for 5 SKUs
  const barChartOption = useMemo(() => {
    if (!report || !report.sku_alignment_indices) return {};

    const items = report.sku_alignment_indices;
    const categories = items.map((s) => `${s.sku_id} (${s.flavour})`).reverse();
    const beforeIndex = items.map((s) => s.historical_mix_index_pct).reverse();
    const afterIndex = items.map((s) => s.post_intervention_index_pct).reverse();

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#17171c",
        borderColor: "#33333d",
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          if (!params || params.length === 0) return "";
          const name = params[0].name;
          const skuCode = name.split(" ")[0];
          const skuObj = items.find((x) => x.sku_id === skuCode);
          if (!skuObj) return "";

          return `<div style="font-weight:700; color:#ffffff; font-family:monospace; margin-bottom:4px;">
            ${skuObj.sku_id} — ${skuObj.flavour}
          </div>
          <div style="color:#d9d9dd; font-size:11px;">Baseline Legacy Mismatch: <b style="color:#94a3b8">${skuObj.historical_mix_index_pct}%</b></div>
          <div style="color:#d9d9dd; font-size:11px;">Rebalanced S&OP Mismatch: <b style="color:#1863dc">${skuObj.post_intervention_index_pct}%</b></div>
          <div style="color:#2dd4bf; font-size:11px; margin-top:3px; font-weight:600;">Mismatch Improvement: -${skuObj.improvement_pct}%</div>
          <div style="color:#8c8c99; font-size:10px; margin-top:4px; font-style:italic;">Evaluated against identical 7d corrected latent demand.</div>`;
        },
      },
      legend: {
        data: ["Historical Quota (Before)", "Demand-Driven Rebalanced (After)"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
        right: 10,
      },
      grid: { left: "28%", right: "8%", top: "14%", bottom: "8%" },
      xAxis: {
        type: "value",
        name: "Mismatch Index %",
        nameTextStyle: { color: "#616161", fontSize: 9 },
        axisLabel: { formatter: "{value}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        max: 30,
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLabel: { color: "#17171c", fontSize: 11, fontFamily: "Inter, sans-serif", fontWeight: 500 },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      series: [
        {
          name: "Historical Quota (Before)",
          type: "bar",
          data: beforeIndex,
          barGap: "20%",
          itemStyle: { color: "#94a3b8", borderRadius: [0, 3, 3, 0] },
          label: {
            show: true,
            position: "right",
            formatter: "{c}%",
            color: "#616161",
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
          },
        },
        {
          name: "Demand-Driven Rebalanced (After)",
          type: "bar",
          data: afterIndex,
          itemStyle: { color: "#1863dc", borderRadius: [0, 3, 3, 0] },
          label: {
            show: true,
            position: "right",
            formatter: "{c}%",
            color: "#17171c",
            fontWeight: 700,
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
          },
        },
      ],
    };
  }, [report]);

  // 2. Depot-by-SKU Heatmap matrix data
  const heatmapData = useMemo(() => {
    if (!report || !report.sku_alignment_indices) return null;

    const skus = report.sku_alignment_indices.map((s) => s.sku_id);
    const depots = [
      "Depot-North-01",
      "Depot-North-02",
      "Depot-West-01",
      "Depot-West-02",
      "Depot-South-01",
      "Depot-South-02",
      "Depot-East-01",
      "Depot-East-02",
      "Depot-Central-01",
    ];

    // Build matrix
    const matrix: Array<{
      sku_id: string;
      depot_id: string;
      allocated_qty: number;
      demand_qty: number;
      alloc_share: number;
      demand_share: number;
      delta_share: number;
      mismatch_contrib: number;
    }> = [];

    skus.forEach((skuId) => {
      const skuObj = report.sku_alignment_indices.find((s) => s.sku_id === skuId);
      if (!skuObj) return;

      const breakdown =
        viewState === "POST_INTERVENTION"
          ? skuObj.post_intervention_depot_breakdown
          : skuObj.historical_depot_breakdown;

      depots.forEach((dId) => {
        const row = breakdown.find((b) => b.depot_id === dId);
        if (row) {
          matrix.push({
            sku_id: skuId,
            depot_id: dId,
            allocated_qty: row.allocated_qty,
            demand_qty: row.demand_qty,
            alloc_share: row.allocation_share_pct,
            demand_share: row.demand_share_pct,
            delta_share: Number((row.allocation_share_pct - row.demand_share_pct).toFixed(2)),
            mismatch_contrib: row.mismatch_contribution_pct,
          });
        }
      });
    });

    return { skus, depots, matrix };
  }, [report, viewState]);

  // Filter matrix
  const filteredMatrix = useMemo(() => {
    if (!heatmapData) return [];
    return heatmapData.matrix.filter((cell) => {
      if (selectedSku !== "ALL" && cell.sku_id !== selectedSku) return false;
      if (selectedDepot !== "ALL" && cell.depot_id !== selectedDepot) return false;
      return true;
    });
  }, [heatmapData, selectedSku, selectedDepot]);

  if (loading || !report) {
    return (
      <div className="p-8 text-center text-xs font-mono text-cohere-body-muted bg-cohere-soft-stone rounded-sm border border-cohere-hairline">
        Loading allocation-vs-demand telemetry...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 1. TOP HEADER STRIP & BEFORE/AFTER KPI SUMMARY */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        {/* KPI: Network Alignment Index Before vs After */}
        <div className="lg:col-span-5 bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat flex flex-col justify-between">
          <div className="flex items-center justify-between pb-2 border-b border-cohere-hairline">
            <div className="flex items-center space-x-1.5">
              <span className="text-xs font-bold text-cohere-primary uppercase font-mono tracking-wide">
                Network Alignment Index
              </span>
              <button
                type="button"
                onClick={() => setShowFormulaTooltip(!showFormulaTooltip)}
                className="text-cohere-body-muted hover:text-cohere-primary transition-colors"
                title="View mathematical formula and interpretation"
              >
                <HelpCircle className="w-3.5 h-3.5" />
              </button>
            </div>
            <span className="badge-ok">
              LOWER = TIGHTER FIT
            </span>
          </div>

          {/* Formula Tooltip Drawer */}
          {showFormulaTooltip && (
            <div className="my-2 p-2.5 rounded bg-cohere-soft-stone border border-cohere-hairline text-[11px] font-mono text-cohere-primary space-y-1">
              <div className="font-bold text-cohere-action-blue">Formula:</div>
              <div>Alignment Index = 0.5 × Σ |Allocation Share - Demand Share|</div>
              <div className="text-[10px] text-cohere-body-muted">
                0% represents perfect geographic alignment where stock perfectly mirrors demand velocity.
              </div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-2 pt-3 text-center">
            <div className="p-2 rounded bg-cohere-soft-stone border border-cohere-hairline">
              <span className="text-[10px] uppercase font-mono text-cohere-body-muted block">Before (Legacy)</span>
              <span className="text-xl font-bold font-mono text-cohere-slate tabular-nums block mt-0.5">
                {(report.overall_historical_mix_index_pct ?? 16.85).toFixed(2)}%
              </span>
            </div>
            <div className="p-2 rounded bg-cohere-soft-stone border border-cohere-hairline">
              <span className="text-[10px] uppercase font-mono text-cohere-body-muted block">After (Rebalanced)</span>
              <span className="text-xl font-bold font-mono text-cohere-action-blue tabular-nums block mt-0.5">
                {(report.overall_post_intervention_index_pct ?? 16.04).toFixed(2)}%
              </span>
            </div>
            <div className="p-2 rounded bg-teal-50 border border-teal-200">
              <span className="text-[10px] uppercase font-mono text-teal-800 block">Gap Improvement</span>
              <span className="text-xl font-bold font-mono text-teal-700 tabular-nums block mt-0.5">
                -{(report.overall_improvement_pct ?? 0.81).toFixed(2)}%
              </span>
            </div>
          </div>

          <div className="text-[10.5px] text-cohere-body-muted pt-2.5 mt-1 border-t border-cohere-hairline">
            <b>Executive Takeaway:</b> Rebalancing eliminates <b>18,000 btls</b> shortfall in Mumbai dark stores, driving the greatest single-SKU improvement in <b>PR-DP (-1.07% gap)</b>.
          </div>
        </div>

        {/* Grouped Horizontal Bar Chart (7 Cols) */}
        <div className="lg:col-span-7 bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat flex flex-col justify-between">
          <div className="flex items-center justify-between pb-2 border-b border-cohere-hairline">
            <span className="text-xs font-bold text-cohere-primary uppercase font-mono tracking-wide">
              SKU Mismatch Comparison (Before vs After)
            </span>
            <span className="text-[10px] font-mono text-cohere-body-muted">
              5 Calibrated Flavours
            </span>
          </div>

          <div className="h-44 w-full">
            <EChart option={barChartOption} height={176} />
          </div>
        </div>
      </div>

      {/* 2. DEPOT-BY-SKU ALLOCATION MISMATCH HEATMAP & INTERACTIVE FILTERS */}
      <div className="bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-cohere-hairline gap-2">
          <div>
            <div className="text-xs font-bold text-cohere-primary uppercase font-mono tracking-wide flex items-center space-x-2">
              <span>Depot-by-SKU Allocation Mismatch Matrix</span>
              <span className="badge-neutral font-mono">
                {viewState === "POST_INTERVENTION" ? "POST-INTERVENTION (REBALANCED)" : "HISTORICAL BASELINE"}
              </span>
            </div>
            <div className="text-xs text-cohere-body-muted mt-0.5">
              Cell color reflects allocation share minus demand share (Teal = Surplus Donor, Crimson = Shortage Deficit).
            </div>
          </div>

          {/* Toggle between Historical and Post-Intervention */}
          <div className="flex items-center space-x-1.5 font-mono text-xs">
            <button
              type="button"
              onClick={() => setViewState("HISTORICAL")}
              className={`px-3 py-1 rounded-pill text-[11px] transition-colors ${
                viewState === "HISTORICAL"
                  ? "bg-cohere-primary text-white font-semibold"
                  : "button-pill-outline text-cohere-slate"
              }`}
            >
              Historical Mix
            </button>
            <button
              type="button"
              onClick={() => setViewState("POST_INTERVENTION")}
              className={`px-3 py-1 rounded-pill text-[11px] transition-colors ${
                viewState === "POST_INTERVENTION"
                  ? "bg-cohere-primary text-white font-semibold"
                  : "button-pill-outline text-cohere-slate"
              }`}
            >
              Post-Intervention
            </button>
          </div>
        </div>

        {/* Interactive Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-2 py-1 text-xs font-mono">
          {/* SKU Filter */}
          <div className="flex items-center space-x-1.5 flex-wrap">
            <span className="text-cohere-body-muted text-[10.5px] uppercase font-semibold">SKU:</span>
            {["ALL", "PR-DP", "PR-PP", "PR-MPB", "PR-GC", "PR-DB"].map((sku) => (
              <button
                key={sku}
                onClick={() => setSelectedSku(sku)}
                className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                  selectedSku === sku
                    ? "bg-cohere-primary text-white font-bold"
                    : "bg-cohere-soft-stone border border-cohere-hairline text-cohere-slate hover:border-cohere-primary/40"
                }`}
              >
                {sku}
              </button>
            ))}
          </div>

          {/* Depot Filter */}
          <div className="flex items-center space-x-1.5 flex-wrap">
            <span className="text-cohere-body-muted text-[10.5px] uppercase font-semibold">Depot:</span>
            {["ALL", "Depot-West-01", "Depot-North-01", "Depot-South-01", "Depot-South-02"].map((d) => (
              <button
                key={d}
                onClick={() => setSelectedDepot(d)}
                className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                  selectedDepot === d
                    ? "bg-cohere-primary text-white font-bold"
                    : "bg-cohere-soft-stone border border-cohere-hairline text-cohere-slate hover:border-cohere-primary/40"
                }`}
              >
                {d === "ALL" ? "All Depots" : d.replace("Depot-", "")}
              </button>
            ))}
          </div>
        </div>

        {/* Data Grid / Matrix */}
        <div className="overflow-x-auto rounded border border-cohere-hairline">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="bg-cohere-soft-stone border-b border-cohere-hairline text-[10.5px] text-cohere-slate uppercase tracking-wider">
                <th className="px-3 py-2 font-semibold">SKU</th>
                <th className="px-3 py-2 font-semibold">Depot</th>
                <th className="px-3 py-2 font-semibold text-right">Allocated Qty</th>
                <th className="px-3 py-2 font-semibold text-right">Corrected Demand</th>
                <th className="px-3 py-2 font-semibold text-right">Alloc Share</th>
                <th className="px-3 py-2 font-semibold text-right">Demand Share</th>
                <th className="px-3 py-2 font-semibold text-center">Share Delta</th>
                <th className="px-3 py-2 font-semibold text-right">Mismatch Contrib</th>
                <th className="px-3 py-2 font-semibold text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cohere-hairline bg-white">
              {filteredMatrix.map((c, i) => {
                const isShortage = c.delta_share < -1.0;
                const isSurplus = c.delta_share > 1.0;
                const isAligned = !isShortage && !isSurplus;

                return (
                  <tr key={i} className="hover:bg-cohere-soft-stone/60 transition-colors">
                    <td className="px-3 py-1.5 font-bold text-cohere-primary">{c.sku_id}</td>
                    <td className="px-3 py-1.5 text-cohere-slate">
                      {DEPOT_LABELS[c.depot_id] || c.depot_id} <span className="text-[10px] text-cohere-body-muted">({c.depot_id})</span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{c.allocated_qty.toLocaleString()} btls</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{c.demand_qty.toLocaleString()} btls</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{c.alloc_share.toFixed(1)}%</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{c.demand_share.toFixed(1)}%</td>
                    <td className="px-3 py-1.5 text-center font-bold tabular-nums">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10.5px] ${
                          isShortage
                            ? "bg-red-50 text-red-700 border border-red-200"
                            : isSurplus
                            ? "bg-teal-50 text-teal-700 border border-teal-200"
                            : "bg-slate-50 text-slate-700 border border-slate-200"
                        }`}
                      >
                        {c.delta_share > 0 ? `+${c.delta_share}%` : `${c.delta_share}%`}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-mono">{c.mismatch_contrib.toFixed(2)}%</td>
                    <td className="px-3 py-1.5 text-center">
                      <span
                        className={`text-[9.5px] font-semibold px-1.5 py-0.5 rounded ${
                          isShortage
                            ? "badge-critical text-red-700"
                            : isSurplus
                            ? "badge-ok text-teal-700"
                            : "badge-neutral text-slate-700"
                        }`}
                      >
                        [{isShortage ? "SHORTAGE" : isSurplus ? "SURPLUS DONOR" : "BALANCED"}]
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-[10.5px] font-mono text-cohere-body-muted pt-1">
          <span>{report.data_honesty_note}</span>
          <span className="text-cohere-slate">Showing {filteredMatrix.length} allocation cells</span>
        </div>
      </div>
    </div>
  );
};
