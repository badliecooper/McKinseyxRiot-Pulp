import React, { useState, useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { 
  Activity, 
  MapPin, 
  GitCompare, 
  Bot, 
  Clock, 
  Database,
  Cpu,
  Layers,
  Upload
} from "lucide-react";
import { api } from "../api/client";
import { NotificationBell } from "./NotificationBell";
import { UploadModal } from "./UploadModal";

export const Layout: React.FC = () => {
  const [operatingMode, setOperatingMode] = useState<string>("Rule-based mode");
  const [lastRefreshed, setLastRefreshed] = useState<string>("");
  const [uploadOpen, setUploadOpen] = useState<boolean>(false);
  const location = useLocation();

  useEffect(() => {
    api.getHealth()
      .then((res) => {
        setOperatingMode(res.operating_mode === "DETERMINISTIC_FALLBACK_ENGINE" ? "Rule-based mode" : res.operating_mode);
        setLastRefreshed(new Date().toLocaleTimeString("en-IN", { hour12: false }) + " IST");
      })
      .catch(() => {
        setOperatingMode("Rule-based mode");
        setLastRefreshed("OFFLINE");
      });
  }, [location.pathname]);

  const navItems = [
    { to: "/control-tower", label: "Control Tower", badge: "Grid", icon: Activity },
    { to: "/depot-explorer", label: "Depot Explorer", badge: "45 SKU-Depots", icon: MapPin },
    { to: "/scenario-replay", label: "Scenario Replay", badge: "Interventions", icon: GitCompare },
    { to: "/ai-copilot", label: "AI Copilot & Approval", badge: "Governed IBP", icon: Bot },
  ];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-cohere-bg font-sans text-cohere-primary antialiased selection:bg-cohere-action-blue selection:text-white">
      {/* 1. COHERE ANNOUNCEMENT BAR (From DESIGN.md) */}
      <div className="announcement-bar flex-shrink-0">
        <div className="flex items-center space-x-2 text-[10.5px]">
          <span className="font-semibold text-cohere-coral">[S&amp;OP CONTROL TOWER]</span>
          <span className="text-cohere-muted">|</span>
          <span className="text-white">PULP RIOT JUICE CO.</span>
          <span className="text-cohere-muted">|</span>
          <span className="text-cohere-soft-stone">VINTAGE 2026-W18 DEMAND SENSING</span>
          <span className="text-cohere-muted">|</span>
          <span className="text-white font-mono">45 SKU-DEPOT CELLS</span>
        </div>
        <div className="flex items-center space-x-3 text-[10.5px]">
          <span className="text-cohere-soft-stone font-mono">ENGINE: {operatingMode}</span>
          <span className="text-cohere-coral">●</span>
          <span className="text-cohere-muted font-mono">{lastRefreshed}</span>
        </div>
      </div>

      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* 2. PERSISTENT LEFT SIDEBAR (Cohere Mineral White Shell) */}
        <aside className="w-64 flex-shrink-0 flex flex-col border-r border-cohere-hairline bg-white select-none">
          {/* Brand Header */}
          <div className="p-4 border-b border-cohere-hairline bg-white">
            <div className="flex items-center space-x-2">
              <span className="font-mono font-bold text-[11px] tracking-widest text-white uppercase bg-cohere-primary px-2.5 py-1 rounded-xs">
                [PULP RIOT]
              </span>
            </div>
            <div className="mt-2 text-sm font-semibold text-cohere-primary tracking-tight flex items-center justify-between">
              <span>Pulp Riot Juice Co.</span>
              <span className="w-2 h-2 rounded-full bg-cohere-deep-green" title="System Live"></span>
            </div>
            <div className="text-[11px] text-cohere-slate mt-0.5">Autonomous S&amp;OP Command Center</div>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            <div className="px-2 pb-2 text-[10px] font-mono font-medium tracking-widest text-cohere-slate uppercase">
              OPERATIONAL VIEWS
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.to || (item.to === "/control-tower" && location.pathname === "/");
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={`flex items-center justify-between px-3 py-2 rounded-xs text-xs transition-colors duration-100 ${
                    isActive
                      ? "bg-cohere-soft-stone text-cohere-primary border-l-2 border-cohere-primary font-semibold"
                      : "text-cohere-body-muted hover:bg-cohere-soft-stone/60 hover:text-cohere-primary font-normal"
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon className={`w-3.5 h-3.5 ${isActive ? "text-cohere-primary" : "text-cohere-slate"}`} />
                    <span>{item.label}</span>
                  </div>
                  <span className={`text-[9.5px] font-mono px-1.5 py-0.5 rounded-xs ${
                    isActive 
                      ? "bg-cohere-primary text-white" 
                      : "text-cohere-slate bg-cohere-card-border"
                  }`}>
                    {item.badge}
                  </span>
                </NavLink>
              );
            })}
          </nav>
        </aside>

        {/* 3. MAIN CONTENT AREA */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-cohere-bg">
          {/* Top Header Bar */}
          <header className="h-12 flex-shrink-0 border-b border-cohere-hairline bg-white px-5 flex items-center justify-between">
            <div className="flex items-center space-x-3 text-xs">
              <span className="font-mono font-medium uppercase tracking-wider text-cohere-slate text-[10.5px]">
                OPERATIONS STATUS:
              </span>
              <span className="badge-ok flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cohere-deep-green inline-block"></span>
                <span>[ACTIVE]</span>
              </span>
              <span className="text-cohere-hairline">|</span>
              <div className="flex items-center space-x-1.5 text-cohere-body-muted text-[11px]">
                <Cpu className="w-3.5 h-3.5 text-cohere-slate" />
                <span className="font-mono text-cohere-slate font-medium text-[10.5px]">
                  [{operatingMode}]
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-3 text-xs text-cohere-slate">
              {/* Upload Data Button for Planning Team (Cohere Primary Pill Button) */}
              <button
                onClick={() => setUploadOpen(true)}
                className="button-primary text-xs"
                title="Upload daily Modern Trade / Quick Commerce sales CSV"
              >
                <Upload className="w-3 h-3 text-white" />
                <span>Upload Data</span>
              </button>

              {/* Notification Bell */}
              <NotificationBell />

              <span className="text-cohere-hairline">|</span>

              <div className="flex items-center space-x-1 font-mono text-[11px] text-cohere-body-muted hidden sm:flex">
                <Clock className="w-3.5 h-3.5 text-cohere-slate" />
                <span>Refreshed:</span>
                <span className="text-cohere-primary font-medium">{lastRefreshed}</span>
              </div>
              <span className="text-cohere-hairline hidden sm:inline">|</span>
              <div className="flex items-center space-x-1 text-cohere-slate font-mono text-[10.5px] hidden md:flex">
                <Database className="w-3.5 h-3.5 text-cohere-slate" />
                <span>CSV PERSISTENCE</span>
              </div>
            </div>
          </header>

          {/* Content Outlet */}
          <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
            <Outlet />
          </main>

          {/* Daily Data Upload Modal */}
          <UploadModal 
            isOpen={uploadOpen} 
            onClose={() => setUploadOpen(false)} 
            onUploadSuccess={() => window.location.reload()} 
          />
        </div>
      </div>
    </div>
  );
};
