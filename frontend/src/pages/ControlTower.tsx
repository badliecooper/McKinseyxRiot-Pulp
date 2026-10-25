import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  FileText,
  Download,
  RefreshCw,
  Layers,
  Sliders,
  DollarSign,
  TrendingDown,
  TrendingUp,
  ShieldAlert,
  ChevronDown,
  ChevronRight,
  Sparkles,
  PieChart as PieIcon,
  BarChart2,
  Check
} from "lucide-react";
import { api } from "../api/client";
import {
  HealthRibbon,
  NationalKPIs,
  HeatmapResponse,
  RiskMatrixResponse,
  RebalancingProposal,
  LossAttributionData,
  AlarmItem,
  ForecastAccuracyComparison,
  PulpBuildTimelineData
} from "../types";
import { EChart } from "../components/EChart";

export const ControlTower: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [ribbon, setRibbon] = useState<HealthRibbon | null>(null);
  const [kpis, setKpis] = useState<NationalKPIs | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string>("allocation_gap");
  const [riskMatrix, setRiskMatrix] = useState<RiskMatrixResponse | null>(null);
  const [proposals, setProposals] = useState<RebalancingProposal[]>([]);
  const [lossAttr, setLossAttr] = useState<LossAttributionData | null>(null);
  const [alarms, setAlarms] = useState<AlarmItem[]>([]);
  const [alarmFilterSev, setAlarmFilterSev] = useState<string>("ALL");
  const [reportPreview, setReportPreview] = useState<any>(null);
  const [generatingReport, setGeneratingReport] = useState<boolean>(false);
  const [selectedAlarm, setSelectedAlarm] = useState<AlarmItem | null>(null);

  // Forecast Accuracy National vs Local (Visualization 2)
  const [forecastAccuracy, setForecastAccuracy] = useState<ForecastAccuracyComparison | null>(null);
  const [demandMix, setDemandMix] = useState<any[]>([]);
  const [vintageTrend, setVintageTrend] = useState<{
    labels: string[];
    wape_series: number[];
    bias_series: number[];
    naive_wape_series: number[];
    details: any[];
  } | null>(null);

  // Pre-Summer Passionfruit Pulp Build Timeline (Visualization 4)
  const [pulpTimeline, setPulpTimeline] = useState<PulpBuildTimelineData | null>(null);
  const [showPulpTimeline, setShowPulpTimeline] = useState<boolean>(true);
  const [pulpStartingCover, setPulpStartingCover] = useState<number>(14);
  const [pulpTargetCover, setPulpTargetCover] = useState<number>(24);
  const [pulpWeeklyBuildKg, setPulpWeeklyBuildKg] = useState<number>(18000);
  const [pulpHoldingCostRate, setPulpHoldingCostRate] = useState<number>(12.50);

  // Sliders state
  const [sliderLate, setSliderLate] = useState<number>(35);
  const [sliderStale, setSliderStale] = useState<number>(40);
  const [sliderPulp, setSliderPulp] = useState<number>(25);

  // Collapsible section toggles
  const [showCausalLoop, setShowCausalLoop] = useState<boolean>(false);
  const [showFeasibility, setShowFeasibility] = useState<boolean>(false);
  const [showWeeklyReport, setShowWeeklyReport] = useState<boolean>(true);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [rRibbon, rKpis, rHeatmap, rMatrix, rRebal, rLoss, rAlarms, rReport, rForecast, rPulp, rDemandMix, rVintageTrend] = await Promise.all([
        api.getHealthRibbon(),
        api.getNationalKPIs(),
        api.getHeatmap(selectedMetric),
        api.getRiskMatrix(),
        api.getRebalancingNetwork(),
        api.getLossAttribution(),
        api.getAlarms(),
        api.getReportPreview("2026-W18"),
        api.getForecastAccuracyComparison("VINTAGE-2026-W18"),
        api.getPulpBuildTimeline(pulpStartingCover, pulpTargetCover, pulpWeeklyBuildKg, pulpHoldingCostRate),
        api.getDemandMix(),
        api.getForecastVintageTrend(),
      ]);

      setRibbon(rRibbon);
      setKpis(rKpis);
      setHeatmap(rHeatmap);
      setRiskMatrix(rMatrix);
      setProposals(rRebal.proposals);
      setLossAttr(rLoss);
      setAlarms(rAlarms.alarms);
      setReportPreview(rReport);
      setForecastAccuracy(rForecast);
      setPulpTimeline(rPulp);
      setDemandMix(rDemandMix || []);
      setVintageTrend(rVintageTrend || null);

      if (rLoss.root_cause_breakdown) {
        setSliderLate(rLoss.root_cause_breakdown.late_demand_detection?.share_pct || 35);
        setSliderStale(rLoss.root_cause_breakdown.stale_allocation_censored_loop?.share_pct || 40);
        setSliderPulp(rLoss.root_cause_breakdown.single_source_pulp_rationing?.share_pct || 25);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load Control Tower data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedMetric]);

  const handleSliderChange = async (key: string, val: number) => {
    if (!lossAttr) return;
    try {
      const currentShares = {
        late_demand_detection: sliderLate,
        stale_allocation_censored_loop: sliderStale,
        single_source_pulp_rationing: sliderPulp,
      };
      const res = await api.redistributeLosses(key, val, currentShares);
      setLossAttr(res);
      setSliderLate(res.root_cause_breakdown.late_demand_detection.share_pct);
      setSliderStale(res.root_cause_breakdown.stale_allocation_censored_loop.share_pct);
      setSliderPulp(res.root_cause_breakdown.single_source_pulp_rationing.share_pct);
    } catch (e: any) {
      console.error(e);
    }
  };

  const handleAcknowledgeAlarm = async (alarmId: string) => {
    try {
      await api.acknowledgeAlarm(alarmId, "Executive-Planner");
      const rAlarms = await api.getAlarms();
      setAlarms(rAlarms.alarms);
    } catch (e) {
      console.error(e);
    }
  };

  const handleResolveAlarm = async (alarmId: string) => {
    try {
      await api.resolveAlarm(alarmId, "Resolved via Executive Control Tower");
      const rAlarms = await api.getAlarms();
      setAlarms(rAlarms.alarms);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDownloadReport = async () => {
    try {
      setGeneratingReport(true);
      const res = await api.generateReport("2026-W18");
      
      const downloadPath = res.download_url.startsWith("http")
        ? res.download_url
        : res.download_url.startsWith("/api")
        ? res.download_url
        : `/api${res.download_url}`;

      const response = await fetch(downloadPath);
      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = res.filename || "weekly_intelligence_report_2026-W18.pdf";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (e: any) {
      alert("Report generation failed: " + (e.message || "Network error"));
    } finally {
      setGeneratingReport(false);
    }
  };

  const filteredAlarms = alarms.filter(a => {
    if (alarmFilterSev === "ALL") return true;
    return a.severity === alarmFilterSev;
  });

  // =========================================================================
  // ECHARTS CONFIGURATIONS
  // =========================================================================

  // CHART 1: FLAVOUR X DEPOT HEATMAP (Red - Yellow - Green Semantic Palettes for all 3 KPIs)
  const heatmapOption = React.useMemo(() => {
    if (!heatmap) return {};
    const data: [number, number, number][] = [];
    const allVals: number[] = [];

    heatmap.rows.forEach((row, rIdx) => {
      heatmap.columns.forEach((col, cIdx) => {
        const val = heatmap.matrix[rIdx]?.[cIdx];
        if (val !== undefined && val !== null && !isNaN(val)) {
          data.push([cIdx, rIdx, val]);
          allVals.push(val);
        }
      });
    });

    const isDoC = selectedMetric === "days_of_cover";
    const isWAPE = selectedMetric === "wape_pct";

    let minVal = allVals.length > 0 ? Math.min(...allVals) : 0;
    let maxVal = allVals.length > 0 ? Math.max(...allVals) : 100;

    // Calibrate metric scale bounds for semantic Red-Yellow-Green thresholds:
    if (isDoC) {
      // Days of Cover: <7d Critical RED, 14d Warning YELLOW, >=21d Healthy GREEN
      minVal = 0;
      maxVal = Math.max(28, Math.ceil(maxVal));
    } else if (isWAPE) {
      // WAPE %: 0-10% Accurate GREEN, 20-30% Moderate YELLOW, >=35% Severe RED
      minVal = 0;
      maxVal = Math.max(35, Math.ceil(maxVal));
    } else {
      // Allocation Gap: Negative is Surplus GREEN, ~0 is Balanced YELLOW, Positive is Shortage RED
      // Keep minVal and maxVal from actual data
    }

    return {
      backgroundColor: "transparent",
      tooltip: {
        position: "top",
        backgroundColor: "#0f172a",
        borderColor: "#334155",
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          const colName = heatmap.columns[params.data[0]];
          const rowName = heatmap.rows[params.data[1]];
          const val = params.data[2];
          let formattedVal = "";
          let statusBadge = "";

          if (isDoC) {
            formattedVal = `${val}d Cover`;
            statusBadge = val < 7 ? `<span style="color:#ef4444; font-weight:700;">[CRITICAL STOCK-OUT RISK]</span>` :
                          val < 14 ? `<span style="color:#f59e0b; font-weight:700;">[NEAR-CLIFF WARNING]</span>` :
                          val >= 21 ? `<span style="color:#22c55e; font-weight:700;">[TARGET COVER HEALTHY]</span>` :
                          `<span style="color:#eab308; font-weight:700;">[MODERATE COVER]</span>`;
          } else if (isWAPE) {
            formattedVal = `${val}% WAPE`;
            statusBadge = val <= 15 ? `<span style="color:#22c55e; font-weight:700;">[EXCELLENT ACCURACY]</span>` :
                          val <= 25 ? `<span style="color:#eab308; font-weight:700;">[ACCEPTABLE ERROR]</span>` :
                          `<span style="color:#ef4444; font-weight:700;">[HIGH FORECAST DRIFT]</span>`;
          } else {
            formattedVal = `${val > 0 ? "+" : ""}${val.toLocaleString()} bottles gap`;
            statusBadge = val > 50000 ? `<span style="color:#ef4444; font-weight:700;">[SHORTAGE DEFICIT]</span>` :
                          val < -50000 ? `<span style="color:#22c55e; font-weight:700;">[SURPLUS DONOR CANDIDATE]</span>` :
                          `<span style="color:#eab308; font-weight:700;">[BALANCED ALLOCATION]</span>`;
          }

          return `<div style="font-weight:600; color:#ffffff; font-size:12px;">${colName} @ ${rowName}</div>
                  <div style="margin-top:4px; font-family:'JetBrains Mono',monospace; color:#f8fafc; font-size:12px;">${formattedVal}</div>
                  <div style="margin-top:4px; font-size:10px;">${statusBadge}</div>`;
        },
      },
      grid: { top: 20, right: 20, bottom: 72, left: 110 },
      xAxis: {
        type: "category",
        data: heatmap.columns,
        splitArea: { show: true },
        axisLabel: { color: "#0f172a", fontWeight: 600, fontSize: 11 },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
      },
      yAxis: {
        type: "category",
        data: heatmap.rows,
        splitArea: { show: true },
        axisLabel: { color: "#334155", fontSize: 11, fontWeight: 500 },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
      },
      visualMap: {
        min: minVal,
        max: maxVal,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 2,
        itemWidth: 12,
        itemHeight: 180,
        textStyle: { color: "#475569", fontSize: 10, fontFamily: "JetBrains Mono, monospace", fontWeight: 600 },
        formatter: (val: number) => {
          if (isDoC) return `${Math.round(val)}d`;
          if (isWAPE) return `${Math.round(val)}%`;
          return `${val > 0 ? "+" : ""}${Math.round(val / 1000)}k`;
        },
        inRange: {
          // Standard Red - Yellow - Green Semantic Palettes:
          // Days of Cover: Low cover (<7d) is RED -> 14d is YELLOW -> >=21d is GREEN
          // WAPE %: Low error (0-15%) is GREEN -> 20-30% is YELLOW -> High error is RED
          // Allocation Gap: Negative (Surplus supply) is GREEN -> ~0 (Balanced) is YELLOW -> Positive (Deficit) is RED
          color: isDoC
            ? ["#dc2626", "#ea580c", "#eab308", "#84cc16", "#16a34a"]
            : ["#16a34a", "#84cc16", "#eab308", "#ea580c", "#dc2626"],
        },
      },
      series: [
        {
          name: "Heatmap Metric",
          type: "heatmap",
          data: data,
          itemStyle: {
            borderColor: "#ffffff",
            borderWidth: 1.5,
            borderRadius: 2,
          },
          label: {
            show: true,
            color: "#ffffff",
            fontWeight: 700,
            fontSize: 10.5,
            fontFamily: "JetBrains Mono, monospace",
            textBorderColor: "rgba(15, 23, 42, 0.5)",
            textBorderWidth: 2,
            formatter: (p: any) =>
              isDoC ? `${p.data[2]}d` : isWAPE ? `${p.data[2]}%` : `${p.data[2] > 0 ? "+" : ""}${Math.round(p.data[2] / 1000)}k`,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: "rgba(0, 0, 0, 0.5)",
              borderColor: "#0f172a",
              borderWidth: 2,
            },
          },
        },
      ],
    };
  }, [heatmap, selectedMetric]);

  // CHART 2: DEMAND VS INVENTORY RISK MATRIX
  const riskMatrixOption = React.useMemo(() => {
    if (!riskMatrix) return {};

    const points = riskMatrix.points.map(pt => [
      pt.forecast_demand,
      pt.days_of_cover,
      pt.allocation_gap,
      pt.sku_id,
      pt.depot_id,
      pt.risk_level,
      pt.projected_stockout_date,
    ]);

    return {
      backgroundColor: "transparent",
      tooltip: {
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          const d = params.data;
          const isCrit = d[5] === "CRITICAL";
          return `<div style="font-weight:600; color:${isCrit ? '#b30000' : '#ffffff'}; font-family:monospace;">${d[3]} @ ${d[4]}</div>
                  <div style="margin-top:4px;">DoC: <b>${d[1]} days</b> | Demand: <b>${Math.round(d[0]).toLocaleString()} btls/d</b></div>
                  <div style="color:#eeece7;">Allocation Gap: ${d[2] > 0 ? `+${d[2].toLocaleString()}` : d[2].toLocaleString()} btls</div>
                  <div style="color:${isCrit ? '#ffad9b' : '#93939f'}; font-size:10px;">Stock-out ETA: ${d[6]}</div>`;
        },
      },
      grid: { top: 25, right: 30, bottom: 55, left: 55 },
      xAxis: {
        type: "value",
        name: "Corrected Daily Demand (btls/d)",
        nameLocation: "middle",
        nameGap: 28,
        nameTextStyle: { color: "#75758a", fontSize: 10 },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        axisLabel: { color: "#616161", fontSize: 10 },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "Days of Cover (DoC)",
        nameTextStyle: { color: "#75758a", fontSize: 10 },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        axisLabel: { color: "#616161", fontSize: 10 },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      series: [
        {
          type: "scatter",
          data: points,
          symbolSize: (val: any) => {
            const gap = Math.abs(val[2] || 10000);
            return Math.max(10, Math.min(26, gap / 60000));
          },
          itemStyle: {
            color: (params: any) => {
              const r = params.data[5];
              if (r === "CRITICAL") return "#dc2626";
              if (r === "WARNING") return "#d97706";
              return "#0d9488";
            },
            shadowBlur: 4,
            shadowColor: "rgba(0,0,0,0.5)",
          },
          markLine: {
            silent: true,
            lineStyle: { type: "dashed", width: 1 },
            data: [
              { yAxis: 21, lineStyle: { color: "#0d9488" }, label: { formatter: "21d Target", color: "#0d9488", position: "end" } },
              { yAxis: 7, lineStyle: { color: "#dc2626" }, label: { formatter: "7d Cliff", color: "#dc2626", position: "end" } },
            ],
          },
          markArea: {
            silent: true,
            itemStyle: { color: "rgba(220, 38, 38, 0.05)" },
            data: [
              [
                { yAxis: 0, xAxis: 3500 },
                { yAxis: 7, xAxis: 15000 },
              ],
            ],
          },
        },
      ],
    };
  }, [riskMatrix]);

  // CHART 3: DEPOT REBALANCING NETWORK
  const rebalancingNetworkOption = React.useMemo(() => {
    const depotNodes = [
      { name: "Depot-North-01", label: "Delhi NCR", x: 200, y: 45, symbolSize: 32, category: 0 },
      { name: "Depot-North-02", label: "Lucknow", x: 300, y: 75, symbolSize: 26, category: 1 },
      { name: "Depot-West-01", label: "Mumbai", x: 100, y: 165, symbolSize: 36, category: 0 },
      { name: "Depot-West-02", label: "Ahmedabad", x: 80, y: 105, symbolSize: 26, category: 1 },
      { name: "Depot-Central-01", label: "Indore", x: 210, y: 130, symbolSize: 28, category: 2 },
      { name: "Depot-South-01", label: "Bengaluru", x: 190, y: 230, symbolSize: 30, category: 2 },
      { name: "Depot-South-02", label: "Chennai", x: 280, y: 225, symbolSize: 32, category: 1 },
      { name: "Depot-East-01", label: "Kolkata", x: 390, y: 140, symbolSize: 28, category: 1 },
      { name: "Depot-East-02", label: "Guwahati", x: 470, y: 95, symbolSize: 24, category: 0 },
    ];

    const links = proposals.map(p => ({
      source: p.origin_depot_id,
      target: p.destination_depot_id,
      value: p.quantity_bottles,
      sku: p.sku_id,
      cost: p.cost_inr,
      eta: p.eta_days,
      donorPost: p.donor_post_cover_days,
      status: p.status,
      selectionRationale: p.selection_rationale,
      lineStyle: {
        width: Math.max(2, Math.min(6, p.quantity_bottles / 15000)),
        curveness: 0.25,
        color: p.status === "APPROVED" ? "#0d9488" : "#1863dc",
        type: p.status === "PENDING" ? "dashed" : "solid",
      },
    }));

    return {
      backgroundColor: "transparent",
      tooltip: {
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          if (params.dataType === "edge") {
            const d = params.data;
            const statusBadge = d.status === "APPROVED" ? "[APPROVED FOR DISPATCH]" : "[PROPOSED - PENDING APPROVAL]";
            return `<div style="font-weight:600; color:#ffffff; font-family:monospace;">LANE: ${d.source} ➔ ${d.target}</div>
                    <div style="margin-top:3px;">SKU: <b>${d.sku}</b> | Transfer: <b>${d.value.toLocaleString()} btls</b></div>
                    <div style="color:#eeece7;">Freight: ₹${Math.round(d.cost).toLocaleString()} (@ ₹1.50/btl) | ETA: <b>${d.eta}d</b></div>
                    <div style="color:#003c33;">Donor Post-Cover: <b>${d.donorPost}d</b> (&ge;21d target)</div>
                    ${d.selectionRationale ? `<div style="color:#1863dc; font-size:10px; margin-top:3px;"><b>Ranked Choice:</b> ${d.selectionRationale}</div>` : ""}
                    <div style="color:${d.status === 'APPROVED' ? '#003c33' : '#1863dc'}; font-size:10px; margin-top:2px; font-weight:600;">Status: ${statusBadge}</div>`;
          }
          return `<div style="font-weight:600; color:#ffffff;">${params.data.label} (${params.data.name})</div>`;
        },
      },
      legend: {
        data: ["Shortage Depot", "Surplus Donor", "Balanced Depot"],
        textStyle: { color: "#616161", fontSize: 10 },
        top: 0,
      },
      series: [
        {
          type: "graph",
          layout: "none",
          roam: false,
          edgeSymbol: ["circle", "arrow"],
          edgeSymbolSize: [4, 10],
          categories: [
            { name: "Shortage Depot", itemStyle: { color: "#b30000" } },
            { name: "Surplus Donor", itemStyle: { color: "#003c33" } },
            { name: "Balanced Depot", itemStyle: { color: "#75758a" } },
          ],
          data: depotNodes.map(n => ({
            ...n,
            label: {
              show: true,
              position: "bottom",
              color: "#17171c",
              fontSize: 10,
              formatter: n.label,
            },
          })),
          links: links,
          lineStyle: { opacity: 0.85 },
          emphasis: {
            focus: "adjacency",
            lineStyle: { width: 4 },
          },
        },
      ],
    };
  }, [proposals]);

  // CHART 4: HISTORICAL LOSS ATTRIBUTION
  const lossAttributionOption = React.useMemo(() => {
    if (!lossAttr) return {};

    const categories = [
      "Emergency Air Freight",
      "Write-Offs & Discounts",
      "Foregone Contribution",
      "Stock-Out Lost Revenue",
    ];

    const values = [
      lossAttr.emergency_air_freight_inr_cr,
      lossAttr.writeoffs_and_discounts_inr_cr,
      lossAttr.foregone_contribution_inr_cr,
      lossAttr.stockout_lost_revenue_inr_cr,
    ];

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
          const p = params[0];
          return `<div style="font-weight:600; color:#ffffff;">${p.name}</div>
                  <div style="margin-top:3px; font-family:monospace; font-size:12px; color:#ffffff;">₹${p.value} Crores</div>
                  <div style="color:#93939f; font-size:10px;">${p.dataIndex === 3 ? "Top-Line Metric (Do NOT sum with contribution)" : "Bottom-Line Impact Category"}</div>`;
        },
      },
      grid: { top: 15, right: 65, bottom: 20, left: 150 },
      xAxis: {
        type: "value",
        axisLabel: { formatter: "₹{value} Cr", color: "#616161", fontSize: 10 },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLabel: { color: "#17171c", fontSize: 11 },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      series: [
        {
          name: "Financial Impact",
          type: "bar",
          data: values.map((val, idx) => ({
            value: val,
            itemStyle: {
              color: idx === 3 ? "#75758a" : idx === 2 ? "#1863dc" : idx === 1 ? "#d97706" : "#b30000",
              borderRadius: [0, 2, 2, 0],
            },
          })),
          label: {
            show: true,
            position: "right",
            formatter: "₹{c} Cr",
            color: "#17171c",
            fontFamily: "JetBrains Mono, monospace",
            fontWeight: 600,
            fontSize: 11,
          },
        },
      ],
    };
  }, [lossAttr]);

  // ADDITIONAL CHART: SKU DEMAND MIX (DONUT)
  const skuDemandMixOption = React.useMemo(() => {
    const pieData = (demandMix && demandMix.length > 0)
      ? demandMix.map(d => ({
          value: d.value,
          name: d.name,
          itemStyle: d.itemStyle,
        }))
      : [
          { value: 38, name: "PR-MPB (Mango)", itemStyle: { color: "#1863dc" } },
          { value: 20, name: "PR-GC (Guava)", itemStyle: { color: "#003c33" } },
          { value: 16, name: "PR-PP (Pulp Passion)", itemStyle: { color: "#d97706" } },
          { value: 14, name: "PR-DB (Dragon Berry)", itemStyle: { color: "#75758a" } },
          { value: 12, name: "PR-DP (Dragon Passion)", itemStyle: { color: "#b30000" } },
        ];

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: "{b}: <b>{c}%</b> of Summer Demand",
      },
      legend: {
        orient: "vertical",
        right: 10,
        top: "middle",
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        itemWidth: 10,
        itemHeight: 10,
      },
      series: [
        {
          name: "Summer Demand Mix",
          type: "pie",
          radius: ["45%", "75%"],
          center: ["38%", "50%"],
          avoidLabelOverlap: false,
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              fontSize: 12,
              fontWeight: "bold",
              color: "#17171c",
              formatter: "{b}\n{c}%",
            },
          },
          data: pieData,
        },
      ],
    };
  }, [demandMix]);

  // ADDITIONAL CHART: INVENTORY RISK DISTRIBUTION (STACKED BARS)
  const inventoryRiskDistOption = React.useMemo(() => {
    if (!riskMatrix) return {};
    let critCount = 0;
    let warnCount = 0;
    let healthyCount = 0;

    riskMatrix.points.forEach(pt => {
      if (pt.risk_level === "CRITICAL") critCount++;
      else if (pt.risk_level === "WARNING") warnCount++;
      else healthyCount++;
    });

    const isCritSmall = critCount < 6;
    const isWarnSmall = warnCount < 6;

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: () => {
          return `<div style="font-weight:600; color:#ffffff; font-family:Inter, sans-serif;">45-Grain Risk Distribution</div>
                  <div style="color:#eeece7; font-size:11px; margin-top:2px;">Safe (≥21d): <b style="color:#2dd4bf;">${healthyCount}</b> (${((healthyCount/45)*100).toFixed(1)}%)</div>
                  <div style="color:#eeece7; font-size:11px;">Warning (7–14d): <b style="color:#fbbf24;">${warnCount}</b> (${((warnCount/45)*100).toFixed(1)}%)</div>
                  <div style="color:#eeece7; font-size:11px;">Critical (&lt;7d): <b style="color:#f87171;">${critCount}</b> (${((critCount/45)*100).toFixed(1)}%)</div>`;
        },
      },
      grid: { top: 15, right: 80, bottom: 25, left: 40 },
      xAxis: {
        type: "category",
        data: ["Risk Bands (45 Total)"],
        axisLine: { lineStyle: { color: "#d9d9dd" } },
        axisLabel: { show: false },
      },
      yAxis: {
        type: "value",
        max: 45,
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
      },
      series: [
        {
          name: "Critical (<7d)",
          type: "bar",
          stack: "total",
          barWidth: 54,
          data: [critCount],
          itemStyle: { color: "#b30000", borderRadius: [0, 0, 3, 3] },
          label: {
            show: critCount > 0,
            position: isCritSmall ? "right" : "inside",
            distance: isCritSmall ? 8 : 0,
            offset: isCritSmall ? [0, 6] : [0, 0],
            formatter: "{c} Crit",
            color: isCritSmall ? "#b30000" : "#ffffff",
            fontSize: 10,
            fontWeight: 700,
            fontFamily: "JetBrains Mono, monospace",
          },
        },
        {
          name: "Warning (7-14d)",
          type: "bar",
          stack: "total",
          barWidth: 54,
          data: [warnCount],
          itemStyle: { color: "#d97706" },
          label: {
            show: warnCount > 0,
            position: isWarnSmall ? "right" : "inside",
            distance: isWarnSmall ? 8 : 0,
            offset: isWarnSmall ? [0, isCritSmall ? -10 : 0] : [0, 0],
            formatter: "{c} Warn",
            color: isWarnSmall ? "#d97706" : "#ffffff",
            fontSize: 10,
            fontWeight: 700,
            fontFamily: "JetBrains Mono, monospace",
          },
        },
        {
          name: "Healthy (>=21d)",
          type: "bar",
          stack: "total",
          barWidth: 54,
          data: [healthyCount],
          itemStyle: { color: "#003c33", borderRadius: [3, 3, 0, 0] },
          label: {
            show: healthyCount > 0,
            position: healthyCount < 6 ? "right" : "inside",
            formatter: "{c} Safe",
            color: healthyCount < 6 ? "#003c33" : "#ffffff",
            fontSize: 11,
            fontWeight: 600,
            fontFamily: "JetBrains Mono, monospace",
          },
        },
      ],
    };
  }, [riskMatrix]);

  // CHART 5: FORECAST ACCURACY BENCHMARK
  const forecastAccuracyOption = React.useMemo(() => {
    const natWape = forecastAccuracy?.national_panel?.wape_pct ?? 17.2;
    const locWape = forecastAccuracy?.sku_depot_panel?.wape_pct ?? 17.2;
    const naiveWape = 19.5;

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
          let s = `<div style="font-weight:600; color:#ffffff;">${params[0].name}</div>`;
          params.forEach((p: any) => {
            s += `<div>${p.marker} ${p.seriesName}: <b>${p.value}% WAPE</b></div>`;
          });
          return s;
        },
      },
      legend: {
        data: ["RIOT RADAR S&OP", "Naive Benchmark"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 30, right: 20, bottom: 30, left: 50 },
      xAxis: {
        type: "category",
        data: ["National Aggregate", "SKU-Depot Disaggregated", "Historical Baseline"],
        axisLabel: { color: "#17171c", fontSize: 10, fontFamily: "Inter, sans-serif" },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "WAPE % (Lower is better)",
        nameTextStyle: { color: "#75758a", fontSize: 9 },
        axisLabel: { formatter: "{value}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          name: "RIOT RADAR S&OP",
          type: "bar",
          data: [natWape, locWape, 17.2],
          itemStyle: { color: "#1863dc", borderRadius: [2, 2, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}%", color: "#17171c", fontSize: 10, fontFamily: "JetBrains Mono, monospace", fontWeight: 600 },
        },
        {
          name: "Naive Benchmark",
          type: "bar",
          data: [naiveWape, 22.4, 30.0],
          itemStyle: { color: "#d9d9dd", borderRadius: [2, 2, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}%", color: "#75758a", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
      ],
    };
  }, [forecastAccuracy]);

  // CHART 6: FORECAST ERROR AND BIAS OVER TIME
  const forecastErrorTrendOption = React.useMemo(() => {
    const xData = vintageTrend?.labels?.length
      ? vintageTrend.labels
      : ["W14", "W15", "W16", "W17", "W18 (Current)"];
    const wapeData = vintageTrend?.wape_series?.length
      ? vintageTrend.wape_series
      : [19.2, 16.5, 14.1, 11.8, 10.7];
    const biasData = vintageTrend?.bias_series?.length
      ? vintageTrend.bias_series
      : [4.8, 3.2, 1.9, 0.4, -0.6];
    const naiveData = vintageTrend?.naive_wape_series?.length
      ? vintageTrend.naive_wape_series
      : [23.5, 20.9, 19.3, 17.1, 12.3];

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#17171c",
        borderColor: "#000000",
        borderWidth: 1,
        textStyle: { color: "#ffffff", fontSize: 11, fontFamily: "Inter, sans-serif" },
        formatter: (params: any) => {
          let s = `<div style="font-weight:600; color:#ffffff;">Vintage: ${params[0].name}</div>`;
          params.forEach((p: any) => {
            s += `<div style="color:#eeece7;">${p.marker} ${p.seriesName}: <b style="color:#ffffff;">${p.value}%</b></div>`;
          });
          return s;
        },
      },
      legend: {
        data: ["Forecast WAPE %", "Naive Benchmark %", "Forecast Bias %"],
        textStyle: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 30, right: 45, bottom: 25, left: 45 },
      xAxis: {
        type: "category",
        data: xData,
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif", interval: "auto" },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: [
        {
          type: "value",
          name: "WAPE %",
          nameTextStyle: { color: "#75758a", fontSize: 9 },
          axisLabel: { formatter: "{value}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
          splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        },
        {
          type: "value",
          name: "Bias %",
          nameTextStyle: { color: "#75758a", fontSize: 9 },
          axisLabel: { formatter: "{value}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "Forecast WAPE %",
          type: "line",
          smooth: true,
          data: wapeData,
          lineStyle: { color: "#1863dc", width: 2 },
          itemStyle: { color: "#1863dc" },
        },
        {
          name: "Naive Benchmark %",
          type: "line",
          smooth: true,
          data: naiveData,
          lineStyle: { color: "#94a3b8", width: 1.5, type: "dotted" },
          itemStyle: { color: "#94a3b8" },
        },
        {
          name: "Forecast Bias %",
          type: "line",
          yAxisIndex: 1,
          smooth: true,
          data: biasData,
          lineStyle: { color: "#003c33", width: 2, type: "dashed" },
          itemStyle: { color: "#003c33" },
        },
      ],
    };
  }, [vintageTrend]);

  const handlePulpParamChange = async (startCover: number, tgtCover: number, weeklyBuild: number, rate: number) => {
    setPulpStartingCover(startCover);
    setPulpTargetCover(tgtCover);
    setPulpWeeklyBuildKg(weeklyBuild);
    setPulpHoldingCostRate(rate);
    try {
      const res = await api.getPulpBuildTimeline(startCover, tgtCover, weeklyBuild, rate);
      setPulpTimeline(res);
    } catch (e) {
      console.error("Failed to update pulp timeline:", e);
    }
  };

  // CHART: NATIONAL FORECAST ACCURACY VS SKU-DEPOT FORECAST ERROR (VISUALIZATION 2)
  const nationalVsLocalForecastOption = React.useMemo(() => {
    if (!forecastAccuracy) return {};

    const natWape = forecastAccuracy.national_panel.wape_pct;
    const localWape = forecastAccuracy.sku_depot_panel.wape_pct;
    const natBiasAbs = Math.abs(forecastAccuracy.national_panel.bias_pct);
    const localMeanAbsBias = forecastAccuracy.sku_depot_panel.mean_absolute_bias_pct;

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
          let html = `<div style="font-weight:600; color:#ffffff; font-family:monospace; margin-bottom:3px;">
            ${params[0].name}
          </div>`;
          params.forEach((p: any) => {
            html += `<div style="color:#eeece7;">${p.marker} ${p.seriesName}: <b style="color:#ffffff;">${p.value}%</b></div>`;
          });
          if (params[0].name.includes("Bias")) {
            html += `<div style="color:#ffad9b; font-size:10px; margin-top:3px;">Signed National Bias: <b>${forecastAccuracy.national_panel.bias_pct}% (${forecastAccuracy.national_panel.bias_direction})</b></div>`;
            html += `<div style="color:#d97706; font-size:10px;">Cancelling Error Gap: <b>+${forecastAccuracy.sku_depot_panel.cancelling_error_gap_pct}%</b> masked at national level</div>`;
          }
          return html;
        },
      },
      legend: {
        data: ["National Aggregate Level", "SKU–Depot Local Disaggregated"],
        textStyle: { color: "#17171c", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 32, right: 20, bottom: 25, left: 45 },
      xAxis: {
        type: "category",
        data: ["WAPE Error %", "Mean Absolute Bias %"],
        axisLabel: { color: "#17171c", fontSize: 11, fontFamily: "Inter, sans-serif" },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: "{value}%", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
      },
      series: [
        {
          name: "National Aggregate Level",
          type: "bar",
          data: [natWape, natBiasAbs],
          itemStyle: { color: "#93939f", borderRadius: [2, 2, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}%", color: "#75758a", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
        {
          name: "SKU–Depot Local Disaggregated",
          type: "bar",
          data: [localWape, localMeanAbsBias],
          itemStyle: { color: "#1863dc", borderRadius: [2, 2, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}%", color: "#17171c", fontWeight: 600, fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        },
      ],
    };
  }, [forecastAccuracy]);

  // CHART: PRE-SUMMER PASSIONFRUIT PULP BUILD TIMELINE (VISUALIZATION 4)
  const pulpBuildTimelineOption = React.useMemo(() => {
    if (!pulpTimeline || !pulpTimeline.weekly_timeline) return {};

    const weeks = pulpTimeline.weekly_timeline.map(w => w.week_label);
    const coverDays = pulpTimeline.weekly_timeline.map(w => w.projected_cover_days);
    const targetRef = pulpTimeline.planning_parameters.target_buffer_cover_days;

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
          const wItem = pulpTimeline.weekly_timeline[idx];
          return `<div style="font-weight:600; color:#ffffff; font-family:monospace; margin-bottom:3px;">
            ${wItem.week_label} (Pre-Summer Planning)
          </div>
          <div style="color:#1863dc;">Projected Pulp Cover: <b>${wItem.projected_cover_days} days</b></div>
          <div style="color:#eeece7;">Pulp Inventory: <b>${wItem.pulp_stock_kg.toLocaleString()} kg</b></div>
          <div style="color:#93939f;">Planned Procurement: <b>${wItem.planned_weekly_procurement_kg.toLocaleString()} kg</b></div>
          <div style="color:${wItem.is_target_achieved ? '#003c33' : '#d97706'}; font-size:10px; margin-top:2px;">
            Target Buffer: ${targetRef}d (${wItem.is_target_achieved ? 'TARGET ACHIEVED' : 'BUILDING BUFFER'})
          </div>`;
        },
      },
      legend: {
        data: ["Projected Pulp Cover (Days)"],
        textStyle: { color: "#17171c", fontSize: 10, fontFamily: "Inter, sans-serif" },
        top: 0,
      },
      grid: { top: 35, right: 35, bottom: 30, left: 45 },
      xAxis: {
        type: "category",
        data: weeks,
        axisLabel: { color: "#616161", fontSize: 10, fontFamily: "Inter, sans-serif", interval: "auto", hideOverlap: true },
        axisLine: { lineStyle: { color: "#d9d9dd" } },
      },
      yAxis: {
        type: "value",
        name: "Days of Cover",
        nameTextStyle: { color: "#75758a", fontSize: 9 },
        axisLabel: { formatter: "{value}d", color: "#616161", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
        splitLine: { lineStyle: { color: "#f2f2f2", type: "dashed" } },
        min: 10,
        max: Math.max(30, targetRef + 6),
      },
      series: [
        {
          name: "Projected Pulp Cover (Days)",
          type: "line",
          data: coverDays,
          smooth: true,
          lineStyle: { color: "#1863dc", width: 2.5 },
          itemStyle: { color: "#1863dc" },
          areaStyle: {
            color: "rgba(24, 99, 220, 0.12)",
          },
          markLine: {
            silent: true,
            data: [
              {
                yAxis: targetRef,
                lineStyle: { color: "#0d9488", type: "dashed", width: 2 },
                label: { formatter: `Target Buffer: ${targetRef}d (21d Closure + 3d Transit)`, color: "#0d9488", position: "middle" },
              },
              {
                yAxis: 21.0,
                lineStyle: { color: "#d97706", type: "dotted", width: 1.5 },
                label: { formatter: "Highway Closure: 21d Outage", color: "#d97706", position: "start" },
              },
            ],
          },
        },
      ],
    };
  }, [pulpTimeline]);

  return (
    <div className="space-y-5 pb-8">
      {/* 1. TOP HEADER & HEALTH RIBBON */}
      <section className="space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-cohere-hairline pb-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-cohere-primary">
              National Operations Control Tower
            </h1>
            <p className="text-xs text-cohere-slate mt-0.5">
              Multi-echelon demand sensing, live inventory cover telemetry, and inter-depot rebalancing governance.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={loadData}
              className="button-pill-outline text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-cohere-action-blue" : ""}`} />
              <span>Telemetry Sync</span>
            </button>
          </div>
        </div>

        {/* 5-MODULE HEALTH RIBBON */}
        {ribbon && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
            {Object.entries(ribbon).map(([modName, modData]) => {
              return (
                <div
                  key={modName}
                  className="p-3 rounded-xs border border-cohere-hairline bg-white shadow-card-flat flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-cohere-slate">
                      {modName}
                    </span>
                    <span className="badge-neutral">[{modData.rag_status}]</span>
                  </div>
                  <div className="my-1.5 text-xs font-semibold text-cohere-primary line-clamp-2 leading-tight">
                    {modData.reason}
                  </div>
                  <div className="text-[10px] font-mono text-cohere-slate flex items-center justify-between border-t border-cohere-hairline pt-1 mt-1">
                    <span>ACTION:</span>
                    <span className="text-cohere-primary font-medium truncate ml-1">{modData.action_required}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* VISUALIZATION 4: PRE-SUMMER PASSIONFRUIT PULP BUILD TIMELINE (EXPANDABLE SECTION BENEATH HEALTH MODULES) */}
      <section className="bg-white border border-cohere-hairline rounded-sm overflow-hidden shadow-card-flat">
        <button
          onClick={() => setShowPulpTimeline(!showPulpTimeline)}
          className="w-full p-3.5 flex items-center justify-between text-left hover:bg-cohere-soft-stone/40 transition-colors border-b border-cohere-hairline"
        >
          <div className="flex items-center space-x-2">
            <span className="font-mono font-medium text-xs text-cohere-primary uppercase tracking-wider">
              Strategic Bottleneck — Pre-Summer Passionfruit Pulp Build Timeline
            </span>
          </div>
          <div className="flex items-center space-x-2 text-xs text-cohere-slate font-mono">
            <span>{pulpTimeline?.weekly_timeline ? `${pulpTimeline.weekly_timeline.length} WEEKS TO MARCH` : "8 WEEKS TO MARCH"}</span>
            {showPulpTimeline ? <ChevronDown className="w-4 h-4 text-cohere-slate" /> : <ChevronRight className="w-4 h-4 text-cohere-slate" />}
          </div>
        </button>

        {showPulpTimeline && (
          <div className="p-4 bg-cohere-bg/50 space-y-4">

            {/* Configurable planning parameters */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-sm bg-white border border-cohere-hairline shadow-card-flat space-y-1">
                <label className="text-[10px] font-mono uppercase tracking-wider text-cohere-slate block">
                  Starting Pulp Cover (Days)
                </label>
                <div className="flex items-center space-x-2">
                  <input
                    type="range"
                    min="7"
                    max="21"
                    step="1"
                    value={pulpStartingCover}
                    onChange={(e) => handlePulpParamChange(Number(e.target.value), pulpTargetCover, pulpWeeklyBuildKg, pulpHoldingCostRate)}
                    className="w-full accent-cohere-action-blue"
                  />
                  <span className="font-mono font-semibold text-xs text-cohere-primary w-10 text-right">{pulpStartingCover}d</span>
                </div>
                <div className="text-[9.5px] font-mono text-cohere-slate">Case baseline: 14d (2 wks)</div>
              </div>

              <div className="p-3 rounded-sm bg-white border border-cohere-hairline shadow-card-flat space-y-1">
                <label className="text-[10px] font-mono uppercase tracking-wider text-cohere-slate block">
                  Target Buffer Cover (Days)
                </label>
                <div className="flex items-center space-x-2">
                  <input
                    type="range"
                    min="18"
                    max="35"
                    step="1"
                    value={pulpTargetCover}
                    onChange={(e) => handlePulpParamChange(pulpStartingCover, Number(e.target.value), pulpWeeklyBuildKg, pulpHoldingCostRate)}
                    className="w-full accent-cohere-action-blue"
                  />
                  <span className="font-mono font-semibold text-xs text-cohere-primary w-10 text-right">{pulpTargetCover}d</span>
                </div>
                <div className="text-[9.5px] font-mono text-cohere-slate">21d Closure + 3d Transit = 24d</div>
              </div>

              <div className="p-3 rounded-sm bg-white border border-cohere-hairline shadow-card-flat space-y-1">
                <label className="text-[10px] font-mono uppercase tracking-wider text-cohere-slate block">
                  Weekly Build-Up (Kg/Wk)
                </label>
                <div className="flex items-center space-x-2">
                  <input
                    type="range"
                    min="5000"
                    max="35000"
                    step="1000"
                    value={pulpWeeklyBuildKg}
                    onChange={(e) => handlePulpParamChange(pulpStartingCover, pulpTargetCover, Number(e.target.value), pulpHoldingCostRate)}
                    className="w-full accent-cohere-action-blue"
                  />
                  <span className="font-mono font-semibold text-xs text-cohere-primary w-14 text-right">{(pulpWeeklyBuildKg / 1000).toFixed(0)}k kg</span>
                </div>
                <div className="text-[9.5px] font-mono text-cohere-slate">Procurement allocation rate</div>
              </div>

              <div className="p-3 rounded-sm bg-white border border-cohere-hairline shadow-card-flat space-y-1">
                <label className="text-[10px] font-mono uppercase tracking-wider text-cohere-slate block">
                  Cold Storage Holding Cost
                </label>
                <div className="flex items-center space-x-2">
                  <input
                    type="range"
                    min="5"
                    max="30"
                    step="0.5"
                    value={pulpHoldingCostRate}
                    onChange={(e) => handlePulpParamChange(pulpStartingCover, pulpTargetCover, pulpWeeklyBuildKg, Number(e.target.value))}
                    className="w-full accent-cohere-action-blue"
                  />
                  <span className="font-mono font-semibold text-xs text-cohere-primary w-14 text-right">₹{pulpHoldingCostRate.toFixed(1)}/kg</span>
                </div>
                <div className="text-[9.5px] font-mono text-cohere-slate">₹/kg/month commercial refrigerated</div>
              </div>
            </div>

            {/* Chart + Financial Comparative Strip */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 p-3.5 rounded-sm bg-white border border-cohere-hairline shadow-card-flat space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] font-mono font-medium text-cohere-primary uppercase">
                    Weekly Cover Trajectory vs 24-Day Target Buffer
                  </div>
                  <div className="flex items-center space-x-3 text-[10px] font-mono">
                    <span className="text-cohere-action-blue flex items-center space-x-1">
                      <span className="w-2.5 h-0.5 bg-cohere-action-blue inline-block"></span>
                      <span>Projected Cover</span>
                    </span>
                    <span className="text-cohere-deep-green flex items-center space-x-1">
                      <span className="w-2.5 h-0.5 border-t border-dashed border-cohere-deep-green inline-block"></span>
                      <span>24d Target Buffer</span>
                    </span>
                    <span className="text-amber-600 flex items-center space-x-1">
                      <span className="w-2.5 h-0.5 border-t border-dotted border-amber-600 inline-block"></span>
                      <span>21d Closure Duration</span>
                    </span>
                  </div>
                </div>
                <div className="h-56 w-full">
                  <EChart option={pulpBuildTimelineOption} height={220} />
                </div>
              </div>

              {/* Trade-off Financial Comparison Card */}
              <div className="p-4 rounded-sm bg-white border border-cohere-hairline shadow-card-flat flex flex-col justify-between space-y-3">
                <div>
                  <div className="text-[11px] font-mono font-medium text-cohere-primary uppercase tracking-wider mb-2">
                    Strategic Trade-Off Assessment
                  </div>
                  <div className="space-y-2.5">
                    <div className="p-2.5 rounded-xs bg-cohere-soft-stone/50 border border-cohere-hairline">
                      <div className="text-[10px] font-mono text-cohere-slate">ADDITIONAL BUFFER REQUIRED</div>
                      <div className="text-base font-semibold font-mono text-cohere-primary mt-0.5">
                        {pulpTimeline?.planning_parameters.required_additional_buffer_kg.toLocaleString() || "123,200"} kg
                        <span className="text-xs text-cohere-slate font-normal ml-1">
                          (+{(pulpTimeline?.planning_parameters.target_buffer_cover_days ?? 24) - (pulpTimeline?.planning_parameters.starting_cover_days ?? 14)} days)
                        </span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-xs bg-cohere-soft-stone/50 border border-cohere-hairline">
                      <div className="text-[10px] font-mono text-cohere-slate">BUFFER HOLDING COST (3 MONTHS)</div>
                      <div className="text-base font-semibold font-mono text-cohere-action-blue mt-0.5">
                        {pulpTimeline?.financial_comparison.estimated_buffer_holding_cost_inr_cr !== null && pulpTimeline?.financial_comparison.estimated_buffer_holding_cost_inr_cr !== undefined
                          ? `₹${pulpTimeline.financial_comparison.estimated_buffer_holding_cost_inr_cr.toFixed(2)} Cr`
                          : "Data unavailable"}
                        <span className="text-[10px] text-cohere-slate font-normal ml-1">(@ ₹{pulpHoldingCostRate}/kg/mo)</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-xs bg-cohere-soft-stone/50 border border-cohere-hairline">
                      <div className="text-[10px] font-mono text-cohere-slate">HISTORICAL EMERGENCY AIR FREIGHT</div>
                      <div className="text-base font-semibold font-mono text-cohere-error mt-0.5">
                        ₹{(pulpTimeline?.financial_comparison.historical_air_freight_reference_inr_cr ?? 3.20).toFixed(2)} Cr
                        <span className="text-[10px] text-cohere-slate font-normal ml-1">(Case Baseline)</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-xs bg-emerald-50 border border-emerald-200">
                  <div className="text-[10px] font-mono font-semibold text-emerald-800 uppercase tracking-wide">
                    NET AVOIDED COST / MARGIN PROTECTED
                  </div>
                  <div className="text-lg font-bold font-mono text-cohere-primary mt-0.5">
                    ₹{(pulpTimeline?.financial_comparison.net_avoided_exposure_inr_cr ?? 3.01).toFixed(2)} Cr
                  </div>
                  <div className="text-[9.5px] text-cohere-body-muted mt-1">
                    Holding cost represents {pulpTimeline?.financial_comparison.estimated_buffer_holding_cost_inr_cr ? ((pulpTimeline.financial_comparison.estimated_buffer_holding_cost_inr_cr / 3.20) * 100).toFixed(1) : "5.9"}% of emergency freight exposure. 16.8x ROI.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 2. EXACTLY SIX NATIONAL KPI CARDS (Clean Institutional Voice) */}
      <section className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {/* KPI 1 */}
        <div className="bg-white border border-cohere-hairline p-3.5 rounded-xs shadow-card-flat flex flex-col justify-between">
          <div className="text-[10px] font-mono font-medium uppercase tracking-widest text-cohere-slate">
            Depots at Risk
          </div>
          <div className="my-1 text-2xl font-bold font-mono text-cohere-primary tracking-tight">
            {kpis?.depots_at_risk || "4"} <span className="text-xs font-normal text-cohere-slate">/ 9</span>
          </div>
          <div className="text-[10px] font-mono text-cohere-slate">Cover &lt; 7 days</div>
        </div>

        {/* KPI 2 */}
        <div className="bg-white border border-cohere-hairline p-3.5 rounded-xs shadow-card-flat flex flex-col justify-between">
          <div className="text-[10px] font-mono font-medium uppercase tracking-widest text-cohere-slate">
            Forecast WAPE
          </div>
          <div className="my-1 text-2xl font-bold font-mono text-cohere-primary tracking-tight">
            {kpis?.forecast_wape_pct || "10.7"}
          </div>
          <div className="text-[10px] font-mono text-cohere-slate flex items-center space-x-1">
            <TrendingDown className="w-3 h-3 text-cohere-slate inline" />
            <span>vs Naive {kpis?.naive_benchmark_wape_pct || "22.4"}%</span>
          </div>
        </div>

        {/* KPI 3 */}
        <div className="bg-white border border-cohere-hairline p-3.5 rounded-xs shadow-card-flat flex flex-col justify-between">
          <div className="text-[10px] font-mono font-medium uppercase tracking-widest text-cohere-slate">
            Projected Shortage
          </div>
          <div className="my-1 text-2xl font-bold font-mono text-cohere-primary tracking-tight">
            {kpis?.projected_shortage_bottles ? Math.round(kpis.projected_shortage_bottles / 100000).toLocaleString() : "34.3"} <span className="text-xs font-normal text-cohere-slate">L btls</span>
          </div>
          <div className="text-[10px] font-mono text-cohere-slate">21-day forward burn</div>
        </div>

        {/* KPI 4 */}
        <div className="bg-white border border-cohere-hairline p-3.5 rounded-xs shadow-card-flat flex flex-col justify-between">
          <div className="text-[10px] font-mono font-medium uppercase tracking-widest text-cohere-slate">
            Transfer Opportunities
          </div>
          <div className="my-1 text-2xl font-bold font-mono text-cohere-primary tracking-tight">
            {kpis?.transfer_opportunities_count || "9"} <span className="text-xs font-normal text-cohere-slate">lanes</span>
          </div>
          <div className="text-[10px] font-mono text-cohere-slate">Donor cover &ge; 21d</div>
        </div>

        {/* KPI 5 */}
        <div className="bg-white border border-cohere-hairline p-3.5 rounded-xs shadow-card-flat flex flex-col justify-between">
          <div className="text-[10px] font-mono font-medium uppercase tracking-widest text-cohere-slate">
            Detection Lead Time
          </div>
          <div className="my-1 text-2xl font-bold font-mono text-cohere-primary tracking-tight">
            +{kpis?.detection_lead_time_days || "17"} <span className="text-xs font-normal text-cohere-slate">days</span>
          </div>
          <div className="text-[10px] font-mono text-cohere-slate">Ahead of spreadsheet</div>
        </div>

        {/* KPI 6 */}
        <div className="bg-white border border-cohere-hairline p-3.5 rounded-xs shadow-card-flat flex flex-col justify-between">
          <div className="text-[10px] font-mono font-medium uppercase tracking-widest text-cohere-slate">
            Pending Decisions
          </div>
          <div className="my-1 text-2xl font-bold font-mono text-cohere-primary tracking-tight">
            {kpis?.pending_decisions_count || "3"} <span className="text-xs font-normal text-cohere-slate">tickets</span>
          </div>
          <div className="text-[10px] font-mono text-cohere-slate">Awaiting COO Approval</div>
        </div>
      </section>

      {/* 3. CHARTS ROW 1: HEATMAP & RISK MATRIX */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* CHART 1: FLAVOUR X DEPOT HEATMAP */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-2.5">
            <div>
              <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider flex items-center space-x-2">
                <span>Chart 1 — SKU × Depot Allocation Heatmap</span>
              </div>
              <div className="text-[11px] text-cohere-slate mt-0.5">
                45 operational combinations across 9 regional depots.
              </div>
            </div>

            <div className="flex items-center space-x-1.5">
              <span className="text-[10px] font-mono text-cohere-slate uppercase">Metric:</span>
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="bg-cohere-soft-stone border border-cohere-hairline rounded-xs px-2.5 py-1 text-xs text-cohere-primary font-mono font-medium focus:outline-none"
              >
                <option value="allocation_gap">Allocation Gap (Bottles)</option>
                <option value="days_of_cover">Days of Cover (DoC)</option>
                <option value="wape_pct">Forecast WAPE %</option>
              </select>
            </div>
          </div>

          <div className="h-[380px] w-full">
            <EChart
              option={heatmapOption}
              height={380}
              loading={loading}
            />
          </div>
        </div>

        {/* CHART 2: DEMAND VS INVENTORY RISK MATRIX */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-2.5">
            <div>
              <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider flex items-center space-x-2">
                <span>Chart 2 — Demand vs. Inventory Risk Matrix</span>
              </div>
              <div className="text-[11px] text-cohere-slate mt-0.5">
                45 SKU–Depots plotted. Red quadrant = velocity &gt; 3,500 btls/d &amp; cover &lt; 7d.
              </div>
            </div>
            <div className="flex items-center space-x-2 text-[10px] font-mono text-cohere-slate">
              <span>[Critical &lt;7d]</span>
              <span>[Safe &ge;21d]</span>
            </div>
          </div>

          <div className="h-[370px] w-full">
            <EChart
              option={riskMatrixOption}
              height={370}
              loading={loading}
            />
          </div>
        </div>
      </section>

      {/* 4. CHARTS ROW 2: REBALANCING NETWORK & LOSS ATTRIBUTION */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* CHART 3: DEPOT REBALANCING NETWORK */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-2.5">
            <div>
              <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider">
                Chart 3 — Depot Rebalancing Network (Surplus-to-Shortage)
              </div>
              <div className="text-[11px] text-cohere-slate mt-0.5">
                Node-link topology: guaranteed donor cover &ge; 21d and 67d MT/QC gate.
              </div>
            </div>
            <span className="badge-ok">{proposals.length} FEASIBLE LANES</span>
          </div>

          <div className="h-80 w-full">
            <EChart
              option={rebalancingNetworkOption}
              height={320}
              loading={loading}
            />
          </div>
        </div>

        {/* CHART 4: HISTORICAL LOSS ATTRIBUTION & ROOT CAUSE */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-3 shadow-card-flat">
          <div className="flex items-center justify-between border-b border-cohere-hairline pb-2.5">
            <div>
              <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider">
                Chart 4 — Historical Loss Attribution (FY25 Baseline)
              </div>
              <div className="text-[11px] text-cohere-slate mt-0.5">
                Non-overlapping categories. Bottom-line exposure = ₹23.95 Cr vs ₹2.50 Cr budget.
              </div>
            </div>
            <span className="badge-critical">10.4% HURDLE RATE</span>
          </div>

          <div className="h-48 w-full">
            <EChart
              option={lossAttributionOption}
              height={190}
              loading={loading}
            />
          </div>

          {/* Root-cause interactive sliders */}
          <div className="p-3.5 rounded-xs bg-cohere-soft-stone border border-cohere-hairline space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono font-medium text-cohere-primary uppercase tracking-wider text-[11px]">
                Interactive Root-Cause Drivers (Sum = 100%)
              </span>
              <span className="font-mono text-cohere-primary font-semibold text-[11px]">
                Total: {sliderLate + sliderStale + sliderPulp}%
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="space-y-1">
                <div className="flex justify-between text-cohere-slate text-[11px]">
                  <span>1. Late Demand Detection (14–21d spreadsheet lag)</span>
                  <span className="font-mono font-semibold text-cohere-primary">{sliderLate}%</span>
                </div>
                <input
                  type="range"
                  min="30"
                  max="40"
                  value={sliderLate}
                  onChange={(e) => handleSliderChange("late_demand_detection", parseFloat(e.target.value))}
                  className="w-full accent-cohere-action-blue cursor-pointer h-1.5 bg-cohere-hairline rounded"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-cohere-slate text-[11px]">
                  <span>2. Stale Allocation &amp; Censored Stock-out Loop</span>
                  <span className="font-mono font-semibold text-cohere-primary">{sliderStale}%</span>
                </div>
                <input
                  type="range"
                  min="35"
                  max="45"
                  value={sliderStale}
                  onChange={(e) => handleSliderChange("stale_allocation_censored_loop", parseFloat(e.target.value))}
                  className="w-full accent-cohere-action-blue cursor-pointer h-1.5 bg-cohere-hairline rounded"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-cohere-slate text-[11px]">
                  <span>3. Single-Source Pulp &amp; Bottling Disruption</span>
                  <span className="font-mono font-semibold text-cohere-primary">{sliderPulp}%</span>
                </div>
                <input
                  type="range"
                  min="20"
                  max="30"
                  value={sliderPulp}
                  onChange={(e) => handleSliderChange("single_source_pulp_rationing", parseFloat(e.target.value))}
                  className="w-full accent-cohere-action-blue cursor-pointer h-1.5 bg-cohere-hairline rounded"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 5. CHARTS ROW 3: SUPPORTING ANALYTICS (DEMAND MIX & INVENTORY BANDS) */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* ADDITIONAL CHART A: SKU DEMAND MIX */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-2 shadow-card-flat">
          <div className="border-b border-cohere-hairline pb-2">
            <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider flex items-center space-x-1.5">
              <PieIcon className="w-3.5 h-3.5 text-cohere-slate" />
              <span>Summer Portfolio Demand Mix</span>
            </div>
            <div className="text-[10.5px] text-cohere-slate">9.6 Cr Finished Bottles Target Share</div>
          </div>
          <div className="h-44 w-full">
            <EChart option={skuDemandMixOption} height={175} />
          </div>
        </div>

        {/* ADDITIONAL CHART B: INVENTORY RISK BANDS */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-2 shadow-card-flat">
          <div className="border-b border-cohere-hairline pb-2">
            <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider flex items-center space-x-1.5">
              <BarChart2 className="w-3.5 h-3.5 text-cohere-slate" />
              <span>45-Grain Risk Distribution</span>
            </div>
            <div className="text-[10.5px] text-cohere-slate">SKU-Depots grouped by Days of Cover</div>
          </div>
          <div className="h-44 w-full">
            <EChart option={inventoryRiskDistOption} height={175} />
          </div>
        </div>

        {/* ACTIVE ALARMS FEED SUMMARY */}
        <div className="bg-white border border-cohere-hairline p-4 rounded-sm space-y-2 flex flex-col justify-between shadow-card-flat">
          <div className="border-b border-cohere-hairline pb-2 flex items-center justify-between">
            <div className="text-xs font-semibold text-cohere-primary uppercase tracking-wider flex items-center space-x-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-cohere-error" />
              <span>Active Exceptions ({alarms.length})</span>
            </div>
            <div className="flex items-center space-x-1">
              {["ALL", "CRITICAL", "WARNING"].map(s => (
                <button
                  key={s}
                  onClick={() => setAlarmFilterSev(s)}
                  className={`px-2.5 py-0.5 rounded-pill text-[9.5px] font-mono transition-colors ${alarmFilterSev === s ? "bg-cohere-primary text-white font-semibold" : "text-cohere-slate hover:text-cohere-primary"
                    }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5 overflow-y-auto max-h-36 pr-1">
            {filteredAlarms.slice(0, 3).map(a => (
              <div
                key={a.alarm_id}
                onClick={() => setSelectedAlarm(a)}
                className="p-2.5 rounded-xs bg-cohere-soft-stone/70 border border-cohere-hairline text-[11px] cursor-pointer hover:border-cohere-slate transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className={a.severity === "CRITICAL" ? "badge-critical" : "badge-warn"}>
                    [{a.severity}]
                  </span>
                  <span className="font-mono text-[9.5px] text-cohere-slate font-medium">{a.sku_id} @ {a.depot_id}</span>
                </div>
                <div className="font-semibold text-cohere-primary mt-1 truncate">{a.title}</div>
                <div className="text-[10px] text-cohere-body-muted truncate">{a.observed_value} vs {a.threshold_value}</div>
              </div>
            ))}
          </div>

          <button
            onClick={() => navigate("/ai-copilot")}
            className="w-full py-1.5 rounded-pill bg-cohere-soft-stone border border-cohere-hairline text-center text-xs text-cohere-primary font-medium hover:bg-cohere-hairline/60 transition-colors"
          >
            Open Exception Governance &rarr;
          </button>
        </div>
      </section>

      {/* 6. WEEKLY S&OP EXECUTIVE REPORT SECTION */}
      <section className="space-y-3 pt-2">
        {/* WEEKLY REPORT PREVIEW & PDF DOWNLOAD */}
        <div className="bg-white border border-cohere-hairline rounded-sm overflow-hidden shadow-card-flat">
          <button
            onClick={() => setShowWeeklyReport(!showWeeklyReport)}
            className="w-full p-3.5 flex items-center justify-between text-left hover:bg-cohere-soft-stone/40 transition-colors border-b border-cohere-hairline"
          >
            <div className="flex items-center space-x-2">
              <span className="font-mono font-medium text-xs text-cohere-primary uppercase">
                Weekly Supply Chain Intelligence Report (Publication-Grade 3-Page PDF)
              </span>
            </div>
            {showWeeklyReport ? <ChevronDown className="w-4 h-4 text-cohere-slate" /> : <ChevronRight className="w-4 h-4 text-cohere-slate" />}
          </button>

          {showWeeklyReport && (
            <div className="p-4 bg-cohere-bg/50 space-y-4">
              {/* VISUALIZATION 2: NATIONAL FORECAST ACCURACY VS SKU-DEPOT FORECAST ERROR */}
              <div className="p-3.5 rounded-xs bg-white border border-cohere-hairline shadow-card-flat space-y-3">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-cohere-hairline pb-2.5">
                  <div>
                    <div className="text-xs font-semibold text-cohere-primary">
                      National Forecast Accuracy vs SKU–Depot Forecast Error
                    </div>
                    <p className="text-[11px] text-cohere-slate mt-0.5">
                      Comparing aggregate national metrics against disaggregated local SKU–Depot performance.
                    </p>
                  </div>
                  <div className="text-[10px] font-mono text-cohere-slate">
                    EVALUATION WINDOW: 4-WEEK S&amp;OP CYCLE
                  </div>
                </div>

                {/* 2-Panel Metric Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* NATIONAL PANEL */}
                  <div className="p-3.5 rounded-xs bg-cohere-soft-stone/60 border border-cohere-hairline space-y-2">
                    <div className="flex items-center justify-between border-b border-cohere-hairline pb-1.5">
                      <span className="font-mono text-xs font-semibold text-cohere-primary uppercase tracking-wider">
                        National Panel (Aggregate)
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 pt-1">
                      <div>
                        <div className="text-[10px] font-mono uppercase text-cohere-slate">National WAPE</div>
                        <div className="text-xl font-bold font-mono text-cohere-primary mt-0.5">
                          {forecastAccuracy?.national_panel.wape_pct ?? "10.7"}%
                        </div>
                        <div className="text-[9.5px] font-mono text-cohere-slate font-medium">High aggregate accuracy</div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono uppercase text-cohere-slate">National Bias</div>
                        <div className="text-xl font-bold font-mono mt-0.5 text-cohere-primary">
                          {forecastAccuracy?.national_panel.bias_pct ?? "-10.7"}%
                        </div>
                        <div className="text-[9.5px] font-mono text-cohere-slate font-medium">
                          [{forecastAccuracy?.national_panel.bias_direction ?? "UNDERFORECASTING"}]
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* SKU-DEPOT PANEL */}
                  <div className="p-3.5 rounded-xs bg-cohere-soft-stone/60 border border-cohere-hairline space-y-2">
                    <div className="flex items-center justify-between border-b border-cohere-hairline pb-1.5">
                      <span className="font-mono text-xs font-semibold text-cohere-primary uppercase tracking-wider">
                        SKU–Depot Panel (Disaggregated)
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 pt-1">
                      <div>
                        <div className="text-[10px] font-mono uppercase text-cohere-slate">SKU–Depot WAPE</div>
                        <div className="text-xl font-bold font-mono text-cohere-primary mt-0.5">
                          {forecastAccuracy?.sku_depot_panel.wape_pct ?? "12.2"}%
                        </div>
                        <div className="text-[9.5px] font-mono text-cohere-slate">Cell-level error metric</div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono uppercase text-cohere-slate">Mean Absolute Bias</div>
                        <div className="text-xl font-bold font-mono text-cohere-primary mt-0.5">
                          {forecastAccuracy?.sku_depot_panel.mean_absolute_bias_pct ?? "12.2"}%
                        </div>
                        <div className="text-[9.5px] font-mono text-cohere-slate font-medium">
                          Uncancelling cell variance
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Side-by-Side Chart & Explanatory Callout */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-1">
                  <div className="lg:col-span-2 p-3 rounded-xs bg-cohere-soft-stone/30 border border-cohere-hairline">
                    <div className="text-[11px] font-mono font-medium text-cohere-primary uppercase mb-1">
                      Side-by-Side Macro vs Micro Error Metrics
                    </div>
                    <div className="h-48 w-full">
                      <EChart option={nationalVsLocalForecastOption} height={180} />
                    </div>
                  </div>

                  {/* Aggregation Fallacy Explanation */}
                  <div className="p-3.5 rounded-xs bg-cohere-soft-stone/30 border border-cohere-hairline flex flex-col justify-between space-y-2">
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-mono font-semibold text-cohere-primary uppercase tracking-wide">
                        [REGIONAL BIAS DYNAMICS]
                      </div>
                      <p className="text-[11px] text-cohere-slate leading-relaxed">
                        National forecast errors cancel out across depots and SKUs. For instance, surplus stock in Bangalore masks acute stock-outs in Delhi. A low national bias does not indicate accurate local forecasts.
                      </p>
                      <div className="p-2.5 rounded-xs bg-white border border-cohere-hairline shadow-card-flat text-[10.5px] font-mono space-y-1">
                        <div className="text-cohere-slate">MASKED ERROR GAP:</div>
                        <div className="text-cohere-primary font-bold text-sm">
                          +{forecastAccuracy?.sku_depot_panel.cancelling_error_gap_pct ?? "1.5"}% Cancelling Gap
                        </div>
                        <div className="text-[9.5px] text-cohere-slate">
                          Local absolute bias exceeds aggregate bias due to regional misallocation.
                        </div>
                      </div>
                    </div>
                    <div className="text-[9px] font-mono text-cohere-slate">
                      Note: Synthetic demo constructs calibrated to case constraints. Negative bias = underforecasting.
                    </div>
                  </div>
                </div>

                {/* Per-Flavor Breakdown Grid */}
                {forecastAccuracy?.sku_breakdown && (
                  <div className="overflow-x-auto border border-cohere-hairline rounded-xs">
                    <table className="w-full text-left border-collapse text-[11px] font-mono">
                      <thead>
                        <tr className="bg-cohere-soft-stone text-cohere-slate border-b border-cohere-hairline text-[10px] uppercase">
                          <th className="py-2 px-3">SKU</th>
                          <th className="py-2 px-3">Flavour Name</th>
                          <th className="py-2 px-3 text-right">National WAPE</th>
                          <th className="py-2 px-3 text-right">National Bias</th>
                          <th className="py-2 px-3 text-right">Local Mean |Bias|</th>
                          <th className="py-2 px-3 text-right">Cancelling Gap</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-cohere-hairline text-cohere-primary">
                        {forecastAccuracy.sku_breakdown.map((row) => (
                          <tr key={row.sku_id} className="hover:bg-cohere-soft-stone/40">
                            <td className="py-2 px-3 font-semibold text-cohere-action-blue">{row.sku_id}</td>
                            <td className="py-2 px-3 text-cohere-slate">{row.flavour}</td>
                            <td className="py-2 px-3 text-right">{row.national_wape_pct}%</td>
                            <td className={`py-2 px-3 text-right font-semibold ${row.national_bias_pct < 0 ? "text-cohere-error" : "text-amber-600"}`}>
                              {row.national_bias_pct > 0 ? `+${row.national_bias_pct}%` : `${row.national_bias_pct}%`}
                            </td>
                            <td className="py-2 px-3 text-right text-cohere-action-blue font-semibold">{row.mean_abs_depot_bias_pct}%</td>
                            <td className="py-2 px-3 text-right text-amber-700 font-mono font-medium">
                              +{row.cancelling_gap_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* CHART 5: FORECAST ACCURACY BENCHMARK */}
                <div className="p-3.5 rounded-xs bg-white border border-cohere-hairline shadow-card-flat space-y-1.5">
                  <div className="text-[11px] font-mono font-medium text-cohere-primary uppercase">
                    Chart 5 — Forecast Accuracy Benchmark (WAPE %)
                  </div>
                  <div className="text-[10px] text-cohere-slate">RIOT RADAR vs Naive Last-Week Actuals</div>
                  <div className="h-48 w-full">
                    <EChart option={forecastAccuracyOption} height={190} />
                  </div>
                </div>

                {/* CHART 6: FORECAST ERROR AND BIAS OVER TIME */}
                <div className="p-3.5 rounded-xs bg-white border border-cohere-hairline shadow-card-flat space-y-1.5">
                  <div className="text-[11px] font-mono font-medium text-cohere-primary uppercase">
                    Chart 6 — Forecast Error &amp; Bias Trajectory
                  </div>
                  <div className="text-[10px] text-cohere-slate">WAPE % (Blue) &amp; Bias % (Teal Dashed) across vintages</div>
                  <div className="h-48 w-full">
                    <EChart option={forecastErrorTrendOption} height={190} />
                  </div>
                </div>
              </div>

              {/* REPORT PREVIEW AND DOWNLOAD ACTION */}
              <div className="p-4 rounded-xs bg-white border border-cohere-hairline shadow-card-flat flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="text-xs font-semibold text-cohere-primary flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-cohere-action-blue" />
                    <span>Weekly Intelligence Briefing — Week 2026-W18</span>
                  </div>
                  <p className="text-[11.5px] text-cohere-slate">
                    {reportPreview?.executive_summary || "Multi-echelon exception briefing with automated ReportLab/Matplotlib charts and root-cause loss attribution."}
                  </p>
                </div>

                <button
                  onClick={handleDownloadReport}
                  disabled={generatingReport}
                  className="button-primary flex-shrink-0"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{generatingReport ? "Generating PDF..." : "Download 3-Page Executive PDF"}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ALARM DETAIL MODAL */}
      {selectedAlarm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-cohere-hairline rounded-md max-w-lg w-full p-6 space-y-4 shadow-card-elevated text-cohere-primary">
            <div className="flex items-center justify-between border-b border-cohere-hairline pb-2.5">
              <div className="flex items-center space-x-2">
                <span className={selectedAlarm.severity === "CRITICAL" ? "badge-critical" : "badge-warn"}>
                  [{selectedAlarm.severity}]
                </span>
                <span className="font-mono font-semibold text-sm text-cohere-primary">{selectedAlarm.alarm_id}</span>
              </div>
              <button
                onClick={() => setSelectedAlarm(null)}
                className="text-cohere-slate hover:text-cohere-primary text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="font-semibold text-cohere-primary text-sm">{selectedAlarm.title}</div>
                <div className="text-cohere-slate mt-1">{selectedAlarm.description}</div>
              </div>

              <div className="grid grid-cols-2 gap-2.5 p-3 rounded-xs bg-cohere-soft-stone border border-cohere-hairline font-mono text-[11px]">
                <div>SKU: <span className="text-cohere-action-blue font-medium">{selectedAlarm.sku_id}</span></div>
                <div>Depot: <span className="text-cohere-primary font-medium">{selectedAlarm.depot_id}</span></div>
                <div>Observed: <span className="text-cohere-error font-semibold">{selectedAlarm.observed_value}</span></div>
                <div>Threshold: <span className="text-cohere-slate">{selectedAlarm.threshold_value}</span></div>
              </div>

              <div className="p-3 rounded-xs bg-cohere-soft-stone/50 border border-cohere-hairline text-cohere-primary">
                <div className="font-semibold text-[10.5px] uppercase text-cohere-slate">Recommended Action:</div>
                <div className="mt-0.5 text-cohere-primary">{selectedAlarm.recommended_action}</div>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-cohere-hairline text-xs font-mono">
              <button
                onClick={() => {
                  handleAcknowledgeAlarm(selectedAlarm.alarm_id);
                  setSelectedAlarm(null);
                }}
                className="button-pill-outline text-xs"
              >
                Acknowledge (NEW &rarr; ACK)
              </button>
              <button
                onClick={() => {
                  handleResolveAlarm(selectedAlarm.alarm_id);
                  setSelectedAlarm(null);
                }}
                className="button-primary text-xs"
              >
                Resolve Exception
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
