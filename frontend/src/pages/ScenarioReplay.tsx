import React, { useState, useEffect } from "react";
import { 
  GitCompare, 
  ArrowRight, 
  Clock, 
  CheckCircle, 
  AlertTriangle, 
  TrendingUp, 
  Zap,
  DollarSign,
  ShieldAlert,
  Sliders,
  Layers,
  Sparkles,
  ChevronDown,
  ChevronRight,
  FileText,
  Database
} from "lucide-react";
import { api } from "../api/client";
import { 
  ScenarioData, 
  AllocationAlignmentReport 
} from "../types";
import { EChart } from "../components/EChart";
import { AllocationAlignmentComparison } from "../components/AllocationAlignmentComparison";

export const ScenarioReplay: React.FC = () => {
  const [scenarioId, setScenarioId] = useState<string>("PR_DP_VIRAL_SPIKE");
  const [closureWeeks, setClosureWeeks] = useState<number>(3);
  const [startingCover, setStartingCover] = useState<number>(14);
  const [rationingStrategy, setRationingStrategy] = useState<string>("CONTRIBUTION_OPTIMIZED");
  const [airFreight, setAirFreight] = useState<boolean>(false);

  const [data, setData] = useState<ScenarioData | null>(null);
  const [alignmentReport, setAlignmentReport] = useState<AllocationAlignmentReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isLedgerOpen, setIsLedgerOpen] = useState<boolean>(true);
  const [activeLedgerTab, setActiveLedgerTab] = useState<"RADAR" | "HISTORICAL">("RADAR");

  const loadScenario = async () => {
    try {
      setLoading(true);
      const [res, alignRep] = await Promise.all([
        api.postScenarioReplay({
          scenario_id: scenarioId,
          closure_weeks: closureWeeks,
          starting_cover_days: startingCover,
          rationing_strategy: rationingStrategy,
          air_freight_trigger: airFreight,
        }),
        api.getAlignmentIndex(),
      ]);
      setData(res);
      setAlignmentReport(alignRep);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScenario();
  }, [scenarioId, closureWeeks, startingCover, rationingStrategy, airFreight]);

  // =========================================================================
  // ECHARTS CONFIGURATIONS (Cohere Minimal Monochrome / Semantic Accents)
  // =========================================================================

  // CHART 9: SHORTAGE MITIGATION WATERFALL
  const waterfallOption = React.useMemo(() => {
    if (!data || !data.waterfall) return {};

    const categories = data.waterfall.map(w => w.label);
    const placeholderData: number[] = [];
    const barData: any[] = [];

    let runningTotal = 0;
    data.waterfall.forEach((step, idx) => {
      const val = step.value;
      if (idx === 0) {
        // First bar: Baseline total (Risk Critical Red)
        placeholderData.push(0);
        barData.push({
          value: Math.round(val),
          itemStyle: { color: "#b30000", borderRadius: [3, 3, 0, 0] },
        });
        runningTotal = val;
      } else if (step.type === "relative") {
        // Reductions: Feasible Rebalancing (Deep Teal/Green) and Rationing (Action Blue)
        const absVal = Math.abs(val);
        runningTotal -= absVal;
        placeholderData.push(Math.round(runningTotal));
        barData.push({
          value: Math.round(absVal),
          itemStyle: { color: idx === 1 ? "#003c33" : "#1863dc", borderRadius: [3, 3, 0, 0] },
        });
      } else {
        // Final total (residual unmet demand: Slate / Muted)
        placeholderData.push(0);
        barData.push({
          value: Math.round(runningTotal),
          itemStyle: { color: "#75758a", borderRadius: [3, 3, 0, 0] },
        });
      }
    });

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          const p = params[1] || params[0];
          const orig = data.waterfall[p.dataIndex];
          return `<div style="font-weight:600; color:#ffffff;">${p.name}</div>
                  <div style="font-family:monospace; margin-top:2px; color:#eeece7;">Impact: <b style="color:#ffffff;">${p.value?.toLocaleString()} btls</b></div>
                  <div style="color:#d9d9dd; font-size:10px;">${orig?.annotation || ""}</div>`;
        },
      },
      grid: { top: 30, right: 25, bottom: 40, left: 70 },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: { color: "#616161", fontSize: 10, interval: 0, fontFamily: "Inter, sans-serif" },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "Bottles",
        nameTextStyle: { color: "#616161", fontSize: 9 },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          name: "Placeholder",
          type: "bar",
          stack: "waterfall",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          emphasis: { itemStyle: { color: "transparent" } },
          data: placeholderData,
        },
        {
          name: "Shortage Delta",
          type: "bar",
          stack: "waterfall",
          data: barData,
          label: {
            show: true,
            position: "top",
            formatter: (p: any) => `${Math.round(p.value / 1000)}k`,
            color: "#17171c",
            fontFamily: "JetBrains Mono, monospace",
            fontWeight: 600,
            fontSize: 10,
          },
        },
      ],
    };
  }, [data]);

  // CHART 10: SCENARIO TIMELINE & COVER COMPARISON
  const timelineCoverOption = React.useMemo(() => {
    if (!data || !data.daily_cover_comparison) return {};

    const days = data.daily_cover_comparison.map(d => `Day ${d.day}`);
    const historicalCover = data.daily_cover_comparison.map(d => parseFloat(d.historical_cover_days.toFixed(1)));
    const radarCover = data.daily_cover_comparison.map(d => parseFloat(d.radar_cover_days.toFixed(1)));

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const pt = data.daily_cover_comparison[idx];
          const dateStr = pt?.date || "";
          let s = `<div style="font-weight:600; color:#ffffff; font-family:Inter, sans-serif;">Day ${pt.day} (${dateStr})</div>`;
          params.forEach((p: any) => {
            s += `<div style="color:#eeece7; font-size:11px;">${p.marker} ${p.seriesName}: <b style="color:#ffffff;">${p.value} days</b></div>`;
          });
          const rRow = data.calculation_ledger?.radar_ledger?.[idx];
          const hRow = data.calculation_ledger?.historical_ledger?.[idx];
          if (rRow?.intervention_note) {
            s += `<div style="color:#2dd4bf; font-size:10px; margin-top:3px; font-family:monospace;"><b>[RADAR Action]:</b> ${rRow.intervention_note}</div>`;
          }
          if (hRow?.intervention_note) {
            s += `<div style="color:#f87171; font-size:10px; margin-top:2px; font-family:monospace;"><b>[Historical Action]:</b> ${hRow.intervention_note}</div>`;
          }
          return s;
        },
      },
      legend: {
        data: ["Historical Spreadsheet Policy (Delayed)", "RIOT RADAR S&OP (Early Sensing)"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 35, right: 30, bottom: 35, left: 55 },
      xAxis: {
        type: "category",
        data: days,
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif", interval: "auto", hideOverlap: true },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "Days of Cover",
        nameTextStyle: { color: "#616161", fontSize: 9 },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          name: "Historical Spreadsheet Policy (Delayed)",
          type: "line",
          data: historicalCover,
          smooth: false,
          lineStyle: { color: "#b30000", width: 2 },
          itemStyle: { color: "#b30000" },
          markPoint: {
            data: [
              {
                name: "Planner Notice",
                coord: ["Day 18", historicalCover[17] || 0],
                value: "Notice",
                itemStyle: { color: "#b30000" },
                label: { fontSize: 8.5, color: "#ffffff", fontWeight: 600, formatter: "Day 18 Notice\n(+17d Lag)" },
              },
            ],
          },
        },
        {
          name: "RIOT RADAR S&OP (Early Sensing)",
          type: "line",
          data: radarCover,
          smooth: false,
          lineStyle: { color: "#003c33", width: 2.5 },
          itemStyle: { color: "#003c33" },
          areaStyle: { color: "rgba(0, 60, 51, 0.08)" },
          markPoint: {
            data: [
              {
                name: "Agent Flag",
                coord: ["Day 1", radarCover[0] || 3.3],
                value: "Agent Flag",
                itemStyle: { color: "#1863dc" },
                label: { fontSize: 8.5, color: "#ffffff", fontWeight: 600, formatter: "Day 1 Flag\n(May 20)" },
              },
              {
                name: "Transfer Arrival",
                coord: ["Day 5", radarCover[4] || 1.8],
                value: "Transfer",
                itemStyle: { color: "#003c33" },
                label: { fontSize: 8.5, color: "#ffffff", fontWeight: 600, formatter: "Day 5 Transfer\n(+18k btls)" },
              },
            ],
          },
          markLine: {
            silent: true,
            lineStyle: { type: "dashed", color: "#003c33" },
            data: [{ yAxis: 21, label: { formatter: "21d Target Cover", color: "#003c33" } }],
          },
        },
      ],
    };
  }, [data]);

  // ADDITIONAL CHART: TRANSFER INTERVENTION IMPACT
  const interventionImpactOption = React.useMemo(() => {
    if (!data) return {};

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#17171c",
        borderColor: "#000000",
        textStyle: { color: "#ffffff", fontSize: 11 },
      },
      grid: { top: 20, right: 35, bottom: 25, left: 130 },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
      },
      yAxis: {
        type: "category",
        data: ["Shortage Mitigated", "Total Baseline Gap"],
        axisLabel: { color: "#17171c", fontSize: 11, fontFamily: "Inter, sans-serif", fontWeight: 500 },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      series: [
        {
          type: "bar",
          data: [
            { value: data.kpis.shortage_reduction_bottles, itemStyle: { color: "#003c33", borderRadius: [0, 3, 3, 0] } },
            { value: data.waterfall[0]?.value || 840000, itemStyle: { color: "#b30000", borderRadius: [0, 3, 3, 0] } },
          ],
          label: {
            show: true,
            position: "right",
            formatter: (p: any) => `${Math.round(p.value / 1000).toLocaleString()}k btls`,
            color: "#17171c",
            fontFamily: "JetBrains Mono, monospace",
            fontWeight: 600,
            fontSize: 10,
          },
        },
      ],
    };
  }, [data]);

  // ALLOCATION ALIGNMENT BEFORE VS AFTER INTERVENTION
  const scenarioAlignmentOption = React.useMemo(() => {
    if (!alignmentReport || !alignmentReport.sku_alignment_indices) return {};

    const items = [...alignmentReport.sku_alignment_indices].reverse();
    const categories = items.map(s => `${s.sku_id} (${s.flavour})`);
    const beforeData = items.map(s => s.historical_mix_index_pct);
    const afterData = items.map(s => ({
      value: s.post_intervention_index_pct,
      itemStyle: {
        color: "#1863dc",
        borderRadius: [0, 3, 3, 0],
      },
    }));

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const skuItem = items[idx];
          if (!skuItem) return "";

          return `<div style="font-weight:600; color:#ffffff; font-family:monospace; margin-bottom:4px;">
            ${skuItem.sku_id} — ${skuItem.flavour}
          </div>
          <div style="color:#d9d9dd; font-size:11px;">Before Intervention (Historical Mix): <b style="color:#ff7759">${skuItem.historical_mix_index_pct}%</b></div>
          <div style="color:#d9d9dd; font-size:11px;">After Intervention (Rebalanced): <b style="color:#1863dc">${skuItem.post_intervention_index_pct}%</b></div>
          <div style="color:#003c33; font-size:11px; margin-top:2px;">Mismatch Reduction: <b>-${skuItem.improvement_pct}%</b></div>
          <div style="font-size:10px; color:#8c8c99; margin-top:4px; font-style:italic;">Evaluated using identical demand assumptions.</div>`;
        },
      },
      legend: {
        data: ["Before Intervention (Baseline Mismatch)", "After Intervention (Rebalanced)"],
        textStyle: { color: "#616161", fontSize: 11, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { left: "26%", right: "8%", top: "14%", bottom: "6%" },
      xAxis: {
        type: "value",
        axisLabel: { formatter: "{value}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        max: (val: any) => Math.max(35, Math.ceil(val.max / 5) * 5),
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLabel: { color: "#17171c", fontSize: 11, fontFamily: "Inter, sans-serif", fontWeight: 500 },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      series: [
        {
          name: "Before Intervention (Baseline Mismatch)",
          type: "bar",
          data: beforeData,
          barGap: "20%",
          itemStyle: { color: "#94a3b8", borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: "right", formatter: "{c}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
        {
          name: "After Intervention (Rebalanced)",
          type: "bar",
          data: afterData,
          itemStyle: { color: "#1863dc", borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: "right", formatter: "{c}%", color: "#17171c", fontWeight: 600, fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
      ],
    };
  }, [alignmentReport]);

  return (
    <div className="space-y-5 pb-8">
      {/* 1. TOP HEADER & SCENARIO SELECTOR */}
      <section className="space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-cohere-hairline pb-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-cohere-primary">
              Disruption Scenario Simulation Engine
            </h1>
            <p className="text-xs text-cohere-body-muted mt-0.5">
              Compare baseline spreadsheet delays against RIOT RADAR early demand sensing, rebalancing, and pulp rationing.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setScenarioId("PR_DP_VIRAL_SPIKE")}
              className={`px-4 py-1.5 rounded-pill text-xs font-mono font-medium transition-all ${
                scenarioId === "PR_DP_VIRAL_SPIKE"
                  ? "button-primary"
                  : "button-pill-outline"
              }`}
            >
              Dragon Passion demand spike
            </button>
            <button
              onClick={() => setScenarioId("PASSIONFRUIT_HIGHWAY_CLOSURE")}
              className={`px-4 py-1.5 rounded-pill text-xs font-mono font-medium transition-all ${
                scenarioId === "PASSIONFRUIT_HIGHWAY_CLOSURE"
                  ? "button-primary"
                  : "button-pill-outline"
              }`}
            >
              Passionfruit road closure
            </button>
          </div>
        </div>
      </section>

      {/* 2. FOUR SCENARIO KPIS */}
      {data && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat">
            <div className="text-[11px] font-mono tracking-wider uppercase text-cohere-body-muted">
              Detection Advantage
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-action-blue mt-1.5">
              +{data.kpis.detection_advantage_days} Days
            </div>
            <div className="text-xs text-cohere-body-muted mt-1">Day 3 (AI Flag) vs Day 20 (Spreadsheets)</div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat">
            <div className="text-[11px] font-mono tracking-wider uppercase text-cohere-body-muted">
              Shortage Reduction
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-teal-700 mt-1.5">
              {data.kpis.shortage_reduction_bottles.toLocaleString()} <span className="text-xs font-normal text-cohere-body-muted">btls</span>
            </div>
            <div className="text-xs text-teal-700 mt-1 font-mono">Customer Volume Protected</div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat">
            <div className="text-[11px] font-mono tracking-wider uppercase text-cohere-body-muted">
              Rebalancing Coverage %
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-primary mt-1.5">
              {data.kpis.rebalancing_coverage_pct}%
            </div>
            <div className="text-xs text-cohere-body-muted mt-1">Mitigated via Surplus Transfers</div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-sm p-4 shadow-card-flat">
            <div className="text-[11px] font-mono tracking-wider uppercase text-cohere-body-muted">
              Net Mitigation Cost
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-primary mt-1.5">
              ₹{data.kpis.net_mitigation_cost_inr >= 10000000 
                ? `${(data.kpis.net_mitigation_cost_inr / 10000000).toFixed(2)} Cr` 
                : Math.round(data.kpis.net_mitigation_cost_inr).toLocaleString()}
            </div>
            <div className="text-xs text-cohere-body-muted mt-1">
              {data.kpis.net_mitigation_cost_inr >= 10000000 ? "Emergency Air Freight Mode" : "Inter-Depot Freight (@ ₹1.50/btl)"}
            </div>
          </div>
        </section>
      )}

      {/* 3. CHARTS ROW: WATERFALL (CHART 9) & TIMELINE (CHART 10) */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* CHART 9: SHORTAGE MITIGATION WATERFALL */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Chart 9 — Shortage Mitigation Waterfall (Feasible Levers)
              </div>
              <div className="text-xs text-cohere-body-muted mt-0.5">
                Decomposing baseline shortage reduction across feasible transfers and rationing.
              </div>
            </div>
            <span className="badge-ok">
              FEASIBLE ONLY
            </span>
          </div>

          <div className="h-80 w-full">
            <EChart
              option={waterfallOption}
              height={320}
              loading={loading}
            />
          </div>
          <div className="text-[11px] text-cohere-body-muted border-t border-cohere-hairline pt-2 flex items-center justify-between">
            <span>SCM Guardrail: Co-packer bottling lines cannot solve raw pulp unavailability when roads are closed.</span>
            <span className="font-mono text-cohere-body-muted">[CONSTRAINT ENFORCED]</span>
          </div>
        </div>

        {/* CHART 10: SCENARIO TIMELINE & COVER COMPARISON */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Chart 10 — Inventory Cover Trajectory (21 Days Horizon)
              </div>
              <div className="text-xs text-cohere-body-muted mt-0.5">
                Historical delayed baseline (Red) vs. RIOT RADAR proactive rebalancing (Green).
              </div>
            </div>
            <span className="font-mono text-xs text-cohere-slate">
              +17 Days Advantage
            </span>
          </div>

          <div className="h-80 w-full">
            <EChart
              option={timelineCoverOption}
              height={320}
              loading={loading}
            />
          </div>

          {/* Timeline Event Strip with Case Fact vs Demo Calibration distinctions */}
          {data && (
            <div className="space-y-2">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 p-3 rounded-sm bg-cohere-soft-stone border border-cohere-hairline text-xs font-mono">
                <div>
                  <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">1. First QC Signal:</span>
                  <div className="text-cohere-primary font-medium">{data.timeline_events.first_signal_date}</div>
                  <span className="text-[9px] text-emerald-700 font-semibold">[Observed POS]</span>
                </div>
                <div>
                  <span className="text-cohere-action-blue block text-[10px] uppercase font-semibold">2. RADAR Flag:</span>
                  <div className="text-cohere-action-blue font-semibold">{data.timeline_events.agent_flag_date}</div>
                  <span className="text-[9px] text-blue-700 font-semibold">[Snapshot Date]</span>
                </div>
                <div>
                  <span className="text-cohere-primary block text-[10px] uppercase font-semibold">3. Human Approval:</span>
                  <div className="text-cohere-primary font-medium">{data.timeline_events.human_approval_date}</div>
                  <span className="text-[9px] text-slate-600 font-semibold">[+24h Governance]</span>
                </div>
                <div>
                  <span className="text-teal-700 block text-[10px] uppercase font-semibold">4. Transfer Arrival:</span>
                  <div className="text-teal-700 font-semibold">{data.timeline_events.transfer_arrival_date}</div>
                  <span className="text-[9px] text-teal-700 font-semibold">[3d Transit + 1d ETA]</span>
                </div>
                <div>
                  <span className="text-cohere-error block text-[10px] uppercase font-semibold">5. Planner Notice:</span>
                  <div className="text-cohere-error font-semibold">{data.timeline_events.historical_planner_notice_date}</div>
                  <span className="text-[9px] text-red-700 font-semibold">[+17d Legacy S&OP]</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center justify-between text-[10.5px] font-mono text-cohere-body-muted bg-white p-2 rounded-sm border border-cohere-hairline">
                <div>
                  <span className="font-semibold text-cohere-primary">[CASE FACT]:</span> 4.1x Quick Commerce velocity surge; 17-day spreadsheet notice lag; ₹60/btl price; 32% margin; ₹1.50/btl transfer.
                </div>
                <div>
                  <span className="font-semibold text-cohere-primary">[DEMO CALIBRATION]:</span> Evaluated across 21 days starting May 20, 2026 snapshot.
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 3B. AUDITED DAILY INVENTORY RECONCILIATION & COVER LEDGER (COLLAPSIBLE PANEL) */}
      {data && data.calculation_ledger && (
        <section className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-4 shadow-card-flat">
          <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-cohere-hairline pb-3 gap-3">
            <div>
              <div className="flex items-center space-x-2">
                <Database className="w-4 h-4 text-cohere-action-blue" />
                <span className="text-xs font-bold text-cohere-primary tracking-wide uppercase font-mono">
                  Daily Inventory Reconciliation &amp; Cover Ledger
                </span>
                <span className="badge-ok font-mono text-[9.5px]">BOTTLE-EXACT AUDIT</span>
              </div>
              <div className="text-xs text-cohere-body-muted mt-0.5">
                Reconstructs inventory starting from audited May 20 opening balance (83,150 btls). Formula: Opening + Receipts + Transfers - Fulfilled Demand = Closing Stock.
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <div className="flex rounded-sm bg-cohere-soft-stone p-0.5 border border-cohere-hairline text-[11px] font-mono">
                <button
                  onClick={() => setActiveLedgerTab("RADAR")}
                  className={`px-3 py-1 rounded-sm transition-colors ${
                    activeLedgerTab === "RADAR"
                      ? "bg-white text-teal-800 font-bold shadow-sm"
                      : "text-cohere-body-muted hover:text-cohere-primary"
                  }`}
                >
                  RIOT RADAR S&amp;OP
                </button>
                <button
                  onClick={() => setActiveLedgerTab("HISTORICAL")}
                  className={`px-3 py-1 rounded-sm transition-colors ${
                    activeLedgerTab === "HISTORICAL"
                      ? "bg-white text-cohere-error font-bold shadow-sm"
                      : "text-cohere-body-muted hover:text-cohere-primary"
                  }`}
                >
                  Historical Delayed
                </button>
              </div>

              <button
                onClick={() => setIsLedgerOpen(!isLedgerOpen)}
                className="flex items-center space-x-1 px-2.5 py-1 text-xs font-mono bg-white border border-cohere-hairline rounded-sm hover:bg-cohere-soft-stone text-cohere-primary"
                title="Toggle Audit Ledger Visibility"
              >
                <span>{isLedgerOpen ? "Hide Ledger" : "View Ledger"}</span>
                {isLedgerOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {isLedgerOpen && (
            <div className="space-y-4">
              {/* Summary Metric Ribbon */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 p-3 bg-cohere-soft-stone/70 border border-cohere-hairline rounded-sm font-mono text-xs">
                <div>
                  <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Opening Usable Stock:</span>
                  <div className="text-cohere-primary font-bold text-sm">
                    {data.calculation_ledger.summary.opening_stock_bottles.toLocaleString()} btls
                  </div>
                  <span className="text-[9.5px] text-emerald-700 font-semibold">[Observed Snapshot 2026-05-20]</span>
                </div>
                <div>
                  <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Stock-out Occurrence:</span>
                  <div className={activeLedgerTab === "HISTORICAL" ? "text-cohere-error font-bold text-sm" : "text-teal-700 font-bold text-sm"}>
                    {activeLedgerTab === "HISTORICAL" 
                      ? (data.calculation_ledger.summary.historical_projected_stockout_date || "2026-05-25 (Day 6)")
                      : "Protected / Averted"}
                  </div>
                  <span className="text-[9.5px] text-cohere-body-muted">
                    {activeLedgerTab === "HISTORICAL" ? "[Calculated Depletion]" : "[Transfers Restocked Depot]"}
                  </span>
                </div>
                <div>
                  <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">21d Cumulative Unmet Demand:</span>
                  <div className="text-cohere-primary font-bold text-sm">
                    {activeLedgerTab === "HISTORICAL"
                      ? `${data.calculation_ledger.summary.historical_total_unmet_demand_bottles.toLocaleString()} btls`
                      : `${data.calculation_ledger.summary.radar_total_unmet_demand_bottles.toLocaleString()} btls`}
                  </div>
                  <span className="text-[9.5px] text-cohere-body-muted">
                    {activeLedgerTab === "HISTORICAL" ? "Unmitigated stockout gap" : "Reduced via early transfers"}
                  </span>
                </div>
                <div>
                  <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Protected Contribution:</span>
                  <div className="text-teal-700 font-bold text-sm">
                    ₹{(data.calculation_ledger.summary.protected_contribution_inr / 100000).toFixed(2)} Lakh
                  </div>
                  <span className="text-[9.5px] text-teal-700 font-semibold">₹19.20/btl (32% Margin)</span>
                </div>
                <div>
                  <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Net Mitigation Cost:</span>
                  <div className="text-cohere-primary font-bold text-sm">
                    ₹{(data.calculation_ledger.summary.mitigation_cost_inr / 1000).toLocaleString()} (@ ₹1.50/btl)
                  </div>
                  <span className="text-[9.5px] text-cohere-action-blue font-semibold">
                    ROI: {(data.calculation_ledger.summary.protected_contribution_inr / (data.calculation_ledger.summary.mitigation_cost_inr || 1)).toFixed(1)}x
                  </span>
                </div>
              </div>

              {/* Data Table */}
              <div className="overflow-x-auto border border-cohere-hairline rounded-sm">
                <table className="w-full text-left font-mono text-[11px] border-collapse">
                  <thead>
                    <tr className="bg-cohere-soft-stone border-b border-cohere-hairline text-[10px] text-cohere-body-muted uppercase tracking-wider">
                      <th className="py-2.5 px-3 font-semibold">Day &amp; Date</th>
                      <th className="py-2.5 px-2.5 font-semibold">Classification</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Opening</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Inbounds</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Transfers</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Available</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Daily Demand</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Fulfilled</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Unmet</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Closing</th>
                      <th className="py-2.5 px-2.5 font-semibold text-right">Cover (DoC)</th>
                      <th className="py-2.5 px-3 font-semibold">Supply Intervention &amp; Source Document</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cohere-hairline">
                    {(activeLedgerTab === "RADAR" 
                      ? data.calculation_ledger.radar_ledger 
                      : data.calculation_ledger.historical_ledger
                    ).map((row) => {
                      const isStockout = row.is_stocked_out || (row.closing_stock === 0 && row.unmet_demand > 0);
                      const hasIntervention = Boolean(row.intervention_note);

                      return (
                        <tr 
                          key={row.day} 
                          className={`hover:bg-cohere-soft-stone/40 transition-colors ${
                            isStockout ? "bg-red-50/40" : hasIntervention ? "bg-emerald-50/20" : ""
                          }`}
                        >
                          <td className="py-2 px-3 font-semibold text-cohere-primary whitespace-nowrap">
                            Day {row.day} <span className="text-cohere-body-muted font-normal">({row.date})</span>
                          </td>
                          <td className="py-2 px-2.5 whitespace-nowrap">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-pill font-semibold border ${
                              row.data_type === "Observed"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : row.data_type === "Simulated"
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-slate-100 text-slate-700 border-slate-200"
                            }`}>
                              [{row.data_type}]
                            </span>
                          </td>
                          <td className="py-2 px-2.5 text-right font-medium text-cohere-primary tabular-nums">
                            {row.opening_stock.toLocaleString()}
                          </td>
                          <td className="py-2 px-2.5 text-right tabular-nums">
                            {row.inbound_receipt_qty > 0 ? (
                              <span className="font-semibold text-emerald-700">+{row.inbound_receipt_qty.toLocaleString()}</span>
                            ) : (
                              <span className="text-cohere-hairline">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2.5 text-right tabular-nums">
                            {row.transfer_in_qty > 0 ? (
                              <span className="font-semibold text-cohere-action-blue">+{row.transfer_in_qty.toLocaleString()}</span>
                            ) : (
                              <span className="text-cohere-hairline">—</span>
                            )}
                          </td>
                          <td className="py-2 px-2.5 text-right font-semibold text-cohere-primary tabular-nums">
                            {row.available_usable_stock.toLocaleString()}
                          </td>
                          <td className="py-2 px-2.5 text-right text-cohere-primary tabular-nums">
                            {row.daily_demand.toLocaleString()}
                          </td>
                          <td className="py-2 px-2.5 text-right text-teal-800 tabular-nums">
                            {row.fulfilled_demand.toLocaleString()}
                          </td>
                          <td className="py-2 px-2.5 text-right tabular-nums">
                            {row.unmet_demand > 0 ? (
                              <span className="font-bold text-cohere-error">+{row.unmet_demand.toLocaleString()}</span>
                            ) : (
                              <span className="text-cohere-hairline">0</span>
                            )}
                          </td>
                          <td className="py-2 px-2.5 text-right font-bold tabular-nums">
                            {row.closing_stock === 0 ? (
                              <span className="text-cohere-error">0 [STOCK-OUT]</span>
                            ) : (
                              <span className="text-cohere-primary">{row.closing_stock.toLocaleString()}</span>
                            )}
                          </td>
                          <td className="py-2 px-2.5 text-right font-bold tabular-nums">
                            <span className={row.days_of_cover < 1.0 ? "text-cohere-error" : row.days_of_cover < 3.0 ? "text-amber-700" : "text-teal-700"}>
                              {row.days_of_cover.toFixed(1)}d
                            </span>
                          </td>
                          <td className="py-2 px-3 text-xs text-cohere-primary max-w-xs">
                            {row.intervention_note ? (
                              <div className="text-emerald-800 font-medium text-[10.5px]">
                                {row.intervention_note}
                              </div>
                            ) : (
                              <span className="text-cohere-body-muted text-[10px]">{row.source_record}</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="text-[10.5px] font-mono text-cohere-body-muted p-2 bg-cohere-soft-stone/50 border border-cohere-hairline rounded-sm">
                <b>Reconciliation Integrity Audit:</b> For every single row day t: Closing Stock = Opening Stock + Inbound Receipts + Transfers In - Fulfilled Demand. Fulfilled demand is strictly capped at available usable stock (Fulfilled &le; Available). Any demand in excess of available stock is recorded as Unmet Demand.
              </div>
            </div>
          )}
        </section>
      )}

      {/* 4. ALLOCATION-VS-DEMAND ALIGNMENT COMPARISON (POWER BI STYLE) */}
      <section className="space-y-2">
        <div className="flex items-center justify-between pb-1">
          <div>
            <div className="text-xs font-bold text-cohere-primary uppercase font-mono tracking-wide">
              Allocation-vs-Demand Alignment Analytics
            </div>
            <div className="text-xs text-cohere-body-muted mt-0.5">
              Comparative analysis of static quota allocations against demand-sensing corrected run-rates.
            </div>
          </div>
        </div>

        <AllocationAlignmentComparison report={alignmentReport} loading={loading} />
      </section>


      {/* 6. MITIGATION EFFECTIVENESS CHART */}
      <section className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-2 shadow-card-flat">
        <div className="border-b border-cohere-hairline pb-2.5 flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
              Mitigation Effectiveness vs Baseline
            </div>
            <div className="text-xs text-cohere-body-muted mt-0.5">Volume rescued via early sensing &amp; feasible transfers</div>
          </div>
          <span className="badge-ok">
            73.8% COVERED
          </span>
        </div>
        <div className="h-56 w-full">
          <EChart option={interventionImpactOption} height={220} />
        </div>
      </section>

      {/* 5. INTERACTIVE SCENARIO CONTROLS (SCENARIO B ONLY) */}
      {scenarioId === "PASSIONFRUIT_HIGHWAY_CLOSURE" && (
        <section className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-4 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
            <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono flex items-center space-x-1.5">
              <Sliders className="w-3.5 h-3.5 text-cohere-action-blue" />
              <span>Interactive Levers — Northeast Highway Outage</span>
            </div>
            <span className="badge-ok">
              REAL-TIME SIMULATION
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="block text-[10px] font-mono text-cohere-body-muted uppercase font-semibold mb-1">
                Outage Duration (Weeks):
              </label>
              <input
                type="range"
                min="1"
                max="6"
                value={closureWeeks}
                onChange={(e) => setClosureWeeks(parseInt(e.target.value))}
                className="w-full accent-cohere-action-blue cursor-pointer h-1.5 bg-cohere-soft-stone rounded"
              />
              <div className="font-mono text-right text-cohere-primary font-semibold text-xs mt-1">{closureWeeks} Weeks</div>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-cohere-body-muted uppercase font-semibold mb-1">
                Starting Factory Pulp Cover (Days):
              </label>
              <input
                type="range"
                min="7"
                max="28"
                value={startingCover}
                onChange={(e) => setStartingCover(parseInt(e.target.value))}
                className="w-full accent-cohere-action-blue cursor-pointer h-1.5 bg-cohere-soft-stone rounded"
              />
              <div className="font-mono text-right text-cohere-primary font-semibold text-xs mt-1">{startingCover} Days Cover</div>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-cohere-body-muted uppercase font-semibold mb-1">
                Pulp Rationing Recipe:
              </label>
              <select
                value={rationingStrategy}
                onChange={(e) => setRationingStrategy(e.target.value)}
                className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-sm px-3 py-2 text-xs text-cohere-primary font-mono focus:outline-none focus:border-cohere-action-blue cursor-pointer"
              >
                <option value="CONTRIBUTION_OPTIMIZED">Protect PR-DP (₹548.57/kg pulp)</option>
                <option value="PRO_RATA">Pro-Rata (-30% Across All)</option>
                <option value="HISTORICAL_UNGOVERNED">Ungoverned (First-Come First-Served)</option>
              </select>
            </div>

            <div className="flex flex-col justify-between">
              <label className="block text-[10px] font-mono text-cohere-body-muted uppercase font-semibold mb-1">
                Emergency Air Freight Lever:
              </label>
              <button
                onClick={() => setAirFreight(!airFreight)}
                className={`py-2 px-3 rounded-pill font-mono font-medium text-xs transition-colors ${
                  airFreight 
                    ? "bg-red-50 border border-cohere-error text-cohere-error font-semibold" 
                    : "button-pill-outline"
                }`}
              >
                {airFreight ? "[EMERGENCY AIR CHARTER ACTIVE]" : "[ACTIVATE AIR FREIGHT]"}
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};
