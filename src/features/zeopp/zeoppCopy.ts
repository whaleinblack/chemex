import type { Locale } from '../../lib/types';

type ModeCopy = {
  title: string;
  subtitle: string;
  run: string;
  fileLabel: string;
  fileHint: string;
  readyHint: string;
  pendingHint: string;
  statusReady: string;
  statusWaiting: string;
  statusFailed: string;
  outputTitle: string;
  outputHint: string;
  copy: string;
  downloadTxt: string;
  downloadMd: string;
  clear: string;
  placeholder: string;
  fields: {
    chanRadius: string;
    probeRadius: string;
    numSamples: string;
    extended: string;
  };
  tabs: {
    psd: string;
    res: string;
    chan: string;
    sa: string;
    vol: string;
    volpo: string;
  };
  result: {
    summary: string;
    metrics: string;
    plot: string;
    rows: string;
    raw: string;
    channels: string;
    noRows: string;
    noMetrics: string;
  };
};

export const zeoppCopy: Record<Locale, ModeCopy> = {
  zh: {
    title: 'ZEO++ Workbench',
    subtitle: '把 PSD、RES、CHAN、SA、VOL、VOLPO 集成到同一个几何分析工作台里。',
    run: '运行计算',
    fileLabel: '结构文件',
    fileHint: '支持 `.cif`、`.cssr`、`.v1`、`.cuc`，上传后在当前子页执行。',
    readyHint: 'ZEO++ 运行时已就绪，可以直接提交任务。',
    pendingHint: '运行时未就绪时，只保留前端表单与结果预览。',
    statusReady: '可运行',
    statusWaiting: '等待运行时',
    statusFailed: '执行失败',
    outputTitle: '原始输出',
    outputHint: '保留 stdout / stderr 与结果文本，便于导出和复核。',
    copy: '复制',
    downloadTxt: '导出 TXT',
    downloadMd: '导出 MD',
    clear: '清空',
    placeholder: '功能骨架已接好，等待后端对应接口输出结构化结果。',
    fields: {
      chanRadius: 'Channel radius',
      probeRadius: 'Probe radius',
      numSamples: '采样点数',
      extended: '启用 RESEX 扩展输出',
    },
    tabs: {
      psd: 'PSD',
      res: 'RES / RESEX',
      chan: 'CHAN',
      sa: 'SA',
      vol: 'VOL',
      volpo: 'VOLPO',
    },
    result: {
      summary: '结果摘要',
      metrics: '关键数值',
      plot: '图形预览',
      rows: '数据表',
      raw: '原始文本',
      channels: '通道摘要',
      noRows: '当前结果还没有返回表格数据。',
      noMetrics: '当前结果还没有结构化指标，先保留原始输出。',
    },
  },
  en: {
    title: 'ZEO++ Workbench',
    subtitle: 'Bring PSD, RES, CHAN, SA, VOL, and VOLPO into one geometry analysis surface.',
    run: 'Run calculation',
    fileLabel: 'Structure file',
    fileHint: 'Supports `.cif`, `.cssr`, `.v1`, `.cuc`; the uploaded file is executed in the active subtab.',
    readyHint: 'The ZEO++ runtime is ready and jobs can be submitted now.',
    pendingHint: 'When the runtime is unavailable, the page still shows the form and result shell.',
    statusReady: 'Ready',
    statusWaiting: 'Waiting for runtime',
    statusFailed: 'Failed',
    outputTitle: 'Raw output',
    outputHint: 'Keep stdout / stderr and result text for export and verification.',
    copy: 'Copy',
    downloadTxt: 'TXT',
    downloadMd: 'MD',
    clear: 'Clear',
    placeholder: 'The feature shell is wired and waiting for backend structured outputs.',
    fields: {
      chanRadius: 'Channel radius',
      probeRadius: 'Probe radius',
      numSamples: 'Sample count',
      extended: 'Enable RESEX extended output',
    },
    tabs: {
      psd: 'PSD',
      res: 'RES / RESEX',
      chan: 'CHAN',
      sa: 'SA',
      vol: 'VOL',
      volpo: 'VOLPO',
    },
    result: {
      summary: 'Summary',
      metrics: 'Metrics',
      plot: 'Plot preview',
      rows: 'Data table',
      raw: 'Raw text',
      channels: 'Channel summary',
      noRows: 'This result has not returned a data table yet.',
      noMetrics: 'No structured metrics are available yet, so keep the raw output handy.',
    },
  },
};
