declare module "plotly.js-dist-min" {
  const Plotly: any;
  export default Plotly;
}
declare module "react-plotly.js/factory" {
  const createPlotlyComponent: (plotly: any) => any;
  export default createPlotlyComponent;
}

interface RfwbUpdateState { status: string; message: string; version: string | null; current?: string; packaged?: boolean }
interface Window {
  /** Sólo existe en la aplicación de escritorio (preload de Electron). */
  rfwb?: { updates: { check: () => Promise<RfwbUpdateState>; state: () => Promise<RfwbUpdateState> } };
}
