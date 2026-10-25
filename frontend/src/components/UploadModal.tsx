import React, { useState, useRef } from "react";
import { 
  Upload, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  X, 
  RefreshCw, 
  Database,
  Calendar,
  Layers,
  Download,
  Copy
} from "lucide-react";
import { api } from "../api/client";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess?: () => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onUploadSuccess }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceChannel, setSourceChannel] = useState<string>("Quick Commerce");
  const [uploaderName, setUploaderName] = useState<string>("Lead S&OP Planner");
  const [previewRows, setPreviewRows] = useState<any[]>([]);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadResult, setUploadResult] = useState<any | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sampleCsvContent = 
`date,sku_id,depot_id,channel,observed_sales
2026-05-21,PR-DP,Depot-West-01,QC,28500
2026-05-21,PR-DP,Depot-North-01,QC,31200
2026-05-21,PR-MPB,Depot-East-01,MT,14800
2026-05-21,PR-GC,Depot-South-01,QC,19400
2026-05-21,PR-PP,Depot-North-02,MT,8200`;

  if (!isOpen) return null;

  const parseAndPreviewCsv = (file: File) => {
    setSelectedFile(file);
    setUploadResult(null);
    setValidationErrors([]);

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
      if (lines.length < 2) {
        setValidationErrors(["File contains no data rows."]);
        return;
      }

      const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
      const dateIdx = headers.findIndex(h => h.includes("date") || h === "day");
      const skuIdx = headers.findIndex(h => h.includes("sku") || h.includes("flavor") || h.includes("flavour"));
      const depotIdx = headers.findIndex(h => h.includes("depot") || h.includes("location"));
      const channelIdx = headers.findIndex(h => h.includes("channel"));
      const salesIdx = headers.findIndex(h => h.includes("sales") || h.includes("qty") || h.includes("quantity") || h.includes("bottles"));

      const errors: string[] = [];
      if (dateIdx === -1) errors.push("Missing 'date' column in CSV.");
      if (skuIdx === -1) errors.push("Missing 'sku_id' column in CSV.");
      if (depotIdx === -1) errors.push("Missing 'depot_id' column in CSV.");
      if (salesIdx === -1) errors.push("Missing 'observed_sales' column in CSV.");

      if (errors.length > 0) {
        setValidationErrors(errors);
        return;
      }

      const parsed: any[] = [];
      for (let i = 1; i < Math.min(lines.length, 12); i++) {
        const parts = lines[i].split(",").map(p => p.trim());
        if (parts.length < 4) continue;

        parsed.push({
          row: i,
          date: parts[dateIdx],
          sku: parts[skuIdx],
          depot: parts[depotIdx],
          channel: channelIdx !== -1 ? parts[channelIdx] : sourceChannel,
          sales: parts[salesIdx],
        });
      }

      setPreviewRows(parsed);
    };
    reader.readAsText(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      parseAndPreviewCsv(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      parseAndPreviewCsv(e.dataTransfer.files[0]);
    }
  };

  const handleCopySample = () => {
    navigator.clipboard.writeText(sampleCsvContent);
    alert("Sample CSV format copied to clipboard!");
  };

  const handleDownloadSample = () => {
    const blob = new Blob([sampleCsvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "riot_radar_sales_sample.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleSubmit = async () => {
    if (!selectedFile) return;

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("source_channel", sourceChannel);
      formData.append("uploader_name", uploaderName);

      const res = await api.uploadSalesCsv(formData);
      setUploadResult(res);

      if (res.status === "SUCCESS" && onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err: any) {
      setValidationErrors([err.message || "Failed to upload file"]);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-cohere-card border border-cohere-border rounded-md max-w-2xl w-full p-6 space-y-4 shadow-card-elevated font-sans text-cohere-textPrimary">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-cohere-border pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xs bg-cohere-surface border border-cohere-borderLight flex items-center justify-center text-white">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white tracking-tight uppercase">
                Ingest Daily Sales Telemetry
              </h2>
              <p className="text-[11px] text-cohere-textMuted mt-0.5">
                Modern Trade &amp; Quick Commerce partner CSV ingestion for demand sensing.
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-cohere-muted hover:text-white text-sm font-bold p-1"
          >
            ✕
          </button>
        </div>

        {/* Upload Form Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div>
            <label className="block text-[10.5px] font-mono text-cohere-muted uppercase mb-1">
              Sales Channel Source:
            </label>
            <select
              value={sourceChannel}
              onChange={(e) => setSourceChannel(e.target.value)}
              className="w-full bg-cohere-panel border border-cohere-border rounded-xs px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cohere-borderLight"
            >
              <option value="Quick Commerce">Quick Commerce (Zepto / Blinkit / Instamart)</option>
              <option value="Modern Trade">Modern Trade (DMart / Reliance Retail / Star)</option>
              <option value="General Trade">General Trade (Distributor Portal)</option>
            </select>
          </div>
          <div>
            <label className="block text-[10.5px] font-mono text-cohere-muted uppercase mb-1">
              Uploader / Role:
            </label>
            <input
              type="text"
              value={uploaderName}
              onChange={(e) => setUploaderName(e.target.value)}
              className="w-full bg-cohere-panel border border-cohere-border rounded-xs px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cohere-borderLight"
            />
          </div>
        </div>

        {/* Drag and Drop Box */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-md p-5 text-center cursor-pointer transition-all ${
            dragActive 
              ? "border-cohere-actionBlue bg-cohere-actionBlue/10" 
              : "border-cohere-border hover:border-cohere-muted bg-cohere-panel/60"
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv"
            className="hidden"
          />
          <Upload className="w-5 h-5 text-cohere-textSecondary mx-auto mb-2" />
          <div className="text-xs font-medium text-white">
            {selectedFile ? selectedFile.name : "Click to select or drag & drop daily sales CSV file"}
          </div>
          <div className="text-[10.5px] font-mono text-cohere-textMuted mt-1">
            Required headers: <span className="text-cohere-actionBlue">date, sku_id, depot_id, channel, observed_sales</span>
          </div>
        </div>

        {/* Sample Actions Bar */}
        <div className="flex items-center justify-between text-[11px] font-mono text-cohere-muted bg-cohere-panel p-2 rounded-xs border border-cohere-border">
          <span>Need the expected template format?</span>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopySample}
              className="flex items-center space-x-1 px-2.5 py-1 rounded-pill bg-cohere-surface hover:text-white border border-cohere-border text-xs"
            >
              <Copy className="w-3 h-3" />
              <span>Copy Template</span>
            </button>
            <button
              onClick={handleDownloadSample}
              className="flex items-center space-x-1 px-2.5 py-1 rounded-pill bg-cohere-surface hover:text-white border border-cohere-border text-xs"
            >
              <Download className="w-3 h-3" />
              <span>Download CSV</span>
            </button>
          </div>
        </div>

        {/* Validation Errors */}
        {validationErrors.length > 0 && (
          <div className="p-3 rounded-xs bg-scm-critical/10 border border-scm-critical/30 text-xs font-mono space-y-1">
            <div className="font-semibold text-scm-critical flex items-center space-x-1">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Validation Errors Encountered:</span>
            </div>
            {validationErrors.map((err, idx) => (
              <div key={idx} className="text-scm-critical text-[11px] pl-5">• {err}</div>
            ))}
          </div>
        )}

        {/* Parsed Preview Table */}
        {previewRows.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono text-cohere-muted">
              <span className="font-semibold uppercase text-[10px] text-white">
                File Preview ({previewRows.length} sample rows)
              </span>
              <span className="text-[10px]">Verified headers matched</span>
            </div>
            <div className="max-h-36 overflow-y-auto rounded-xs border border-cohere-border bg-cohere-panel">
              <table className="w-full text-[10.5px] font-mono">
                <thead className="bg-cohere-surface border-b border-cohere-border text-cohere-muted text-left sticky top-0">
                  <tr>
                    <th className="p-1.5 font-medium">Date</th>
                    <th className="p-1.5 font-medium">SKU</th>
                    <th className="p-1.5 font-medium">Depot</th>
                    <th className="p-1.5 font-medium">Channel</th>
                    <th className="p-1.5 text-right font-medium">Sales (Btls)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cohere-border/40">
                  {previewRows.map((r, idx) => (
                    <tr key={idx} className="hover:bg-cohere-surface/40">
                      <td className="p-1.5 text-white">{r.date}</td>
                      <td className="p-1.5 font-semibold text-cohere-actionBlue">{r.sku}</td>
                      <td className="p-1.5 text-cohere-textSecondary">{r.depot}</td>
                      <td className="p-1.5 text-cohere-muted">{r.channel}</td>
                      <td className="p-1.5 text-right font-medium text-white">
                        {parseInt(r.sales || 0).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Upload Success Banner */}
        {uploadResult && uploadResult.status === "SUCCESS" && (
          <div className="p-3 rounded-xs bg-scm-healthy/10 border border-scm-healthy/30 text-xs font-mono text-scm-healthy space-y-1">
            <div className="font-semibold flex items-center space-x-1.5 text-scm-healthy">
              <CheckCircle2 className="w-4 h-4" />
              <span>{uploadResult.message}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-[10.5px] pt-1 text-cohere-textSecondary">
              <div>Upload ID: <b className="text-white">{uploadResult.upload_id}</b></div>
              <div>Records Ingested: <b className="text-scm-healthy">{uploadResult.records_inserted}</b></div>
              <div>Duplicates Skipped: <b className="text-cohere-muted">{uploadResult.duplicates_skipped}</b></div>
              <div>Period: <b className="text-white">{uploadResult.reporting_period}</b></div>
              <div>Uploader: <b className="text-white">{uploadResult.uploader}</b></div>
              <div>Timestamp: <b className="text-white">{uploadResult.timestamp.slice(11)}</b></div>
            </div>
          </div>
        )}

        {/* Data Honesty Disclaimer */}
        <div className="p-2.5 rounded-xs bg-cohere-panel border border-cohere-border text-[10px] font-mono text-cohere-muted leading-relaxed">
          <b>Mandatory Data Integrity Rule:</b> Ingested sales are appended to <code className="text-cohere-actionBlue">demand_history.csv</code>.
          Forecast models, corrected latent demand, and inventory cover calculations will automatically refresh. Historical vintages are immutably preserved.
        </div>

        {/* Modal Action Buttons */}
        <div className="flex items-center justify-end space-x-2 pt-2 border-t border-cohere-border font-mono text-xs">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-pill bg-cohere-surface border border-cohere-border text-cohere-textSecondary hover:text-white"
          >
            {uploadResult ? "Close" : "Cancel"}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!selectedFile || uploading || (uploadResult && uploadResult.status === "SUCCESS")}
            className="button-primary disabled:opacity-50"
          >
            {uploading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Ingesting Telemetry...</span>
              </>
            ) : (
              <>
                <Upload className="w-3.5 h-3.5" />
                <span>Submit Ingestion</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
