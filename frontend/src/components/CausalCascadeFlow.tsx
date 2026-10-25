import React, { useState } from "react";
import { 
  Clock, 
  Layers, 
  AlertTriangle, 
  EyeOff, 
  TrendingDown, 
  Repeat, 
  ChevronRight, 
  Info, 
  CheckCircle2, 
  XCircle, 
  ArrowRight,
  ShieldCheck,
  FileText
} from "lucide-react";
import { CausalCascadeData, CausalCascadeNode } from "../types";

interface CausalCascadeFlowProps {
  data: CausalCascadeData | null;
  loading?: boolean;
}

const STAGE_ICONS: Record<string, React.ReactNode> = {
  late_demand_signal: <Clock className="w-4 h-4" />,
  stale_allocation: <Layers className="w-4 h-4" />,
  stock_out: <AlertTriangle className="w-4 h-4" />,
  censored_sales: <EyeOff className="w-4 h-4" />,
  underestimated_forecast: <TrendingDown className="w-4 h-4" />,
  repeated_stock_out: <Repeat className="w-4 h-4" />,
};

const STAGE_DATA_NATURE: Record<string, { label: string; badgeClass: string }> = {
  late_demand_signal: { label: "Measured Fact", badgeClass: "border-slate-300 text-slate-700 bg-slate-50" },
  stale_allocation: { label: "Simulated Policy", badgeClass: "border-blue-300 text-blue-700 bg-blue-50" },
  stock_out: { label: "Measured Fact", badgeClass: "border-red-300 text-red-700 bg-red-50" },
  censored_sales: { label: "Model Estimate", badgeClass: "border-purple-300 text-purple-700 bg-purple-50" },
  underestimated_forecast: { label: "Model Estimate", badgeClass: "border-amber-300 text-amber-700 bg-amber-50" },
  repeated_stock_out: { label: "Simulated Policy", badgeClass: "border-teal-300 text-teal-700 bg-teal-50" },
};

