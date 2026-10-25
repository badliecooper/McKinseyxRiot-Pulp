import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface EChartProps {
  option: any;
  height?: number | string;
  width?: number | string;
  className?: string;
  loading?: boolean;
  empty?: boolean;
  emptyText?: string;
  onEvents?: Record<string, (params: any) => void>;
}

export const EChart: React.FC<EChartProps> = ({
  option,
  height = 320,
  width = "100%",
  className = "",
  loading = false,
  empty = false,
  emptyText = "No data available",
  onEvents,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, {
        renderer: "canvas",
      });

      // Bind events
      if (onEvents) {
        Object.entries(onEvents).forEach(([eventName, handler]) => {
          chartInstance.current?.on(eventName, handler);
        });
      }
    }

    const chart = chartInstance.current;

    if (loading) {
      chart.showLoading({
        text: "Analyzing...",
        color: "#1863DC",
        textColor: "#94A3B8",
        maskColor: "rgba(13, 14, 18, 0.75)",
      });
    } else {
      chart.hideLoading();
      chart.setOption(option, true);
    }

    const handleResize = () => {
      chart.resize();
    };

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [option, loading, onEvents]);

  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

  if (empty) {
    return (
      <div
        className={`flex items-center justify-center border border-cohere-border rounded-sm bg-cohere-card text-cohere-muted text-xs font-mono ${className}`}
        style={{ height, width }}
      >
        {emptyText}
      </div>
    );
  }

  return (
    <div
      ref={chartRef}
      className={`w-full overflow-hidden ${className}`}
      style={{ height, width }}
    />
  );
};
