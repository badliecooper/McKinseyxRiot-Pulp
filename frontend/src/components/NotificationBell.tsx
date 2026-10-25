import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { 
  Bell, 
  Check, 
  CheckCheck, 
  X, 
  AlertTriangle, 
  ExternalLink, 
  Clock, 
  ShieldAlert, 
  Truck,
  Layers,
  Sparkles
} from "lucide-react";
import { api } from "../api/client";
import { AlarmItem } from "../types";

export const NotificationBell: React.FC = () => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [alarms, setAlarms] = useState<AlarmItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [filterType, setFilterType] = useState<string>("ALL");
  const panelRef = useRef<HTMLDivElement>(null);

  const fetchAlarms = async () => {
    try {
      setLoading(true);
      const res = await api.getAlarms();
      setAlarms(res.alarms);
      setUnreadCount(res.unread_count || 0);
    } catch (e) {
      console.error("Failed to fetch alarms for notification bell:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlarms();
    // Poll alarms every 30 seconds
    const interval = setInterval(fetchAlarms, 30000);
    return () => clearInterval(interval);
  }, []);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleMarkRead = async (alarmId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.markAlarmRead(alarmId);
      setAlarms((prev) =>
        prev.map((a) => (a.alarm_id === alarmId ? { ...a, is_read: true } : a))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllAlarmsRead();
      setAlarms((prev) => prev.map((a) => ({ ...a, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAcknowledge = async (alarmId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.acknowledgeAlarm(alarmId, "Control-Tower-Bell");
      setAlarms((prev) =>
        prev.map((a) =>
          a.alarm_id === alarmId ? { ...a, status: "ACKNOWLEDGED", is_read: true } : a
        )
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error(err);
    }
  };

  const handleResolve = async (alarmId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.resolveAlarm(alarmId, "Resolved via Bell Notification Center");
      setAlarms((prev) =>
        prev.map((a) =>
          a.alarm_id === alarmId ? { ...a, status: "RESOLVED", is_read: true } : a
        )
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error(err);
    }
  };

  const handleNavigate = (alarm: AlarmItem) => {
    setIsOpen(false);
    if (alarm.alarm_type === "PENDING_APPROVAL" || alarm.recommendation_id) {
      navigate("/ai-copilot");
    } else if (alarm.sku_id && alarm.depot_id) {
      navigate(`/depot-explorer?depot=${alarm.depot_id}&sku=${alarm.sku_id}`);
    } else {
      navigate("/control-tower");
    }
  };

  const filteredAlarms = alarms.filter((a) => {
    if (filterType === "CRITICAL") return a.severity === "CRITICAL" && a.status !== "RESOLVED";
    if (filterType === "WARNING") return a.severity === "WARNING" && a.status !== "RESOLVED";
    if (filterType === "UNRESOLVED") return a.status !== "RESOLVED";
    if (filterType === "DELAYS") return a.alarm_type === "DELAYED_INBOUND" && a.status !== "RESOLVED";
    return true;
  });

  return (
    <div className="relative inline-block" ref={panelRef}>
      {/* Bell Icon Button */}
      <button
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) fetchAlarms();
        }}
        className="relative p-1.5 rounded-sm text-cohere-textSecondary hover:text-white hover:bg-cohere-surface/60 transition-colors focus:outline-none"
        title="Exception Alarms & Alerts"
        aria-label="Open Alerts Panel"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[15px] h-3.5 px-1 rounded-pill bg-scm-critical text-[9px] font-mono font-bold text-white leading-none border border-cohere-card">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Popover Alert Drawer (Cohere Console Style) */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 md:w-[440px] max-h-[580px] bg-cohere-card border border-cohere-border rounded-md shadow-card-elevated z-50 flex flex-col font-sans overflow-hidden">
          {/* Header */}
          <div className="p-3 border-b border-cohere-border bg-cohere-panel flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="font-mono font-semibold text-xs text-white uppercase tracking-wider">
                Operational Exception Alerts
              </span>
              {unreadCount > 0 && (
                <span className="badge-critical font-mono text-[9.5px]">
                  {unreadCount} UNREAD
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-[10px] font-mono text-cohere-muted hover:text-white flex items-center space-x-1"
                  title="Mark all active as read"
                >
                  <CheckCheck className="w-3 h-3" />
                  <span>Mark All Read</span>
                </button>
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="text-cohere-muted hover:text-white text-xs font-bold"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Filter Pills (Cohere button-pill style) */}
          <div className="px-3 py-1.5 bg-cohere-panel/60 border-b border-cohere-border flex items-center space-x-1.5 text-[10px] font-mono overflow-x-auto">
            {["UNRESOLVED", "CRITICAL", "WARNING", "DELAYS", "ALL"].map((f) => (
              <button
                key={f}
                onClick={() => setFilterType(f)}
                className={`px-2.5 py-0.5 rounded-pill transition-colors whitespace-nowrap text-[10px] ${
                  filterType === f
                    ? "bg-white text-cohere-black font-semibold"
                    : "text-cohere-textSecondary hover:text-white bg-cohere-surface/50 border border-cohere-border"
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Alert Items List */}
          <div className="flex-1 overflow-y-auto p-2.5 space-y-2 max-h-[420px]">
            {filteredAlarms.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono text-cohere-muted">
                No active alarms match filter [{filterType}].
              </div>
            ) : (
              filteredAlarms.map((a) => {
                const isCrit = a.severity === "CRITICAL";
                const isWarn = a.severity === "WARNING";
                const isUnread = !a.is_read && a.status !== "RESOLVED";
                const isResolved = a.status === "RESOLVED";
                const isAck = a.status === "ACKNOWLEDGED";

                return (
                  <div
                    key={a.alarm_id}
                    onClick={() => handleNavigate(a)}
                    className={`p-3 rounded-sm transition-all cursor-pointer ${
                      isUnread
                        ? "bg-white border border-cohere-hairline shadow-card-flat"
                        : "bg-cohere-soft-stone/50 border border-cohere-hairline hover:border-cohere-primary/40"
                    }`}
                  >
                    {/* Header line */}
                    <div className="flex items-center justify-between text-[10px] font-mono pb-1 border-b border-cohere-border/50">
                      <div className="flex items-center space-x-1.5">
                        <span className={isCrit ? "badge-critical" : isWarn ? "badge-warn" : "badge-ok"}>
                          [{a.severity}]
                        </span>
                        <span className="font-medium text-cohere-textSecondary">[{a.alarm_id}]</span>
                        {a.sku_id && a.depot_id && (
                          <span className="text-cohere-actionBlue font-medium">
                            {a.sku_id} @ {a.depot_id}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center space-x-1.5 text-cohere-muted">
                        <span>{a.created_at.slice(11, 16)}</span>
                        <span className={isResolved ? "badge-ok" : isAck ? "badge-gold" : "badge-warn"}>
                          [{a.status}]
                        </span>
                      </div>
                    </div>

                    {/* Title & Description */}
                    <div className="mt-1.5">
                      <div className="text-xs font-semibold text-white leading-snug">
                        {a.title}
                      </div>
                      <div className="text-[11px] text-cohere-textMuted mt-0.5 line-clamp-2">
                        {a.description}
                      </div>
                    </div>

                    {/* Telemetry Strip */}
                    <div className="mt-2 flex items-center justify-between text-[10px] font-mono p-1.5 rounded-xs bg-cohere-surface/60 border border-cohere-border text-cohere-textSecondary">
                      <div>
                        <span className="text-cohere-muted">Observed: </span>
                        <span className="font-semibold text-scm-critical">{a.observed_value}</span>
                      </div>
                      <div>
                        <span className="text-cohere-muted">Threshold: </span>
                        <span>{a.threshold_value}</span>
                      </div>
                    </div>

                    {/* Action Bar */}
                    <div className="mt-2 pt-1.5 border-t border-cohere-border/40 flex items-center justify-between text-[10.5px] font-mono">
                      <span className="text-cohere-actionBlue text-[10px] flex items-center space-x-1 hover:underline">
                        <span>Inspect in View</span>
                        <ExternalLink className="w-2.5 h-2.5 inline" />
                      </span>

                      <div className="flex items-center space-x-1.5" onClick={(e) => e.stopPropagation()}>
                        {isUnread && (
                          <button
                            onClick={(e) => handleMarkRead(a.alarm_id, e)}
                            className="px-2 py-0.5 rounded-pill bg-cohere-surface border border-cohere-border text-cohere-textSecondary hover:text-white text-[9.5px]"
                            title="Mark as Read"
                          >
                            Mark Read
                          </button>
                        )}
                        {!isResolved && !isAck && (
                          <button
                            onClick={(e) => handleAcknowledge(a.alarm_id, e)}
                            className="px-2.5 py-0.5 rounded-pill bg-cohere-surface border border-cohere-border text-white font-medium hover:border-cohere-borderLight text-[9.5px]"
                            title="Acknowledge (Does NOT approve recommendations)"
                          >
                            Acknowledge
                          </button>
                        )}
                        {!isResolved && (
                          <button
                            onClick={(e) => handleResolve(a.alarm_id, e)}
                            className="px-2.5 py-0.5 rounded-pill bg-scm-healthy text-white font-medium hover:bg-teal-600 text-[9.5px]"
                            title="Mark as Resolved"
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="p-2 border-t border-cohere-border bg-cohere-panel text-[9px] font-mono text-cohere-muted text-center">
            *Acknowledging an alarm acknowledges notice and never executes or approves recommendations.
          </div>
        </div>
      )}
    </div>
  );
};
