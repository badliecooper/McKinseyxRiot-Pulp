import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { 
  MapPin, 
  Layers, 
  Calendar, 
  ArrowRight, 
  Send, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  Truck,
  TrendingUp,
  ShieldCheck,
  ShieldAlert,
  Info,
  Check,
  X,
  Edit2
} from "lucide-react";
import { api } from "../api/client";
import { 
  SkuDepotItem, 
  DemandSeriesPoint, 
  InventoryProjectionPoint, 
  RebalancingProposal,
  AllocationAlignmentReport,
  SkuAlignmentIndex
} from "../types";
import { EChart } from "../components/EChart";

export const DepotExplorer: React.FC = () => {
  const [searchParams] = useSearchParams();
  const initialDepot = searchParams.get("depot") || "Depot-West-01";
  const initialSku = searchParams.get("sku") || "PR-DP";

  const [depots, setDepots] = useState<any[]>([]);
  const [skus, setSkus] = useState<any[]>([]);
  const [selectedDepot, setSelectedDepot] = useState<string>(initialDepot);
  const [selectedSku, setSelectedSku] = useState<string>(initialSku);

  const [detail, setDetail] = useState<SkuDepotItem | null>(null);
  const [demandSeries, setDemandSeries] = useState<DemandSeriesPoint[]>([]);
  const [projection, setProjection] = useState<any>(null);
  const [proposals, setProposals] = useState<RebalancingProposal[]>([]);
  const [alignmentReport, setAlignmentReport] = useState<AllocationAlignmentReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Manual stockout report form state
  const [channel, setChannel] = useState<string>("Quick Commerce");
  const [unmetBottles, setUnmetBottles] = useState<number>(15000);
  const [reporter, setReporter] = useState<string>("Store Operations Lead");
  const [evidence, setEvidence] = useState<string>("Blinkit/Zepto partner dark store stockout logs");
  const [notes, setNotes] = useState<string>("Zero inventory across 14 dark stores during peak velocity surge.");
  const [reportSuccess, setReportSuccess] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<string>("FULL_SUMMER");

  // Modify proposal modal state
  const [modifyingProposal, setModifyingProposal] = useState<RebalancingProposal | null>(null);
  const [modifiedQty, setModifiedQty] = useState<number>(0);

  const loadData = async (activeTf = timeframe) => {
    try {
      setLoading(true);
      const [depList, skuList, dDetail, dSeries, dProj, dTrans, dAlign] = await Promise.all([
        api.getDepots(),
        api.getSkus(),
        api.getSkuDepotDetail(selectedSku, selectedDepot),
        api.getDemandSeries(selectedSku, selectedDepot, undefined, activeTf),
        api.getInventoryProjection(selectedSku, selectedDepot, 42),
        api.getTransfers(selectedSku, selectedDepot),
        api.getAlignmentIndex(),
      ]);

      setDepots(depList);
      setSkus(skuList);
      setDetail(dDetail);
      setDemandSeries(dSeries.series);
      setProjection(dProj);
      setProposals(dTrans.proposals);
      setAlignmentReport(dAlign);
    } catch (e: any) {
      console.error("Failed to load depot explorer:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(timeframe);
  }, [selectedDepot, selectedSku, timeframe]);

  const handleDecision = async (recId: string, decision: "APPROVE" | "MODIFY" | "REJECT", modQty?: number) => {
    try {
      const res = await api.postApprovalDecision(recId, decision, "Depot-Planner-UI", modQty);
      setActionMessage(res.summary_message);
      // Reload proposals and detail
      const [dDetail, dTrans] = await Promise.all([
        api.getSkuDepotDetail(selectedSku, selectedDepot),
        api.getTransfers(selectedSku, selectedDepot),
      ]);
      setDetail(dDetail);
      setProposals(dTrans.proposals);
    } catch (e: any) {
      alert("Decision failed: " + e.message);
    }
  };

  const handleSubmitStockout = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.postStockoutReport({
        depot_id: selectedDepot,
        sku_id: selectedSku,
        channel,
        estimated_unmet_bottles: unmetBottles,
        reported_by: reporter,
        evidence_source: evidence,
        notes,
      });
      setReportSuccess(`Logged: ${res.report_id} — Field telemetry saved to stockout_reports.csv.`);
      loadData();
    } catch (err: any) {
      alert("Error reporting stockout: " + err.message);
    }
  };

  // =========================================================================
  // ECHARTS CONFIGURATIONS
  // =========================================================================

  // CHART 7: DEMAND SENSING VS FORECAST
  const demandSensingOption = React.useMemo(() => {
    if (!demandSeries || demandSeries.length === 0) return {};

    const dates = demandSeries.map(d => d.date.slice(5));
    const observed = demandSeries.map(d => Math.round(d.observed_sales));
    const forecast = demandSeries.map(d => Math.round(d.forecast_demand));
    const corrected = demandSeries.map(d => Math.round(d.corrected_demand));

    // Identify stockout flagged windows
    const markAreaData: any[] = [];
    let startIdx: number | null = null;
    demandSeries.forEach((pt, idx) => {
      if (pt.is_stockout_flagged && startIdx === null) {
        startIdx = idx;
      } else if (!pt.is_stockout_flagged && startIdx !== null) {
        markAreaData.push([{ xAxis: dates[startIdx] }, { xAxis: dates[idx - 1] }]);
        startIdx = null;
      }
    });
    if (startIdx !== null) {
      markAreaData.push([{ xAxis: dates[startIdx] }, { xAxis: dates[dates.length - 1] }]);
    }

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          let s = `<div style="font-weight:600; color:#ffffff;">Date: ${params[0].name}</div>`;
          params.forEach((p: any) => {
            s += `<div style="color:#eeece7;">${p.marker} ${p.seriesName}: <b style="color:#ffffff;">${p.value?.toLocaleString()} btls</b></div>`;
          });
          const original = demandSeries.find(d => d.date.endsWith(params[0].name));
          if (original?.is_stockout_flagged) {
            s += `<div style="color:#ffad9b; font-weight:600; margin-top:3px; font-family:monospace;">[STOCK-OUT CENSORED WINDOW]</div>`;
          }
          return s;
        },
      },
      legend: {
        data: ["Observed Sales", "Saved Forecast Vintage", "Corrected Latent Demand"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 35, right: 25, bottom: 35, left: 60 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif", interval: "auto", hideOverlap: true },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "Bottles / Day",
        nameTextStyle: { color: "#75758a", fontSize: 9 },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          name: "Observed Sales",
          type: "line",
          data: observed,
          smooth: true,
          lineStyle: { color: "#75758a", width: 2 },
          itemStyle: { color: "#75758a" },
        },
        {
          name: "Saved Forecast Vintage",
          type: "line",
          data: forecast,
          smooth: true,
          lineStyle: { color: "#1863dc", width: 2, type: "dashed" },
          itemStyle: { color: "#1863dc" },
        },
        {
          name: "Corrected Latent Demand",
          type: "line",
          data: corrected,
          smooth: true,
          lineStyle: { color: "#003c33", width: 2.5 },
          itemStyle: { color: "#003c33" },
          areaStyle: {
            color: "rgba(0, 60, 51, 0.08)",
          },
          markArea: {
            silent: true,
            itemStyle: { color: "rgba(179, 0, 0, 0.12)" },
            data: markAreaData,
          },
        },
      ],
    };
  }, [demandSeries]);

  // CHART 8: PROJECTED INVENTORY DEPLETION SAWTOOTH
  const inventorySawtoothOption = React.useMemo(() => {
    if (!projection || !projection.timeline || projection.timeline.length === 0) return {};

    const chartTimeline = projection.timeline.slice(0, 21);
    const dates = chartTimeline.map((t: any) => t.date.slice(5));
    const closingStock = chartTimeline.map((t: any) => Math.round(t.closing_stock));
    const inbounds = chartTimeline.map((t: any) => Math.round(t.inbound_receipt_qty));
    const transfers = chartTimeline.map((t: any) => Math.round(t.transfer_in_qty || 0));
    const targetStock = projection.target_stock || 0;

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
          const target = chartTimeline.find((t: any) => t.date.endsWith(params[0].name));
          let s = `<div style="font-weight:600; color:#ffffff; font-family:Inter, sans-serif;">Date: ${target?.date || params[0].name}</div>`;
          if (target) {
            s += `<div style="color:#eeece7; font-size:10.5px;">Opening Stock: <b style="color:#ffffff;">${target.opening_stock.toLocaleString()} btls</b></div>`;
            if (target.inbound_receipt_qty > 0) {
              s += `<div style="color:#2dd4bf; font-size:10.5px;">Inbound Receipts: <b style="color:#2dd4bf;">+${target.inbound_receipt_qty.toLocaleString()} btls</b></div>`;
            }
            if (target.transfer_in_qty > 0) {
              s += `<div style="color:#60a5fa; font-size:10.5px;">Transfers In: <b style="color:#60a5fa;">+${target.transfer_in_qty.toLocaleString()} btls</b></div>`;
            }
            s += `<div style="color:#eeece7; font-size:10.5px;">Daily Demand Burn: <b style="color:#f87171;">-${target.daily_demand_burn.toLocaleString()} btls</b></div>`;
            s += `<div style="color:#eeece7; font-size:10.5px;">Fulfilled Demand: <b style="color:#2dd4bf;">${(target.fulfilled_demand ?? target.daily_demand_burn).toLocaleString()} btls</b></div>`;
            if (target.unmet_demand > 0) {
              s += `<div style="color:#ffad9b; font-size:10.5px; font-weight:bold;">Unmet Demand: +${target.unmet_demand.toLocaleString()} btls</div>`;
            }
            s += `<div style="color:#eeece7; font-size:10.5px; border-top:1px solid #333; margin-top:2px; padding-top:2px;">Usable Closing Stock: <b style="color:#ffffff;">${target.closing_stock.toLocaleString()} btls</b> (${(target.days_of_cover ?? 0).toFixed(1)}d cover)</div>`;
            if (target.intervention_note) {
              s += `<div style="color:#67e8f9; font-size:10px; margin-top:3px; font-family:monospace;"><b>[Intervention]:</b> ${target.intervention_note}</div>`;
            }
            if (target.is_stocked_out || (target.closing_stock === 0 && target.unmet_demand > 0)) {
              s += `<div style="color:#ffad9b; font-weight:600; margin-top:3px; font-family:monospace;">[PROJECTED STOCKOUT]</div>`;
            }
          }
          return s;
        },
      },
      legend: {
        data: ["Usable Closing Stock", "Inbound Receipts (+Qty)", "Transfers In (+Qty)"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 35, right: 25, bottom: 35, left: 65 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif", interval: "auto", hideOverlap: true },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "Usable Stock (Btls)",
        nameTextStyle: { color: "#75758a", fontSize: 9 },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          name: "Inbound Receipts (+Qty)",
          type: "bar",
          data: inbounds,
          itemStyle: { color: "#003c33", borderRadius: [2, 2, 0, 0] },
          barWidth: 7,
        },
        {
          name: "Transfers In (+Qty)",
          type: "bar",
          data: transfers,
          itemStyle: { color: "#1863dc", borderRadius: [2, 2, 0, 0] },
          barWidth: 7,
        },
        {
          name: "Usable Closing Stock",
          type: "line",
          data: closingStock,
          smooth: false,
          lineStyle: { color: "#1863dc", width: 2 },
          itemStyle: { color: "#1863dc" },
          areaStyle: {
            color: "rgba(24, 99, 220, 0.08)",
          },
          markLine: {
            silent: true,
            lineStyle: { type: "dashed", width: 1.5 },
            data: [
              {
                yAxis: targetStock,
                lineStyle: { color: "#003c33" },
                label: { formatter: `21d Target: ${Math.round(targetStock/1000)}k`, color: "#003c33", position: "end" },
              },
              {
                yAxis: 0,
                lineStyle: { color: "#b30000" },
                label: { formatter: "Stock-out (0 btls)", color: "#b30000", position: "end" },
              },
            ],
          },
        },
      ],
    };
  }, [projection]);

  // ADDITIONAL CHART: DEMAND VS SUPPLY TREND
  const demandVsSupplyOption = React.useMemo(() => {
    if (!demandSeries || demandSeries.length === 0 || !projection) return {};

    const SNAPSHOT_DATE = "2026-05-20";
    const projMap = new Map<string, any>();
    if (projection.timeline) {
      projection.timeline.forEach((p: any) => {
        projMap.set(p.date, p);
      });
    }

    const dates = demandSeries.map(d => d.date.slice(5));
    const fullDates = demandSeries.map(d => d.date);

    // 1. Available Inventory:
    // Only available from 2026-05-20 onwards. Before May 20, display null (gap, not zero!).
    // Available inventory = opening_stock (eligible opening stock + cumulative receipts - cumulative demand)
    const availableInventory = demandSeries.map(d => {
      if (d.date < SNAPSHOT_DATE) {
        return null;
      }
      const proj = projMap.get(d.date);
      if (!proj) return null;
      return Math.round(proj.opening_stock);
    });

    // 2. Daily Demand Burn: daily corrected_demand
    const demandBurn = demandSeries.map(d => Math.round(d.corrected_demand));

    // 3. Observed Sales: for separate comparison
    const observedSales = demandSeries.map(d => Math.round(d.observed_sales));

    const hasMay20 = demandSeries.some(d => d.date === SNAPSHOT_DATE);

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
          const fullDate = fullDates[idx] || params[0].name;
          const isPreSnapshot = fullDate < SNAPSHOT_DATE;

          let s = `<div style="font-weight:600; color:#ffffff; font-family:Inter, sans-serif;">Date: ${fullDate}</div>`;

          params.forEach((p: any) => {
            if (p.seriesName === "Available Inventory") {
              if (p.value === null || p.value === undefined || isPreSnapshot) {
                s += `<div style="color:#a1a1aa; font-size:10.5px;">${p.marker} Available Inventory: <b style="color:#fcd34d;">[Data Unavailable — Pre-Snapshot]</b></div>`;
              } else {
                s += `<div style="color:#eeece7; font-size:10.5px;">${p.marker} Available Inventory: <b style="color:#2dd4bf;">${Number(p.value).toLocaleString()} btls</b></div>`;
              }
            } else if (p.seriesName === "Daily Demand Burn (Corrected)") {
              s += `<div style="color:#eeece7; font-size:10.5px;">${p.marker} Daily Demand Burn: <b style="color:#f87171;">${Number(p.value).toLocaleString()} btls/d</b></div>`;
            } else if (p.seriesName === "Observed Sales") {
              s += `<div style="color:#eeece7; font-size:10.5px;">${p.marker} Observed Sales: <b style="color:#cbd5e1;">${Number(p.value).toLocaleString()} btls/d</b></div>`;
            }
          });

          if (fullDate === SNAPSHOT_DATE) {
            s += `<div style="color:#93c5fd; font-size:10px; margin-top:3px; font-family:monospace; border-top:1px dashed #3f3f46; padding-top:2px;">[AUTHENTICATED PHYSICAL AUDIT DATE]</div>`;
          }

          return s;
        },
      },
      legend: {
        data: ["Available Inventory", "Daily Demand Burn (Corrected)", "Observed Sales"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 38, right: 65, bottom: 35, left: 65 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif", interval: "auto", hideOverlap: true },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: [
        {
          type: "value",
          name: "Available Stock (Btls)",
          nameLocation: "end",
          nameGap: 10,
          nameTextStyle: { color: "#003c33", fontSize: 9, align: "left" },
          axisLabel: {
            color: "#003c33",
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
            formatter: (v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`),
          },
          splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        },
        {
          type: "value",
          name: "Daily Demand Burn (Btls/Day)",
          nameLocation: "end",
          nameGap: 10,
          nameTextStyle: { color: "#b30000", fontSize: 9, align: "right" },
          axisLabel: {
            color: "#b30000",
            fontSize: 10,
            fontFamily: "JetBrains Mono, monospace",
            formatter: (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`),
          },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "Available Inventory",
          type: "line",
          yAxisIndex: 0,
          data: availableInventory,
          connectNulls: false,
          smooth: false,
          lineStyle: { color: "#003c33", width: 2.5 },
          itemStyle: { color: "#003c33" },
          areaStyle: { color: "rgba(0, 60, 51, 0.08)" },
          markLine: hasMay20
            ? {
                silent: true,
                data: [
                  {
                    xAxis: "05-20",
                    lineStyle: { color: "#1863dc", type: "dashed", width: 1.5 },
                    label: {
                      formatter: "Snapshot (May 20)",
                      color: "#1863dc",
                      position: "insideEndTop",
                      fontSize: 10,
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                    },
                  },
                ],
              }
            : undefined,
        },
        {
          name: "Daily Demand Burn (Corrected)",
          type: "line",
          yAxisIndex: 1,
          data: demandBurn,
          smooth: true,
          lineStyle: { color: "#b30000", width: 2 },
          itemStyle: { color: "#b30000" },
        },
        {
          name: "Observed Sales",
          type: "line",
          yAxisIndex: 1,
          data: observedSales,
          smooth: true,
          lineStyle: { color: "#75758a", width: 1.5, type: "dotted" },
          itemStyle: { color: "#75758a" },
        },
      ],
    };
  }, [demandSeries, projection]);

  // ADDITIONAL CHART: SHELF-LIFE RISK ANALYSIS
  const shelfLifeRiskOption = React.useMemo(() => {
    if (!detail) return {};

    const stockMtQc = detail.usable_stock_mt_qc;
    const stockGtOnly = detail.usable_stock_gt_only;
    const shelfDays = detail.remaining_shelf_life_days;

    return {
      backgroundColor: "transparent",
      tooltip: {
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          const d = params.data;
          return `<div style="font-weight:600; color:#ffffff;">Batch Lot Telemetry</div>
                  <div style="color:#eeece7;">Channel: <b style="color:#ffffff;">${d[2]}</b></div>
                  <div style="color:#eeece7;">Shelf Life: <b style="color:#ffffff;">${d[0]} days remaining</b></div>
                  <div style="color:#eeece7;">Inventory: <b style="color:#ffffff;">${d[1].toLocaleString()} bottles</b></div>`;
        },
      },
      grid: { top: 40, right: 35, bottom: 35, left: 65 },
      xAxis: {
        type: "value",
        max: 85,
        name: "Days Remaining",
        nameLocation: "middle",
        nameGap: 22,
        nameTextStyle: { color: "#75758a", fontSize: 9 },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      yAxis: {
        type: "value",
        name: "Stock (Btls)",
        nameLocation: "end",
        nameGap: 12,
        nameTextStyle: {
          color: "#75758a",
          fontSize: 9,
          fontFamily: "Inter, sans-serif",
          align: "right",
          padding: [0, 6, 0, 0],
        },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          type: "scatter",
          symbolSize: 20,
          data: [
            [shelfDays, stockMtQc, "Modern Trade & QC Eligible (>=60d)", "#003c33"],
            [Math.max(15, shelfDays - 35), stockGtOnly, "General Trade Only (<60d)", "#d97706"],
          ],
          itemStyle: {
            color: (params: any) => params.data[3],
          },
          markLine: {
            silent: true,
            data: [
              {
                xAxis: 60,
                lineStyle: { color: "#b30000", width: 1.5 },
                label: {
                  formatter: "60d MT Gate",
                  color: "#b30000",
                  position: "end",
                  align: "right",
                  padding: [0, 6, 0, 0],
                  fontSize: 10,
                  fontWeight: 600,
                  fontFamily: "Inter, sans-serif",
                },
              },
              {
                xAxis: 67,
                lineStyle: { color: "#d97706", width: 1.5, type: "dashed" },
                label: {
                  formatter: "67d Warning",
                  color: "#d97706",
                  position: "end",
                  align: "left",
                  padding: [14, 0, 0, 6],
                  fontSize: 10,
                  fontWeight: 600,
                  fontFamily: "Inter, sans-serif",
                },
              },
            ],
          },
        },
      ],
    };
  }, [detail]);

  // ALLOCATION-VS-DEMAND ALIGNMENT INDEX (CHART 1)
  const alignmentIndexOption = React.useMemo(() => {
    if (!alignmentReport || !alignmentReport.sku_alignment_indices) return {};

    const items = [...alignmentReport.sku_alignment_indices].reverse();
    const categories = items.map(s => `${s.sku_id} (${s.flavour})`);
    const histData = items.map(s => s.historical_mix_index_pct);
    const demandData = items.map(s => {
      const isSelected = s.sku_id === selectedSku;
      return {
        value: s.current_allocation_index_pct,
        itemStyle: {
          color: isSelected ? "#1863dc" : "#003c33",
          borderColor: isSelected ? "#4c6ee6" : "transparent",
          borderWidth: isSelected ? 2 : 0,
          borderRadius: [0, 4, 4, 0],
        },
      };
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
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const skuItem = items[idx];
          if (!skuItem) return "";

          let html = `<div style="font-weight:600; color:#ffffff; font-family:monospace; margin-bottom:4px;">
            ${skuItem.sku_id} — ${skuItem.flavour}
          </div>`;
          html += `<div style="color:#eeece7; font-size:11px;">Historical-Mix Mismatch: <b style="color:#b30000">${skuItem.historical_mix_index_pct}%</b></div>`;
          html += `<div style="color:#eeece7; font-size:11px;">Demand-Driven Mismatch: <b style="color:#1863dc">${skuItem.current_allocation_index_pct}%</b></div>`;
          html += `<div style="color:#003c33; font-size:11px; margin-bottom:6px;">Improvement: <b>-${skuItem.improvement_pct}%</b> mismatch</div>`;

          if (skuItem.current_depot_breakdown && skuItem.current_depot_breakdown.length > 0) {
            html += `<div style="border-top:1px solid #33333d; padding-top:4px; margin-top:4px; font-size:10px; color:#93939f; font-family:monospace;">TOP MISMATCH DEPOTS:</div>`;
            const sortedDepots = [...skuItem.current_depot_breakdown]
              .sort((a, b) => b.mismatch_contribution_pct - a.mismatch_contribution_pct)
              .slice(0, 3);
            sortedDepots.forEach(d => {
              html += `<div style="font-size:10.5px; font-family:monospace; color:#eeece7; display:flex; justify-content:space-between; gap:8px;">
                <span>${d.depot_id}:</span>
                <span>Alloc <b>${d.allocation_share_pct}%</b> | Dem <b>${d.demand_share_pct}%</b> (Gap: <b>${d.mismatch_contribution_pct}%</b>)</span>
              </div>`;
            });
          }
          return html;
        },
      },
      legend: {
        data: ["Historical-Mix Allocation", "Demand-Driven Allocation (Gold/Improved)"],
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
          name: "Historical-Mix Allocation",
          type: "bar",
          data: histData,
          barGap: "20%",
          itemStyle: { color: "#d9d9dd", borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: "right", formatter: "{c}%", color: "#75758a", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
        {
          name: "Demand-Driven Allocation (Gold/Improved)",
          type: "bar",
          data: demandData,
          itemStyle: { color: "#1863dc", borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: "right", formatter: "{c}%", color: "#17171c", fontWeight: 600, fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
      ],
    };
  }, [alignmentReport, selectedSku]);

  const selectedSkuAlignment = React.useMemo(() => {
    return alignmentReport?.sku_alignment_indices?.find(s => s.sku_id === selectedSku);
  }, [alignmentReport, selectedSku]);

  return (
    <div className="space-y-5 pb-8">
      {/* 1. TOP HEADER & SELECTORS */}
      <section className="space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-cohere-hairline pb-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-cohere-primary">
              Depot Operations Workspace
            </h1>
            <p className="text-xs text-cohere-slate mt-0.5">
              Deep operational drilldown across 45 nodes. Latent demand recovery, inventory depletion sawtooth, and transfer governance.
            </p>
          </div>

          {/* Selectors */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-2 bg-cohere-soft-stone border border-cohere-hairline px-3 py-1.5 rounded-pill">
              <span className="text-[10px] font-mono text-cohere-slate uppercase">Depot:</span>
              <select
                value={selectedDepot}
                onChange={(e) => setSelectedDepot(e.target.value)}
                className="bg-transparent text-xs text-cohere-primary font-mono font-medium focus:outline-none cursor-pointer"
              >
                {depots.map((d) => (
                  <option key={d.depot_id} value={d.depot_id} className="bg-white text-cohere-primary">
                    {d.name} ({d.depot_id})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center space-x-2 bg-cohere-soft-stone border border-cohere-hairline px-3 py-1.5 rounded-pill">
              <span className="text-[10px] font-mono text-cohere-slate uppercase">SKU:</span>
              <select
                value={selectedSku}
                onChange={(e) => setSelectedSku(e.target.value)}
                className="bg-transparent text-xs text-cohere-primary font-mono font-medium focus:outline-none cursor-pointer"
              >
                {skus.map((s) => (
                  <option key={s.sku_id} value={s.sku_id} className="bg-white text-cohere-primary">
                    {s.sku_id} — {s.flavour}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Action message banner */}
        {actionMessage && (
          <div className="p-3 rounded-xs bg-emerald-50 border border-emerald-200 text-xs font-mono text-emerald-800 flex items-center justify-between">
            <span>{actionMessage}</span>
            <button onClick={() => setActionMessage(null)} className="text-sm font-bold hover:text-emerald-950">✕</button>
          </div>
        )}
      </section>

      {/* 2. FIVE PRIMARY LOCAL KPIS */}
      {detail && (
        <section className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white border border-cohere-hairline rounded-xs p-4 shadow-card-flat hover:border-cohere-slate transition-colors">
            <div className="text-[10px] font-mono tracking-wider uppercase text-cohere-slate">Days of Cover (DoC)</div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-primary mt-1.5">
              {detail.days_of_cover !== null ? `${detail.days_of_cover} Days` : "N/A"}
            </div>
            <div className="text-xs text-cohere-deep-green mt-1 font-mono font-medium">Target: 21.0 Days</div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-xs p-4 shadow-card-flat hover:border-cohere-slate transition-colors">
            <div className="text-[10px] font-mono tracking-wider uppercase text-cohere-slate">Allocation Gap</div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-primary mt-1.5">
              {detail.allocation_gap > 0 ? `+${detail.allocation_gap.toLocaleString()}` : detail.allocation_gap.toLocaleString()} <span className="text-xs font-normal text-cohere-slate">btls</span>
            </div>
            <div className="text-xs text-cohere-slate mt-1">Net Rebalancing Need</div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-xs p-4 shadow-card-flat hover:border-cohere-slate transition-colors">
            <div className="text-[10px] font-mono tracking-wider uppercase text-cohere-slate">Demand Uplift %</div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-action-blue mt-1.5">
              {detail.demand_uplift_pct !== null ? `+${detail.demand_uplift_pct}%` : "0.0%"}
            </div>
            <div className="text-xs text-cohere-slate mt-1">Latent vs Observed Run-Rate</div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-xs p-4 shadow-card-flat hover:border-cohere-slate transition-colors">
            <div className="text-[10px] font-mono tracking-wider uppercase text-cohere-slate">Forecast Bias %</div>
            <div className="text-2xl font-bold font-mono tabular-nums text-amber-700 mt-1.5">
              {detail.forecast_bias_pct !== null ? `${detail.forecast_bias_pct > 0 ? "+" : ""}${detail.forecast_bias_pct}%` : "0.0%"}
            </div>
            <div className="text-xs text-cohere-slate mt-1 font-mono">
              {detail.forecast_bias_pct && detail.forecast_bias_pct < 0 ? "Underforecasting" : "Overforecasting"}
            </div>
          </div>

          <div className="bg-white border border-cohere-hairline rounded-xs p-4 shadow-card-flat hover:border-cohere-slate transition-colors">
            <div className="text-[10px] font-mono tracking-wider uppercase text-cohere-slate">Estimated Fill Rate %</div>
            <div className="text-2xl font-bold font-mono tabular-nums text-cohere-deep-green mt-1.5">
              {detail.service_level_fill_rate_pct !== null ? `${detail.service_level_fill_rate_pct}%` : "N/A"}
            </div>
            <div className="text-xs text-cohere-slate mt-1">Target Order Service Level</div>
          </div>
        </section>
      )}

      {/* 3. CHARTS ROW 1: DEMAND SENSING (CHART 7) & INVENTORY SAWTOOTH (CHART 8) */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* CHART 7: DEMAND SENSING VS FORECAST */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-3 shadow-card-flat">
          <div className="flex flex-wrap items-center justify-between border-b border-cohere-hairline pb-3 gap-2">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Chart 7 — Demand Sensing vs. Forecast Vintage
              </div>
              <div className="text-xs text-cohere-slate mt-0.5">
                Observed sell-through vs. Latent Demand estimate. Red zone = censored stock-out window.
              </div>
            </div>
            
            {/* Timeframe selector pills */}
            <div className="flex items-center space-x-1 bg-cohere-soft-stone p-1 rounded-pill border border-cohere-hairline">
              {[
                { id: "FULL_SUMMER", label: "Full Summer (122d)" },
                { id: "MARCH", label: "March (Surge)" },
                { id: "APRIL", label: "April (Drift)" },
                { id: "MAY", label: "May (Outage)" },
                { id: "JUNE", label: "June (Recovery)" },
                { id: "LAST_30", label: "Last 30d" },
              ].map((tf) => (
                <button
                  key={tf.id}
                  onClick={() => setTimeframe(tf.id)}
                  className={`px-2.5 py-1 text-[10px] font-mono font-medium rounded-pill transition-colors ${
                    timeframe === tf.id
                      ? "bg-cohere-primary text-white shadow-xs"
                      : "text-cohere-slate hover:text-cohere-primary"
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          </div>

          <div className="h-80 w-full">
            <EChart
              option={demandSensingOption}
              height={320}
              loading={loading}
              empty={demandSeries.length === 0}
              emptyText="No demand series telemetry for this node"
            />
          </div>
          <div className="text-[11px] text-cohere-slate flex items-center justify-between border-t border-cohere-hairline pt-2">
            <span>Observed sales drop to 0 during stock-outs; Latent Demand recovers true consumer velocity.</span>
            <span className="font-mono text-cohere-slate font-medium">[VINTAGE: 2026-W18]</span>
          </div>
        </div>

        {/* CHART 8: PROJECTED INVENTORY DEPLETION SAWTOOTH */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Chart 8 — Projected Inventory Depletion &amp; Cover Timeline
              </div>
              <div className="text-xs text-cohere-slate mt-0.5">
                Forward 21-day depletion sawtooth with dated inbound receipts.
              </div>
            </div>
            <span className="badge-critical">
              STOCK-OUT: {projection?.projected_stockout_date || "N/A"}
            </span>
          </div>

          <div className="h-80 w-full">
            <EChart
              option={inventorySawtoothOption}
              height={320}
              loading={loading}
              empty={!projection}
              emptyText="No forward projection data available"
            />
          </div>
          <div className="text-[11px] text-cohere-slate flex flex-wrap items-center justify-between border-t border-cohere-hairline pt-2 font-mono">
            <span>Snapshot: 2026-05-20 [Observed Opening: {projection?.timeline?.[0]?.opening_stock ? projection.timeline[0].opening_stock.toLocaleString() : "83,150"} btls] | Shelf-Life: {projection?.shelf_life_status || "Evaluating"}</span>
            <span className="text-cohere-deep-green font-semibold">21d Target: {projection?.target_stock?.toLocaleString() || "407,106"} btls</span>
          </div>
        </div>
      </section>

      {/* 4. CHARTS ROW 2: ADDITIONAL SUPPORTING ANALYTICS */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ADDITIONAL CHART C: DEMAND VS SUPPLY TREND */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-2 shadow-card-flat">
          <div className="border-b border-cohere-hairline pb-2.5 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Demand Burn vs. Available Supply Capacity
              </div>
              <div className="text-xs text-cohere-slate mt-0.5">Comparing daily consumption velocity against physical depot stock</div>
            </div>
            <span className="badge-ok">SNAPSHOT: 2026-05-20</span>
          </div>
          <div className="h-60 w-full">
            <EChart option={demandVsSupplyOption} height={240} />
          </div>
          <div className="text-[10px] text-cohere-slate flex items-center justify-between border-t border-cohere-hairline pt-2 font-mono">
            <span>
              Data Quality Note: Physical inventory snapshot authenticated as of 2026-05-20. Pre-snapshot dates display gap (unavailable) to prevent backward distortion.
            </span>
          </div>
        </div>

        {/* ADDITIONAL CHART D: SHELF-LIFE RISK ANALYSIS */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-2 shadow-card-flat">
          <div className="border-b border-cohere-hairline pb-2.5 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Shelf-Life Freshness &amp; Channel Gate Risk
              </div>
              <div className="text-xs text-cohere-slate mt-0.5">Batches &lt;60d rejected by MT/QC; routed to General Trade via FEFO</div>
            </div>
            <span className="badge-warn">67D CLIFF WARNING</span>
          </div>
          <div className="h-60 w-full">
            <EChart option={shelfLifeRiskOption} height={240} />
          </div>
        </div>
      </section>

      {/* ALLOCATION-VS-DEMAND ALIGNMENT INDEX (CHART 1) */}
      <section className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-4 shadow-card-flat">
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-cohere-hairline pb-3 gap-2">
          <div>
            <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
              Allocation-vs-Demand Alignment Index (Allocation-Mismatch)
            </div>
            <div className="text-xs text-cohere-slate mt-0.5">
              Geographic stock mismatch across 9 depots. Lower values indicate tighter alignment.
            </div>
          </div>
          <div className="flex items-center space-x-2 text-xs font-mono">
            <span className="text-cohere-slate">SKU: <b className="text-cohere-primary">{selectedSku}</b></span>
            <span className="badge-ok">DEMAND-DRIVEN (IMPROVED)</span>
          </div>
        </div>

        <div className="h-64 w-full">
          <EChart option={alignmentIndexOption} height={250} loading={loading} />
        </div>

        {/* Selected SKU Alignment Details Strip */}
        {selectedSkuAlignment && (
          <div className="p-3.5 rounded-xs bg-cohere-soft-stone border border-cohere-hairline space-y-2">
            <div className="flex flex-col md:flex-row md:items-center justify-between text-xs gap-1">
              <span className="font-mono text-cohere-primary font-semibold">
                {selectedSkuAlignment.sku_id} ({selectedSkuAlignment.flavour}) — Depot-Level Allocation vs Demand Shares
              </span>
              <span className="font-mono text-[10.5px] text-cohere-deep-green font-medium">
                Mismatch Index: {selectedSkuAlignment.historical_mix_index_pct}% (Hist) ➔ {selectedSkuAlignment.current_allocation_index_pct}% (Demand-Driven) [-{selectedSkuAlignment.improvement_pct}% mismatch reduction]
              </span>
            </div>

            <div className="grid grid-cols-3 md:grid-cols-9 gap-1.5 pt-1 text-[10.5px] font-mono">
              {selectedSkuAlignment.current_depot_breakdown.map((d) => {
                const isSelectedDepot = d.depot_id === selectedDepot;
                return (
                  <div 
                    key={d.depot_id}
                    className={`p-2.5 rounded-xs border ${isSelectedDepot ? "bg-white border-cohere-action-blue ring-1 ring-cohere-action-blue shadow-card-flat" : "bg-white/80 border-cohere-hairline"} space-y-0.5`}
                  >
                    <div className="text-cohere-slate truncate text-[10px] font-semibold">{d.depot_id}</div>
                    <div className="text-cohere-slate flex justify-between">
                      <span className="text-[9px]">Alloc:</span>
                      <span className="tabular-nums font-medium text-cohere-primary">{d.allocation_share_pct}%</span>
                    </div>
                    <div className="text-cohere-slate flex justify-between">
                      <span className="text-[9px]">Demand:</span>
                      <span className="tabular-nums font-semibold text-cohere-primary">{d.demand_share_pct}%</span>
                    </div>
                    <div className="text-cohere-slate flex justify-between border-t border-cohere-hairline pt-0.5">
                      <span className="text-[9px]">Gap:</span>
                      <span className={`tabular-nums font-semibold ${d.mismatch_contribution_pct > 3.0 ? "text-cohere-error" : "text-cohere-deep-green"}`}>
                        {d.mismatch_contribution_pct}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {/* 5. REBALANCING PROPOSALS TABLE & MANUAL REPORT FORM */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* REBALANCING PROPOSALS (2 COLS) */}
        <div className="lg:col-span-2 bg-white border border-cohere-hairline rounded-sm p-5 space-y-4 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
            <div>
              <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                Feasible Inter-Depot Rebalancing Proposals ({proposals.length})
              </div>
              <div className="text-xs text-cohere-slate mt-0.5">
                Strict guardrail enforcement: donor post-transfer cover must remain &ge; 21.0 days.
              </div>
            </div>
            <span className="badge-ok">RATE: ₹1.50/BTL</span>
          </div>

          {proposals.length === 0 ? (
            <div className="p-8 text-center text-xs font-mono text-cohere-slate bg-cohere-soft-stone rounded-sm border border-cohere-hairline">
              No feasible inter-depot transfers found satisfying donor safety stock &ge; 21d cover.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-cohere-hairline text-cohere-slate text-[10px] uppercase font-mono tracking-wider bg-cohere-soft-stone/40">
                    <th className="py-2.5 px-3">Ticket</th>
                    <th className="py-2.5 px-3">Origin ➔ Dest</th>
                    <th className="py-2.5 px-3 text-right">Quantity</th>
                    <th className="py-2.5 px-3 text-right">Freight Cost</th>
                    <th className="py-2.5 px-3 text-center">Donor Cover</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cohere-hairline font-mono text-xs text-cohere-primary">
                  {proposals.map((p) => (
                    <React.Fragment key={p.recommendation_id}>
                      <tr className="hover:bg-cohere-soft-stone/40 transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-cohere-action-blue">{p.recommendation_id}</td>
                        <td className="py-2.5 px-3 text-cohere-slate">
                          <span className="text-cohere-primary">{p.origin_depot_id}</span>
                          <ArrowRight className="w-3 h-3 text-cohere-action-blue inline mx-1.5" />
                          <span className="text-cohere-primary font-medium">{p.destination_depot_id}</span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium text-cohere-primary tabular-nums">
                          {p.quantity_bottles.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-right text-cohere-slate tabular-nums">
                          ₹{Math.round(p.cost_inr).toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-center text-cohere-deep-green font-medium tabular-nums">
                          {p.donor_post_cover_days}d
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span className={
                            p.status === "APPROVED" 
                              ? "badge-ok" 
                              : p.status === "REJECTED" 
                              ? "badge-critical" 
                              : "badge-warn"
                          }>
                            [{p.status}]
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right space-x-1.5 whitespace-nowrap">
                          {p.status === "PENDING" ? (
                            <>
                              <button
                                onClick={() => handleDecision(p.recommendation_id, "APPROVE")}
                                className="px-2.5 py-1 rounded-pill bg-cohere-primary text-white text-[10px] font-mono hover:bg-black transition-colors"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => {
                                  setModifyingProposal(p);
                                  setModifiedQty(p.quantity_bottles);
                                }}
                                className="button-pill-outline text-[10px] px-2 py-0.5"
                              >
                                Modify
                              </button>
                              <button
                                onClick={() => handleDecision(p.recommendation_id, "REJECT")}
                                className="px-2.5 py-1 rounded-pill bg-white border border-cohere-error text-cohere-error text-[10px] font-mono hover:bg-rose-50 transition-colors"
                              >
                                Reject
                              </button>
                            </>
                          ) : (
                            <span className="text-[10px] text-cohere-slate italic font-sans">Committed</span>
                          )}
                        </td>
                      </tr>
                      {p.selection_rationale && (
                        <tr className="bg-cohere-soft-stone/30">
                          <td colSpan={7} className="py-1.5 px-3 text-[10.5px] font-mono text-cohere-slate border-b border-cohere-hairline">
                            <span className="text-cohere-primary font-medium">Feasibility Rationale:</span> {p.selection_rationale}
                            {p.rejected_alternatives && (
                              <span className="text-cohere-slate ml-2 italic">({p.rejected_alternatives})</span>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* MANUAL STOCKOUT REPORTING FORM (1 COL) */}
        <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-4 shadow-card-flat">
          <div className="border-b border-cohere-hairline pb-3">
            <div className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono flex items-center space-x-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-cohere-action-blue" />
              <span>Log Manual Stock-Out Incident</span>
            </div>
            <div className="text-xs text-cohere-slate mt-0.5">
              Report field stock-out from dark stores to update latent demand.
            </div>
          </div>

          {reportSuccess && (
            <div className="p-3 rounded-xs bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-mono">
              {reportSuccess}
            </div>
          )}

          <form onSubmit={handleSubmitStockout} className="space-y-3 text-xs">
            <div>
              <label className="block text-[10px] font-mono text-cohere-slate uppercase mb-1">Channel:</label>
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-xs px-3 py-2 text-xs text-cohere-primary focus:outline-none focus:border-cohere-action-blue cursor-pointer"
              >
                <option value="Quick Commerce">Quick Commerce (Zepto/Blinkit/Instamart)</option>
                <option value="Modern Trade">Modern Trade (DMart/Reliance)</option>
                <option value="General Trade">General Trade (Kiranas)</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-cohere-slate uppercase mb-1">
                Estimated Unmet Demand (Bottles):
              </label>
              <input
                type="number"
                value={unmetBottles}
                onChange={(e) => setUnmetBottles(parseInt(e.target.value) || 0)}
                className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-xs px-3 py-2 text-xs text-cohere-primary font-mono focus:outline-none focus:border-cohere-action-blue tabular-nums"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono text-cohere-slate uppercase mb-1">Evidence Source:</label>
              <input
                type="text"
                value={evidence}
                onChange={(e) => setEvidence(e.target.value)}
                className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-xs px-3 py-2 text-xs text-cohere-primary focus:outline-none focus:border-cohere-action-blue"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono text-cohere-slate uppercase mb-1">Reporter Role:</label>
              <input
                type="text"
                value={reporter}
                onChange={(e) => setReporter(e.target.value)}
                className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-xs px-3 py-2 text-xs text-cohere-primary focus:outline-none focus:border-cohere-action-blue"
              />
            </div>

            <button
              type="submit"
              className="button-primary w-full py-2.5 flex items-center justify-center space-x-1.5 mt-2"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Submit &amp; Recalibrate Demand</span>
            </button>
          </form>
        </div>
      </section>

      {/* MODIFY QUANTITY MODAL */}
      {modifyingProposal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-cohere-hairline rounded-md max-w-sm w-full p-6 space-y-4 shadow-card-elevated text-cohere-primary">
            <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
              <span className="font-mono font-medium text-xs text-cohere-primary uppercase tracking-wider">
                MODIFY QUANTITY [{modifyingProposal.recommendation_id}]
              </span>
              <button onClick={() => setModifyingProposal(null)} className="text-cohere-slate hover:text-cohere-primary text-sm font-bold">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="text-cohere-slate">
                Original Quantity: <b className="text-cohere-primary font-mono tabular-nums">{modifyingProposal.quantity_bottles.toLocaleString()} btls</b>
              </div>
              <div>
                <label className="block text-[10px] font-mono text-cohere-slate uppercase mb-1">New Transfer Quantity:</label>
                <input
                  type="number"
                  value={modifiedQty}
                  onChange={(e) => setModifiedQty(parseInt(e.target.value) || 0)}
                  className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-xs px-3 py-2 text-xs font-mono text-cohere-primary focus:outline-none focus:border-cohere-action-blue tabular-nums"
                />
              </div>
              <div className="text-[11px] text-cohere-slate">
                New Transfer Cost: <span className="font-mono text-cohere-primary font-semibold">₹{Math.round(modifiedQty * 1.5).toLocaleString()}</span> (@ ₹1.50/btl)
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-cohere-hairline font-mono text-xs">
              <button
                onClick={() => setModifyingProposal(null)}
                className="button-pill-outline text-xs"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleDecision(modifyingProposal.recommendation_id, "MODIFY", modifiedQty);
                  setModifyingProposal(null);
                }}
                className="button-primary text-xs"
              >
                Confirm Modification
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
