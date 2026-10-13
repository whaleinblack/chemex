import type { Locale } from './types';

type Copy = {
  badges: {
    toolbox: string;
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
    research: string;
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
      toolbox: 'COF多功能工具箱',
    },
    languageLabel: '语言',
    heroSubtitle: 'COF多功能工具箱',
    heroBody:
      'COF多功能工具箱，整合实验设计与文献检索、SESAMI 吸附分析和 ZEO++ 孔隙结构分析。',
    heroFootnote: '支持本地文件上传、任务进度跟踪、结果查看与导出。',
    guide: {
      buttonLabel: '使用说明',
      title: '使用说明',
      intro: 'ChemEx 当前已把 SESAMI 与 ZEO++ 的核心工作流整合到同一个本地双语工作台，页面风格与顶部和底部说明采用线上正式版口径。',
      implementedTitle: '当前已实现',
      implementedItems: [
        'COF实验设计：名称/CAS 基础检索；配置深度检索后支持识图、主体匹配及条件提取',
        'SESAMI：BET、BET+ESW、BET-ML、Compare、Advanced',
        'ZEO++：PSD、RES/RESEX、CHAN、SA、VOL、VOLPO',
        '支持本地文件上传、真实任务进度轮询、图像与原始结果导出',
      ],
      usageTitle: '如何操作',
      usageItems: [
        '选择 COF实验设计、SESAMI 或 ZEO++；文献检索先确认单体身份，再检索组合。',
        '上传本地等温线或结构文件，按需要填写气体、版本或计算参数。',
        '点击运行后等待进度完成，再在结果区查看指标、图像、线性区或导出原始数据。',
      ],
      note: '文献检索需要联网服务；暂未检索到不能证明无人做过。条件以原文和补充信息为准。',
    },
    tabs: {
      research: 'COF实验设计',
      sesami: 'SESAMI',
      zeopp: 'ZEO++',
    },
    footer: {
      brand: 'ChemEx',
      description: 'COF多功能工具箱',
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
    },
    languageLabel: 'Language',
    heroSubtitle: 'COF multifunctional toolbox',
    heroBody:
      'A COF multifunctional toolbox for experiment design, literature research, SESAMI adsorption analysis, and ZEO++ pore analysis.',
    heroFootnote: 'Supports local file upload, job progress tracking, result inspection, and export.',
    guide: {
      buttonLabel: 'Usage guide',
      title: 'Usage guide',
      intro: 'ChemEx now brings the core SESAMI and ZEO++ workflows into one bilingual local workbench, while keeping the header and footer aligned with the formal online presentation.',
      implementedTitle: 'Currently implemented',
      implementedItems: [
        'COF Experiment Design: name/CAS metadata search; image, backbone and condition research with the enhanced service',
        'SESAMI: BET, BET+ESW, BET-ML, Compare, Advanced',
        'ZEO++: PSD, RES/RESEX, CHAN, SA, VOL, VOLPO',
        'Local file upload, real progress polling, plots, and raw-result export',
      ],
      usageTitle: 'How to use',
      usageItems: [
        'Choose COF Experiment Design, SESAMI, or ZEO++; confirm monomer identities before researching a combination.',
        'Upload a local isotherm or structure file and set the needed gas, version, or calculation parameters.',
        'Run the job and inspect metrics, plots, linear regions, or exported raw data once the progress completes.',
      ],
      note: 'Literature research requires the online service. No results does not prove novelty; verify conditions in the paper and supporting information.',
    },
    tabs: {
      research: 'COF Experiment Design',
      sesami: 'SESAMI',
      zeopp: 'ZEO++',
    },
    footer: {
      brand: 'ChemEx',
      description: 'COF multifunctional toolbox',
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