export const CausalCascadeFlow: React.FC<CausalCascadeFlowProps> = ({ data, loading }) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string>("late_demand_signal");

  if (loading || !data || !data.nodes || data.nodes.length === 0) {
    return (
      <div className="p-8 text-center text-xs font-mono text-cohere-body-muted bg-cohere-soft-stone rounded-sm border border-cohere-hairline">
        Loading operational cause-and-effect cascade telemetry...
      </div>
    );
  }

  const nodes = data.nodes;
  const activeNode = nodes.find((n) => n.id === selectedNodeId) || nodes[0];

  return (
    <div className="space-y-4">
      {/* 1. VISUAL FLOW PIPELINE (SVG CONNECTED GRAPH) */}
      <div className="relative overflow-x-auto pb-2">
        <div className="min-w-[860px] grid grid-cols-6 gap-2 relative">
          {nodes.map((node, idx) => {
            const isSelected = activeNode.id === node.id;
            const isMitigated = node.status === "MITIGATED";
            const icon = STAGE_ICONS[node.id] || <Info className="w-4 h-4" />;
            const nature = STAGE_DATA_NATURE[node.id] || { label: "Model Metric", badgeClass: "border-slate-300 text-slate-700" };

            return (
              <div key={node.id} className="relative flex flex-col">
                {/* Node Box */}
                <button
                  type="button"
                  onClick={() => setSelectedNodeId(node.id)}
                  className={`w-full text-left p-3 rounded-sm border transition-all flex flex-col justify-between h-[152px] ${
                    isSelected
                      ? "bg-white border-cohere-primary ring-2 ring-cohere-primary/20 shadow-md"
                      : isMitigated
                      ? "bg-white border-cohere-hairline hover:border-cohere-muted shadow-card-flat"
                      : "bg-red-50/20 border-red-200 hover:border-red-400 shadow-card-flat"
                  }`}
                >
                  {/* Top Bar: Icon + Step + Nature */}
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center space-x-1.5">
                      <div
                        className={`w-6 h-6 rounded flex items-center justify-center ${
                          isMitigated
                            ? "bg-teal-50 text-teal-800 border border-teal-200"
                            : "bg-red-50 text-red-800 border border-red-200"
                        }`}
                      >
                        {icon}
                      </div>
                      <span className="text-[10px] font-mono font-bold text-cohere-slate">
                        0{node.step_number}
                      </span>
                    </div>

                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded border uppercase tracking-wider ${nature.badgeClass}`}
                    >
                      {nature.label}
                    </span>
                  </div>

                  {/* Title & Short Desc */}
                  <div className="my-1">
                    <div className="text-xs font-bold text-cohere-primary truncate" title={node.title}>
                      {node.title}
                    </div>
                    <div className="text-[10px] text-cohere-body-muted line-clamp-2 leading-tight mt-0.5">
                      {node.short_desc}
                    </div>
                  </div>

                  {/* Metric Strip */}
                  <div className="pt-1.5 border-t border-cohere-hairline w-full flex items-center justify-between">
                    <div>
                      <span className="text-[9px] uppercase font-mono text-cohere-body-muted block">
                        {node.model_metric_label}
                      </span>
                      <span
                        className={`text-[11px] font-mono font-bold tabular-nums block ${
                          isMitigated ? "text-teal-700" : "text-red-700"
                        }`}
                      >
                        {node.model_metric_value}
                      </span>
                    </div>

                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold ${
                        isMitigated
                          ? "bg-teal-50 text-teal-800 border border-teal-200"
                          : "bg-red-50 text-red-800 border border-red-200"
                      }`}
                    >
                      [{isMitigated ? "MITIGATED" : "ACTIVE RISK"}]
                    </span>
                  </div>
                </button>

                {/* Connecting arrow to next node */}
                {idx < nodes.length - 1 && (
                  <div className="hidden lg:flex absolute -right-2 top-1/2 -translate-y-1/2 z-20 pointer-events-none items-center justify-center">
                    <div
                      className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold shadow-xs ${
                        isMitigated ? "bg-teal-700 text-white" : "bg-red-600 text-white"
                      }`}
                    >
                      ➔
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. DETAIL EVIDENCE INSPECTION DRAWER */}
      {activeNode && (
        <div className="p-4 rounded-sm bg-white border border-cohere-hairline shadow-card-flat space-y-3">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-2.5 border-b border-cohere-hairline gap-2">
            <div className="flex items-center space-x-2">
              <span className="font-mono text-xs font-bold text-cohere-primary">
                Stage {activeNode.step_number}: {activeNode.title}
              </span>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  activeNode.status === "MITIGATED"
                    ? "bg-teal-50 text-teal-800 border-teal-200 font-semibold"
                    : "bg-red-50 text-red-800 border-red-200 font-bold"
                }`}
              >
                [{activeNode.status}]
              </span>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                  STAGE_DATA_NATURE[activeNode.id]?.badgeClass || "border-slate-200 text-slate-700"
                }`}
              >
                {STAGE_DATA_NATURE[activeNode.id]?.label || "Operational Metric"}
              </span>
            </div>

            <div className="text-xs font-mono text-cohere-body-muted">
              {activeNode.model_metric_label}: <b className="text-cohere-primary">{activeNode.model_metric_value}</b>
            </div>
          </div>

          {/* 3-Column Diagnostic Details */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            {/* Col 1: Mathematical Calculation & Definition */}
            <div className="p-3 rounded-xs bg-cohere-soft-stone border border-cohere-hairline space-y-1.5">
              <div className="text-[10px] font-mono text-cohere-body-muted uppercase font-semibold flex items-center space-x-1">
                <FileText className="w-3 h-3 text-cohere-slate" />
                <span>Calculation &amp; Formula:</span>
              </div>
              <p className="text-[11px] text-cohere-primary font-mono leading-relaxed">
                {activeNode.supporting_calculation || "Formula based on calibrated network run-rates."}
              </p>
            </div>

            {/* Col 2: Grounding Evidence & Source Records */}
            <div className="p-3 rounded-xs bg-cohere-soft-stone border border-cohere-hairline space-y-1.5">
              <div className="text-[10px] font-mono text-cohere-body-muted uppercase font-semibold flex items-center space-x-1">
                <CheckCircle2 className="w-3 h-3 text-cohere-slate" />
                <span>POS &amp; Dark Store Grounding:</span>
              </div>
              <p className="text-[11px] text-cohere-primary leading-relaxed">
                {activeNode.evidence}
              </p>
            </div>

            {/* Col 3: Affected Depots & Prescribed Intervention */}
            <div className="p-3 rounded-xs bg-cohere-soft-stone border border-cohere-hairline space-y-1.5">
              <div className="text-[10px] font-mono text-cohere-body-muted uppercase font-semibold flex items-center space-x-1">
                <ShieldCheck className="w-3 h-3 text-teal-700" />
                <span>Intervention &amp; Mitigation Lever:</span>
              </div>
              <p className="text-[11px] text-teal-900 font-medium leading-relaxed">
                {activeNode.mitigation_lever}
              </p>
              {activeNode.affected_sku_depots && activeNode.affected_sku_depots.length > 0 && (
                <div className="pt-1.5 border-t border-cohere-hairline flex flex-wrap gap-1">
                  {activeNode.affected_sku_depots.map((sd, i) => (
                    <span
                      key={i}
                      className="px-1.5 py-0.5 rounded bg-white border border-cohere-hairline font-mono text-[9.5px] text-cohere-action-blue"
                    >
                      {sd}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Footnote */}
          <div className="text-[10.5px] font-mono text-cohere-body-muted pt-1 flex items-center justify-between border-t border-cohere-hairline">
            <span>{data.disclaimer}</span>
            <span className="text-cohere-slate">Click any stage above to inspect causal link</span>
          </div>
        </div>
      )}
    </div>
  );
};
