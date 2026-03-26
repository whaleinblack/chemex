import type { Locale } from './types';

type Copy = {
  badges: {
    toolbox: string;
    release: string;
  };
  languageLabel: string;
  heroSubtitle: string;
  heroBody: string;
  heroFootnote: string;
  guide: {
    buttonLabel: string;
    title: string;
    intro: string;
    implementedTitle: string;
    implementedItems: string[];
    usageTitle: string;
    usageItems: string[];
    note: string;
  };
  tabs: {
    sesami: string;
    zeopp: string;
  };
  footer: {
    brand: string;
    description: string;
    online: string;
    offline: string;
    ready: string;
    unavailable: string;
    pending: string;
    apiReady: string;
    apiUnknown: string;
    status: {
      api: string;
      sesami: string;
      zeopp: string;
    };
  };
  common: {
    comingSoon: string;
  };
};

export const copy: Record<Locale, Copy> = {
  zh: {
    badges: {
      toolbox: 'COF 多功能计算工具箱',
      release: 'v0.5',
    },
    languageLabel: '语言',
    heroSubtitle: 'COF多功能计算工具箱',
    heroBody:
      'COF多功能计算工具箱，已接入 SESAMI 与 ZEO++ 两条真实计算工作流，并在统一界面下扩展为多功能分析套件。',
    heroFootnote: '支持本地文件上传、任务进度跟踪、结果查看与导出。',
    guide: {
      buttonLabel: '使用说明',
      title: '使用说明',
      intro: 'ChemEx 当前已把 SESAMI 与 ZEO++ 的核心工作流整合到同一个本地双语工作台，页面风格与顶部和底部说明采用线上正式版口径。',
      implementedTitle: '当前已实现',
      implementedItems: [
        'SESAMI：BET、BET+ESW、BET-ML、Compare、Advanced',
        'ZEO++：PSD、RES/RESEX、CHAN、SA、VOL、VOLPO',
        '支持本地文件上传、真实任务进度轮询、图像与原始结果导出',
      ],
      usageTitle: '如何操作',
      usageItems: [
        '先在顶部选择 SESAMI 或 ZEO++ 主工具，再切换到对应 subtab。',
        '上传本地等温线或结构文件，按需要填写气体、版本或计算参数。',
        '点击运行后等待进度完成，再在结果区查看指标、图像、线性区或导出原始数据。',
      ],
      note: '当前说明以线上正式版展示口径为准，实际可用功能以本地已接入的真实计算流程为准。',
    },
    tabs: {
      sesami: 'SESAMI',
      zeopp: 'ZEO++',
    },
    footer: {
      brand: 'ChemEx',
      description: 'COF多功能计算工具箱 · v0.5',
      online: 'Online',
      offline: 'Offline',
      ready: 'Ready',
      unavailable: 'Unavailable',
      pending: '等待状态更新',
      apiReady: 'API ready',
      apiUnknown: '尚未连接到后端',
      status: {
        api: '后端状态',
        sesami: 'SESAMI',
        zeopp: 'ZEO++',
      },
    },
    common: {
      comingSoon: '功能骨架已就位，正在接入真实计算流程。',
    },
  },
  en: {
    badges: {
      toolbox: 'COF Multi-Toolbox',
      release: 'v0.5',
    },
    languageLabel: 'Language',
    heroSubtitle: 'COF multifunctional computational toolbox',
    heroBody:
      'A COF multifunctional computation toolbox with live SESAMI and ZEO++ workflows, expanded inside one shared interface as multi-function analysis suites.',
    heroFootnote: 'Supports local file upload, job progress tracking, result inspection, and export.',
    guide: {
      buttonLabel: 'Usage guide',
      title: 'Usage guide',
      intro: 'ChemEx now brings the core SESAMI and ZEO++ workflows into one bilingual local workbench, while keeping the header and footer aligned with the formal online presentation.',
      implementedTitle: 'Currently implemented',
      implementedItems: [
        'SESAMI: BET, BET+ESW, BET-ML, Compare, Advanced',
        'ZEO++: PSD, RES/RESEX, CHAN, SA, VOL, VOLPO',
        'Local file upload, real progress polling, plots, and raw-result export',
      ],
      usageTitle: 'How to use',
      usageItems: [
        'Choose SESAMI or ZEO++ at the top, then switch to the required subtab.',
        'Upload a local isotherm or structure file and set the needed gas, version, or calculation parameters.',
        'Run the job and inspect metrics, plots, linear regions, or exported raw data once the progress completes.',
      ],
      note: 'The visual guidance follows the formal online presentation, while the actual available actions reflect the local features already wired to real calculations.',
    },
    tabs: {
      sesami: 'SESAMI',
      zeopp: 'ZEO++',
    },
    footer: {
      brand: 'ChemEx',
      description: 'COF multifunctional computational toolbox · v0.5',
      online: 'Online',
      offline: 'Offline',
      ready: 'Ready',
      unavailable: 'Unavailable',
      pending: 'Waiting for status',
      apiReady: 'API ready',
      apiUnknown: 'Backend not connected yet',
      status: {
        api: 'Backend status',
        sesami: 'SESAMI',
        zeopp: 'ZEO++',
      },
    },
    common: {
      comingSoon: 'The feature shell is ready and being wired to real calculations.',
    },
  },
};
