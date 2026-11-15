import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { memo } from "react";

const PlotlyComp = createPlotlyComponent(Plotly);

export const PALETTE = ["#2fe39a", "#58b4ff", "#f0b44c", "#ff7a8a", "#b58cff", "#4fd1e8", "#e8e27a", "#ff9f5c"];

const AXIS = {
  gridcolor: "#15222a",
  exponentformat: "SI",
  zerolinecolor: "#22323a",
  linecolor: "#22323a",
  tickfont: { family: "JetBrains Mono", size: 10, color: "#7f9089" },
  title: { font: { family: "IBM Plex Sans", size: 11, color: "#7f9089" } },
  showspikes: true,
  spikecolor: "#2fe39a",
  spikethickness: 1,
  spikedash: "dot",
};

export interface PlotProps {
  data: any[];
  layout?: any;
  height?: number;
  onClickX?: (x: number) => void;
}

function PlotInner({ data, layout = {}, height = 280, onClickX }: PlotProps) {
  const lay = {
    autosize: true,
    height,
    margin: { l: 56, r: 16, t: layout.title ? 30 : 10, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#070c0e",
    font: { family: "IBM Plex Sans", color: "#d6e2dd", size: 11 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: "#0e161a", bordercolor: "#2fe39a", font: { family: "JetBrains Mono", size: 11 } },
    legend: { orientation: "h", y: 1.12, x: 0, font: { size: 10.5 }, bgcolor: "rgba(0,0,0,0)" },
    colorway: PALETTE,
    ...layout,
    xaxis: { ...AXIS, ...(layout.xaxis ?? {}), title: { ...AXIS.title, ...(layout.xaxis?.title ?? {}) } },
    yaxis: { ...AXIS, ...(layout.yaxis ?? {}), title: { ...AXIS.title, ...(layout.yaxis?.title ?? {}) } },
    ...(layout.yaxis2 ? { yaxis2: { ...AXIS, overlaying: "y", side: "right", showgrid: false, ...layout.yaxis2, title: { ...AXIS.title, ...(layout.yaxis2.title ?? {}) } } } : {}),
  };
  return (
    <PlotlyComp
      data={data}
      layout={lay}
      useResizeHandler
      style={{ width: "100%", height }}
      config={{ displaylogo: false, responsive: true, scrollZoom: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"], toImageButtonOptions: { format: "png", scale: 2 } }}
      onClick={(e: any) => {
        const x = e?.points?.[0]?.x;
        if (onClickX && typeof x === "number") onClickX(x);
      }}
    />
  );
}

export const Plot = memo(PlotInner);
