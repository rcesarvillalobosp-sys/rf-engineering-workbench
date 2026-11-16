import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { memo } from "react";
import { type Palette, useTheme } from "../lib/theme";

const PlotlyComp = createPlotlyComponent(Plotly);

/** Colores de series del tema activo (sustituye a la antigua constante PALETTE). */
export function usePalette() {
  return useTheme().series;
}

export interface PlotProps {
  data: any[];
  layout?: any;
  height?: number;
  onClickX?: (x: number) => void;
}

function axis(T: Palette) {
  return {
    gridcolor: T.grid,
    exponentformat: "SI",
    zerolinecolor: T.zero,
    linecolor: T.zero,
    tickfont: { family: "JetBrains Mono", size: 10, color: T.dim },
    title: { font: { family: "IBM Plex Sans", size: 11, color: T.dim } },
    showspikes: true,
    spikecolor: T.acc,
    spikethickness: 1,
    spikedash: "dot",
  };
}

function PlotInner({ data, layout = {}, height = 280, onClickX }: PlotProps) {
  const T = useTheme();
  const AX = axis(T);
  const lay = {
    autosize: true,
    height,
    margin: { l: 56, r: 16, t: layout.title ? 30 : 10, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: T.plotBg,
    font: { family: "IBM Plex Sans", color: T.ink, size: 11 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: T.panel2, bordercolor: T.acc, font: { family: "JetBrains Mono", size: 11, color: T.ink } },
    legend: { orientation: "h", y: 1.12, x: 0, font: { size: 10.5, color: T.ink }, bgcolor: "rgba(0,0,0,0)" },
    colorway: T.series,
    ...layout,
    xaxis: { ...AX, ...(layout.xaxis ?? {}), title: { ...AX.title, ...(layout.xaxis?.title ?? {}) } },
    yaxis: { ...AX, ...(layout.yaxis ?? {}), title: { ...AX.title, ...(layout.yaxis?.title ?? {}) } },
    ...(layout.yaxis2 ? { yaxis2: { ...AX, overlaying: "y", side: "right", showgrid: false, ...layout.yaxis2, title: { ...AX.title, ...(layout.yaxis2.title ?? {}) } } } : {}),
    ...(layout.polar ? { polar: { bgcolor: T.plotBg, ...layout.polar,
      angularaxis: { gridcolor: T.grid, linecolor: T.zero, tickfont: { size: 9, color: T.dim }, ...(layout.polar.angularaxis ?? {}) },
      radialaxis: { gridcolor: T.grid, linecolor: T.zero, tickfont: { size: 9, color: T.dim }, ...(layout.polar.radialaxis ?? {}) } } } : {}),
  };
  return (
    <PlotlyComp
      data={data}
      layout={lay}
      useResizeHandler
      style={{ width: "100%", height }}
      config={{ displaylogo: false, responsive: true, scrollZoom: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"], toImageButtonOptions: { format: "png", scale: 3 } }}
      onClick={(e: any) => {
        const x = e?.points?.[0]?.x;
        if (onClickX && typeof x === "number") onClickX(x);
      }}
    />
  );
}

export const Plot = memo(PlotInner);
