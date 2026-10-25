import React, { useState, useEffect } from "react";
import { 
  Bot, 
  Send, 
  CheckCircle, 
  XCircle, 
  Edit3, 
  RefreshCw, 
  ShieldCheck, 
  Layers, 
  Clock,
  ArrowRight,
  ShieldAlert,
  Sparkles,
  Check,
  X,
  FileCheck,
  Cpu,
  AlertTriangle
} from "lucide-react";
import { api } from "../api/client";
import { RebalancingProposal } from "../types";
import { MarkdownRenderer } from "../components/MarkdownRenderer";

export const AICopilot: React.FC = () => {
  const [operatingMode, setOperatingMode] = useState<string>("DETERMINISTIC_FALLBACK_ENGINE");
  const [recommendations, setRecommendations] = useState<RebalancingProposal[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [triggering, setTriggering] = useState<boolean>(false);
  const [filterStatus, setFilterStatus] = useState<string>("PENDING");

  // Chat state
  const [messages, setMessages] = useState<Array<{ 
    sender: "user" | "copilot"; 
    text: string; 
    mode?: string;
    evidence?: any;
    suggestedActions?: any[];
  }>>([
    {
      sender: "copilot",
      text: "Welcome to the RIOT RADAR SCM Copilot. I monitor 45 SKU–Depot combinations across 9 regional depots, grounded directly in live inventory, demand sensing, and rebalancing tools. Ask me to diagnose demand spikes, rank feasible surplus donors (>21d cover), explain supply bottlenecks, or review loss attribution.",
      mode: "Rule-based mode",
    },
  ]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);

  // Decision & Modal states
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [modifyingRec, setModifyingRec] = useState<RebalancingProposal | null>(null);
  const [modifiedQty, setModifiedQty] = useState<number>(0);
  const [rejectingRec, setRejectingRec] = useState<RebalancingProposal | null>(null);
  const [rejectionNote, setRejectionNote] = useState<string>("");

  const loadData = async () => {
    try {
      setLoading(true);
      const [hRes, recRes] = await Promise.all([
        api.getHealth(),
        api.getRecommendations(),
      ]);
      setOperatingMode(hRes.operating_mode === "DETERMINISTIC_FALLBACK_ENGINE" ? "Rule-based mode" : hRes.operating_mode);
      setRecommendations(recRes.recommendations);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerDetection = async () => {
    try {
      setTriggering(true);
      const res = await api.triggerDetection();
      setStatusMessage(`Detection Pipeline executed (Run: ${res.run_id}). Generated ${res.recommendations_generated.length} pending tickets.`);
      loadData();
    } catch (e: any) {
      alert("Pipeline trigger failed: " + e.message);
    } finally {
      setTriggering(false);
    }
  };

  const handleDecision = async (
    recId: string,
    decision: "APPROVE" | "MODIFY" | "REJECT",
    modQty?: number,
    notes?: string
  ) => {
    try {
      const res = await api.postApprovalDecision(recId, decision, "Executive-Planner-UI", modQty, notes);
      setStatusMessage(res.summary_message);
      loadData();
    } catch (e: any) {
      alert("Decision failed: " + e.message);
    }
  };

  const handleSendMessage = async (userText: string) => {
    if (!userText.trim()) return;

    setChatError(null);
    setLastFailedMessage(null);
    setInputMessage("");
    
    const newHistory = [...messages, { sender: "user" as const, text: userText }];
    setMessages(newHistory);

    try {
      setChatLoading(true);
      const res = await api.postCopilotChat(userText, undefined, undefined, newHistory);
      setMessages((prev) => [
        ...prev, 
        { 
          sender: "copilot", 
          text: res.reply, 
          mode: res.operating_mode === "DETERMINISTIC_FALLBACK_ENGINE" ? "Rule-based mode" : res.operating_mode,
          evidence: res.grounded_evidence,
          suggestedActions: res.suggested_actions
        }
      ]);
    } catch (err: any) {
      setChatError(err.message || "Failed to reach SCM Copilot service");
      setLastFailedMessage(userText);
      setMessages((prev) => [
        ...prev,
        { sender: "copilot", text: "Error connecting to SCM Copilot service: " + (err.message || "Network error. Click Retry to resubmit.") },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const filteredRecs = recommendations.filter(r => {
    if (filterStatus === "ALL") return true;
    return r.status === filterStatus;
  });

  const pendingCount = recommendations.filter(r => r.status === "PENDING").length;

  return (
    <div className="space-y-5 pb-8">
      {/* 1. TOP HEADER & OPERATIONAL MODE */}
      <section className="space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-cohere-hairline pb-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-cohere-primary">
              Governed Exception Management &amp; AI Copilot
            </h1>
            <p className="text-xs text-cohere-body-muted mt-0.5">
              LangGraph two-phase orchestration: agent proposes, humans approve. Zero autonomous execution without signature.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleTriggerDetection}
              disabled={triggering}
              className="button-primary flex items-center space-x-1.5 px-4 py-2 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
              <span>{triggering ? "Scanning..." : "Run 6-Node Detection Pipeline"}</span>
            </button>
          </div>
        </div>

        {/* Status Confirmation Banner */}
        {statusMessage && (
          <div className="p-3 rounded-sm bg-teal-50 border border-teal-200 text-xs font-mono text-teal-800 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FileCheck className="w-4 h-4 text-teal-600" />
              <span>{statusMessage}</span>
            </div>
            <button onClick={() => setStatusMessage(null)} className="text-sm font-bold hover:text-teal-950">✕</button>
          </div>
        )}
      </section>

      {/* 2. MAIN SPLIT VIEW: EXCEPTION TICKETS (LEFT) & CHAT COPILOT (RIGHT) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT COLUMN: IBP EXCEPTION TICKETS (7 COLS) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="bg-white border border-cohere-hairline rounded-sm p-5 space-y-4 shadow-card-flat">
            <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-cohere-primary tracking-wide uppercase font-mono">
                  Operational Recommendation Tickets
                </span>
                <span className="badge-warn">
                  {pendingCount} PENDING APPROVAL
                </span>
              </div>

              {/* Status filter tabs */}
              <div className="flex items-center space-x-1 text-xs">
                {["PENDING", "APPROVED", "REJECTED", "ALL"].map(st => (
                  <button
                    key={st}
                    onClick={() => setFilterStatus(st)}
                    className={`px-3 py-1 rounded-pill text-[11px] font-mono transition-colors ${
                      filterStatus === st 
                        ? "button-primary" 
                        : "button-pill-outline text-cohere-slate"
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>

            {filteredRecs.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono text-cohere-body-muted bg-cohere-soft-stone rounded-sm border border-cohere-hairline">
                No recommendation tickets found matching filter [{filterStatus}].
              </div>
            ) : (
              <div className="space-y-3.5 max-h-[640px] overflow-y-auto pr-1">
                {filteredRecs.map((rec) => {
                  const isPending = rec.status === "PENDING";
                  const isApproved = rec.status === "APPROVED";
                  const isRejected = rec.status === "REJECTED";

                  return (
                    <div 
                      key={rec.recommendation_id}
                      className="p-4 rounded-sm bg-white border border-cohere-hairline space-y-3 shadow-card-flat hover:border-cohere-primary/30 transition-colors"
                    >
                      {/* Ticket Header Bar */}
                      <div className="flex items-center justify-between border-b border-cohere-hairline pb-2 font-mono text-xs">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-cohere-primary">[{rec.recommendation_id}]</span>
                          <span className={rec.priority === "P1" ? "badge-critical" : "badge-warn"}>
                            [{rec.priority}]
                          </span>
                          <span className="text-cohere-body-muted text-[10px] font-medium">[{rec.module}]</span>
                        </div>
                        <span className={
                          isApproved 
                            ? "badge-ok" 
                            : isRejected 
                            ? "badge-critical" 
                            : "badge-warn"
                        }>
                          [{rec.status}]
                        </span>
                      </div>

                      {/* Bottleneck Diagnosis (1 line) */}
                      <div className="text-xs text-cohere-primary font-medium leading-relaxed">
                        {rec.diagnosis || `${rec.sku_id} @ ${rec.destination_depot_id}: stock-out imminent due to velocity surge; rebalance from surplus donor.`}
                      </div>

                      {/* Quantified Trade-Off Strip (4 Mini-Columns) */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 p-3 rounded-sm bg-cohere-soft-stone border border-cohere-hairline text-xs font-mono">
                        <div>
                          <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Action:</span>
                          <span className="font-bold text-cohere-primary">
                            Move {rec.quantity_bottles.toLocaleString()} btls
                          </span>
                        </div>
                        <div>
                          <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Lane &amp; Lead Time:</span>
                          <span className="text-cohere-primary font-medium">
                            {rec.lead_time_days}d transit + 1d apprv = <b>{rec.eta_days}d ETA</b>
                          </span>
                        </div>
                        <div>
                          <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Cost Impact:</span>
                          <span className="text-cohere-primary tabular-nums font-semibold">
                            ₹{Math.round(rec.cost_inr).toLocaleString()} (@ ₹1.50)
                          </span>
                        </div>
                        <div>
                          <span className="text-cohere-body-muted block text-[10px] uppercase font-semibold">Donor Cover:</span>
                          <span className="text-teal-700 font-semibold tabular-nums">
                            Post: {rec.donor_post_cover_days}d (&ge; 21d Safe)
                          </span>
                        </div>
                      </div>

                      {/* Selection Rationale & Rejected Alternatives */}
                      {(rec.selection_rationale || rec.rejected_alternatives) && (
                        <div className="p-2.5 rounded-sm bg-cohere-soft-stone/60 border border-cohere-hairline text-[11px] font-mono space-y-1">
                          {rec.selection_rationale && (
                            <div className="text-cohere-primary flex items-start space-x-1.5">
                              <span className="text-cohere-slate uppercase font-semibold flex-shrink-0">Selected:</span>
                              <span>{rec.selection_rationale}</span>
                            </div>
                          )}
                          {rec.rejected_alternatives && (
                            <div className="text-cohere-body-muted flex items-start space-x-1.5">
                              <span className="uppercase font-semibold flex-shrink-0">Rejected Alts:</span>
                              <span className="text-cohere-body-muted italic">{rec.rejected_alternatives}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Action Controls Bar */}
                      {isPending && (
                        <div className="flex items-center justify-end space-x-2 pt-2 border-t border-cohere-hairline font-mono text-xs">
                          <button
                            onClick={() => handleDecision(rec.recommendation_id, "APPROVE")}
                            className="button-primary px-3.5 py-1.5 text-xs font-semibold flex items-center space-x-1.5"
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>Approve Execution</span>
                          </button>
                          <button
                            onClick={() => {
                              setModifyingRec(rec);
                              setModifiedQty(rec.quantity_bottles);
                            }}
                            className="button-pill-outline px-3.5 py-1.5 text-xs font-mono text-cohere-primary flex items-center space-x-1.5"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                            <span>Modify Qty</span>
                          </button>
                          <button
                            onClick={() => {
                              setRejectingRec(rec);
                              setRejectionNote("");
                            }}
                            className="px-3.5 py-1.5 rounded-pill border border-cohere-error/40 text-cohere-error hover:bg-red-50 text-xs font-mono transition-colors flex items-center space-x-1.5"
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Reject with Note</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: AI COPILOT CHAT & TOOL GROUNDING (5 COLS - Signature Cohere Agent Console Card) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="bg-cohere-primary text-white rounded-sm p-5 flex flex-col h-[700px] border border-cohere-primary shadow-card-elevated">
            {/* Chat Header */}
            <div className="border-b border-[#2b2b36] pb-3 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="w-7 h-7 rounded-pill bg-[#23232b] border border-[#33333d] flex items-center justify-center text-cohere-action-blue">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-white tracking-wide uppercase font-mono">
                    Control Tower Copilot
                  </div>
                  <div className="text-[10px] text-cohere-slate">Grounded in Registered Tools</div>
                </div>
              </div>
              <span className="font-mono text-[10px] text-[#eeece7] border border-[#33333d] px-2 py-0.5 rounded-pill">
                [{operatingMode}]
              </span>
            </div>

            {/* Quick Prompt Suggestion Chips */}
            <div className="py-2.5 flex flex-wrap gap-1.5 border-b border-[#2b2b36]">
              {[
                "What surplus donors have >21 days of cover for PR-DP?",
                "Diagnose PR-DP at Mumbai",
                "Why can't co-packers solve the passionfruit disruption?",
                "Show breakdown of ₹46.08 Cr loss",
              ].map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleSendMessage(chip)}
                  className="text-[11px] px-3 py-1.5 rounded-pill bg-[#23232b] border border-[#33333d] text-[#eeece7] hover:bg-[#2d2d38] hover:border-cohere-action-blue transition-colors text-left"
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Chat Message History */}
            <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1 text-xs">
              {messages.map((m, idx) => {
                const isUser = m.sender === "user";
                return (
                  <div
                    key={idx}
                    className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[92%] p-3.5 rounded-md leading-relaxed ${
                        isUser
                          ? "bg-[#2d2d38] border border-[#3e3e4d] text-white font-normal text-xs"
                          : "bg-[#1c1c24] border border-[#2b2b36] text-[#eeece7]"
                      }`}
                    >
                      {isUser ? (
                        <div className="whitespace-pre-wrap">{m.text}</div>
                      ) : (
                        <MarkdownRenderer content={m.text} />
                      )}
                    </div>
                    <span className="text-[10px] font-mono text-[#8c8c99] mt-1 px-1">
                      {isUser ? "You (Planner)" : `RIOT RADAR Copilot [${m.mode || operatingMode}]`}
                    </span>
                  </div>
                );
              })}
              {chatLoading && (
                <div className="p-3 rounded-sm bg-[#23232b] border border-[#33333d] text-xs font-mono text-cohere-action-blue animate-pulse flex items-center space-x-2">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Executing registered tool telemetry...</span>
                </div>
              )}
              {chatError && lastFailedMessage && (
                <div className="p-3 rounded-sm bg-red-950/60 border border-red-500/40 text-xs font-mono flex items-center justify-between">
                  <span className="text-red-300">Error: {chatError}</span>
                  <button
                    onClick={() => handleSendMessage(lastFailedMessage)}
                    className="px-3 py-1 rounded-pill bg-white text-black font-semibold text-xs hover:bg-[#eeece7] transition-colors"
                  >
                    Retry Question
                  </button>
                </div>
              )}
            </div>

            {/* Chat Input Bar */}
            <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(inputMessage); }} className="pt-3 border-t border-[#2b2b36] flex space-x-2">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage(inputMessage);
                  }
                }}
                placeholder="Ask about allocation gaps, stock, or rebalancing (Press Enter)..."
                className="flex-1 bg-[#23232b] border border-[#3a3a48] rounded-pill px-4 py-2.5 text-xs text-white placeholder:text-[#8c8c99] focus:outline-none focus:border-cohere-action-blue font-mono min-w-0"
              />
              <button
                type="submit"
                disabled={chatLoading || !inputMessage.trim()}
                className="px-4 py-2.5 rounded-pill bg-white text-cohere-primary font-semibold hover:bg-[#eeece7] disabled:opacity-40 transition-colors flex items-center justify-center flex-shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* MODIFY QUANTITY MODAL */}
      {modifyingRec && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-cohere-hairline rounded-md max-w-sm w-full p-6 space-y-4 shadow-card-elevated text-cohere-primary">
            <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
              <span className="font-mono font-bold text-xs text-cohere-primary uppercase tracking-wider">
                MODIFY QUANTITY [{modifyingRec.recommendation_id}]
              </span>
              <button onClick={() => setModifyingRec(null)} className="text-cohere-body-muted hover:text-cohere-primary text-sm font-bold">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="text-cohere-body-muted">
                Original Quantity: <b className="text-cohere-primary font-mono tabular-nums">{modifyingRec.quantity_bottles.toLocaleString()} btls</b>
              </div>
              <div>
                <label className="block text-[10px] font-mono text-cohere-body-muted uppercase font-semibold mb-1">New Transfer Quantity:</label>
                <input
                  type="number"
                  value={modifiedQty}
                  onChange={(e) => setModifiedQty(parseInt(e.target.value) || 0)}
                  className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-sm px-3 py-2 text-xs font-mono text-cohere-primary focus:outline-none focus:border-cohere-action-blue tabular-nums"
                />
              </div>
              <div className="text-[11px] text-cohere-body-muted">
                New Transfer Cost: <span className="font-mono text-cohere-primary font-bold">₹{Math.round(modifiedQty * 1.5).toLocaleString()}</span> (@ ₹1.50/btl)
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-cohere-hairline font-mono text-xs">
              <button
                onClick={() => setModifyingRec(null)}
                className="button-pill-outline px-3 py-1.5 text-xs text-cohere-slate"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleDecision(modifyingRec.recommendation_id, "MODIFY", modifiedQty);
                  setModifyingRec(null);
                }}
                className="button-primary px-3.5 py-1.5 text-xs font-semibold"
              >
                Confirm Modification
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REJECT WITH NOTE MODAL */}
      {rejectingRec && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-cohere-hairline rounded-md max-w-sm w-full p-6 space-y-4 shadow-card-elevated text-cohere-primary">
            <div className="flex items-center justify-between border-b border-cohere-hairline pb-3">
              <span className="font-mono font-bold text-xs text-cohere-error uppercase tracking-wider">
                REJECT TICKET [{rejectingRec.recommendation_id}]
              </span>
              <button onClick={() => setRejectingRec(null)} className="text-cohere-body-muted hover:text-cohere-primary text-sm font-bold">✕</button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="text-cohere-body-muted">
                Action: <b className="text-cohere-primary">Move {rejectingRec.quantity_bottles.toLocaleString()} btls from {rejectingRec.origin_depot_id}</b>
              </div>
              <div>
                <label className="block text-[10px] font-mono text-cohere-body-muted uppercase font-semibold mb-1">Reason for Rejection:</label>
                <textarea
                  rows={3}
                  value={rejectionNote}
                  onChange={(e) => setRejectionNote(e.target.value)}
                  placeholder="e.g., Regional truck strike, local festival surge reserved, or manual depot override."
                  className="w-full bg-cohere-soft-stone border border-cohere-hairline rounded-sm p-3 text-xs text-cohere-primary placeholder:text-cohere-body-muted focus:outline-none focus:border-cohere-action-blue"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-cohere-hairline font-mono text-xs">
              <button
                onClick={() => setRejectingRec(null)}
                className="button-pill-outline px-3 py-1.5 text-xs text-cohere-slate"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleDecision(rejectingRec.recommendation_id, "REJECT", undefined, rejectionNote);
                  setRejectingRec(null);
                }}
                className="px-3.5 py-1.5 rounded-pill bg-cohere-error text-white font-semibold text-xs hover:bg-red-700 transition-colors"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
