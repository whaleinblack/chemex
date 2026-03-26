export type Locale = 'zh' | 'en';
export type ToolKey = 'zeopp' | 'sesami';

export type Health = {
  status: string;
  sesamiReady: boolean;
  sesamiMessage?: string;
  zeoppReady: boolean;
  zeoppMessage: string;
};

export type ZeoppStatus = {
  available: boolean;
  binaryPath: string | null;
  message: string;
};

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export type JobSnapshot<T = unknown> = {
  jobId: string;
  workflow: string;
  filename?: string;
  status: JobStatus;
  progress: number;
  stage: string;
  result?: T | null;
  error?: string | null;
  warning?: string | null;
};

export type SesamiVersion = '2.9' | '1.0';
export type SesamiSubtab = 'bet' | 'betEsw' | 'betMl' | 'compare' | 'advanced';
export type ZeoppSubtab = 'psd' | 'res' | 'chan' | 'sa' | 'vol' | 'volpo';

export type SesamiPlot = {
  name: string;
  url: string;
};

export type SesamiPoint = {
  P_rel?: number | null;
  Pressure?: number | null;
  Loading?: number | null;
};

export type SesamiLinearRegion = {
  count: number;
  lowPressurePa: number;
  highPressurePa: number;
};

export type SesamiMetrics = {
  area?: number | null;
  qm?: number | null;
  C?: number | null;
  r2?: number | null;
  con3?: string | null;
  con4?: string | null;
};

export type SesamiCompareEntry = {
  label: string;
  engine?: string;
  metrics?: SesamiMetrics;
  warning?: string | null;
};

export type SesamiResult = {
  jobId?: string;
  gas?: string;
  engine?: string;
  version?: string;
  mode?: string;
  area?: number | null;
  qm?: number | null;
  C?: number | null;
  r2?: number | null;
  con3?: string | null;
  con4?: string | null;
  plotUrl?: string | null;
  plots?: SesamiPlot[];
  points?: SesamiPoint[];
  selectedPoints?: SesamiPoint[];
  linearRegionPoints?: SesamiPoint[];
  linearRegion?: SesamiLinearRegion;
  betEsw?: SesamiMetrics & {
    linearRegion?: SesamiLinearRegion;
    selectedPoints?: SesamiPoint[];
  };
  betMl?: {
    area?: number | null;
    warning?: string | null;
  };
  comparison?: SesamiCompareEntry[];
  warning?: string | null;
  rawOutput?: string | null;
  metadata?: Record<string, string | number | boolean | null>;
};

export type ZeoppSeriesRow = {
  diameter: number;
  value: number;
  count?: number;
  cumulative?: number;
  derivative?: number;
};

export type ZeoppMetric = {
  key: string;
  label: string;
  value: number | string | null;
  unit?: string;
};

export type ZeoppChannelSummary = {
  count: number;
  dimensionalities: number[];
  largestIncludedSpheres: number[];
  largestFreeSpheres: number[];
  largestIncludedFreeSpheres: number[];
};

export type ZeoppResult = {
  jobId?: string;
  mode?: string;
  rows?: ZeoppSeriesRow[];
  metrics?: ZeoppMetric[];
  channels?: ZeoppChannelSummary;
  rawOutput?: string;
  stdout?: string;
  stderr?: string;
  returnCode?: number;
  warning?: string | null;
  artifacts?: Array<{ name: string; url: string }>;
  metadata?: Record<string, string | number | boolean | null>;
};
