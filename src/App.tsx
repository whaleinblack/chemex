import { useEffect, useState, type CSSProperties, type MouseEvent as ReactMouseEvent } from 'react';
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  FileButton,
  Group,
  Modal,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
} from '@mantine/core';
import {
  IconAtom2,
  IconDroplet,
  IconLanguage,
  IconSparkles,
  IconUpload,
} from '@tabler/icons-react';

type Locale = 'zh' | 'en';
type ToolKey = 'zeopp' | 'sesami';

type Health = {
  status: string;
  sesamiReady: boolean;
  sesamiMessage?: string;
  zeoppReady: boolean;
  zeoppMessage: string;
};

type ZeoppStatus = {
  available: boolean;
  binaryPath: string | null;
  message: string;
};

type SesamiPlot = {
  name: string;
  url: string;
};

type SesamiPoint = {
  P_rel?: number;
  Pressure?: number;
  Loading?: number;
};

type SesamiResult = {
  engine?: string;
  area: number;
  qm: number;
  C: number;
  r2: number;
  con3: string;
  con4: string;
  plotUrl: string | null;
  plots: SesamiPlot[];
  points: SesamiPoint[];
  selectedPoints: SesamiPoint[];
  linearRegionPoints?: SesamiPoint[];
  linearRegion: {
    count: number;
    lowPressurePa: number;
    highPressurePa: number;
  };
};

type ZeoppResult = {
  rows: Array<{ diameter: number; value: number }>;
  rawOutput: string;
};

type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

type JobSnapshot<T = unknown> = {
  jobId: string;
  workflow: ToolKey;
  filename?: string;
  status: JobStatus;
  progress: number;
  stage: string;
  result?: T | null;
  error?: string | null;
  warning?: string | null;
};

type Copy = {
  subtitle: string;
  languageLabel: string;
  heroTitle: string;
  heroBody: string;
  heroFootnote: string;
  tabs: Record<ToolKey, string>;
  health: {
    online: string;
    sesami: string;
    zeopp: string;
  };
  sesami: {
    title: string;
    desc: string;
    upload: string;
    noFile: string;
    gas: string;
    run: string;
    accepted: string;
    metrics: {
      area: string;
      qm: string;
      c: string;
      r2: string;
      region: string;
    };
  };
  zeopp: {
    title: string;
    desc: string;
    upload: string;
    noFile: string;
    chanRadius: string;
    probeRadius: string;
    numSamples: string;
    run: string;
    accepted: string;
    unavailableTitle: string;
    unavailableBody: string;
    rawOutput: string;
  };
  working: string;
  failed: string;
};

const copy: Record<Locale, Copy> = {
  zh: {
    subtitle: '多孔材料计算工作台',
    languageLabel: '语言',
    heroTitle: '先把两条真实计算链接进来',
    heroBody:
      '当前页面已经聚焦到两个优先功能：ZEO++ 的 pore size distribution 和 SESAMI 的 BET surface area。SESAMI 会直接调用上游算法，ZEO++ 会按原生命令行接口执行。',
    heroFootnote: '这版主要目标是把本地上传、任务触发和结果回传先打通。',
    tabs: {
      zeopp: 'ZEO++ · PSD',
      sesami: 'SESAMI · BET',
    },
    health: {
      online: '后端状态',
      sesami: 'SESAMI BET',
      zeopp: 'ZEO++ PSD',
    },
    sesami: {
      title: 'BET 比表面积计算',
      desc: '上传 CSV 或 AIF，使用最新 SESAMI 包的 fitbet 接口计算 BET 表面积，并返回线性区间与图像。',
      upload: '上传等温线文件',
      noFile: '未选择 CSV / AIF 文件',
      gas: '吸附气体',
      run: '运行 BET',
      accepted: '支持 .csv / .aif，默认按 Argon(87 K) 或 Nitrogen(77 K) 计算。',
      metrics: {
        area: 'BET 面积',
        qm: 'qm',
        c: 'C 常数',
        r2: '线性 R²',
        region: '线性区间',
      },
    },
    zeopp: {
      title: 'Pore Size Distribution',
      desc: '上传结构文件并按 ZEO++ 的 -psd 命令执行。当前页面已接好参数与 API，是否可运行取决于本机是否存在编译后的 network 二进制。',
      upload: '上传结构文件',
      noFile: '未选择结构文件',
      chanRadius: 'Channel radius',
      probeRadius: 'Probe radius',
      numSamples: '采样点数',
      run: '运行 PSD',
      accepted: '优先用于已能被 ZEO++ 处理的结构文件。当前机器若没有 network 二进制，会直接返回环境提示。',
      unavailableTitle: '当前机器尚未具备 ZEO++ 运行时',
      unavailableBody: '源码已接入，前端和 API 已就位，但缺少已编译的 network 可执行文件，所以本地无法真正执行 PSD。',
      rawOutput: '原始输出',
    },
    working: '运行中...',
    failed: '请求失败',
  },
  en: {
    subtitle: 'Porous Materials Workbench',
    languageLabel: 'Language',
    heroTitle: 'Two real calculation flows first',
    heroBody:
      'This build now focuses on the two priority workflows: ZEO++ pore size distribution and SESAMI BET surface area. SESAMI calls the upstream algorithm directly, while ZEO++ is wired through its native command-line interface.',
    heroFootnote: 'The goal of this iteration is to make local upload, job execution, and result return work end to end.',
    tabs: {
      zeopp: 'ZEO++ · PSD',
      sesami: 'SESAMI · BET',
    },
    health: {
      online: 'Backend status',
      sesami: 'SESAMI BET',
      zeopp: 'ZEO++ PSD',
    },
    sesami: {
      title: 'BET surface area',
      desc: 'Upload a CSV or AIF file and run BET through the latest SESAMI package fitbet interface, with a returned linear region summary and figure.',
      upload: 'Upload isotherm file',
      noFile: 'No CSV / AIF selected',
      gas: 'Adsorbate gas',
      run: 'Run BET',
      accepted: 'Supports .csv / .aif. Uses Argon (87 K) or Nitrogen (77 K) defaults.',
      metrics: {
        area: 'BET area',
        qm: 'qm',
        c: 'C constant',
        r2: 'Linear R²',
        region: 'Linear region',
      },
    },
    zeopp: {
      title: 'Pore Size Distribution',
      desc: 'Upload a structure file and execute the ZEO++ -psd command. The UI and API are wired, but execution depends on whether this machine has a compiled network binary.',
      upload: 'Upload structure file',
      noFile: 'No structure file selected',
      chanRadius: 'Channel radius',
      probeRadius: 'Probe radius',
      numSamples: 'Samples',
      run: 'Run PSD',
      accepted: 'Best with files already supported by ZEO++. If the machine lacks a network binary, the API returns an environment warning.',
      unavailableTitle: 'ZEO++ runtime is not available on this machine yet',
      unavailableBody: 'The source code is wired in and the app can submit PSD jobs, but local execution still needs a compiled network binary.',
      rawOutput: 'Raw output',
    },
    working: 'Running...',
    failed: 'Request failed',
  },
};

const ACTIVE_JOB_STATUSES: JobStatus[] = ['queued', 'running'];
const APP_BASE_PATH = detectRuntimeBasePath();

const stageCopy: Record<Locale, Record<string, string>> = {
  zh: {
    submitting: '\u63d0\u4ea4\u4e2d',
    queued: '\u961f\u5217\u4e2d',
    preparing_input: '\u51c6\u5907\u8f93\u5165',
    initializing_engine: '\u521d\u59cb\u5316\u5f15\u64ce',
    preparing_isotherm: '\u9884\u5904\u7406\u7b49\u6e29\u7ebf',
    running_bet: '\u6b63\u5728\u6267\u884c BET',
    rendering_plots: '\u751f\u6210\u56fe\u50cf',
    packaging_result: '\u6574\u7406\u7ed3\u679c',
    launching: '\u542f\u52a8 ZEO++',
    reading_structure: '\u8bfb\u53d6\u7ed3\u6784',
    initial_voronoi: '\u521d\u59cb Voronoi \u5206\u89e3',
    routing_network: '\u6784\u5efa\u7f51\u7edc',
    psd_setup: '\u521d\u59cb\u5316 PSD',
    psd_voronoi: 'PSD Voronoi \u5206\u6790',
    finding_channels: '\u641c\u7d22\u901a\u9053\u4e0e\u5b54\u888b',
    classifying_pores: '\u5206\u7c7b\u5b54\u7ed3\u6784',
    writing_output: '\u5199\u51fa PSD \u7ed3\u679c',
    parsing_output: '\u89e3\u6790\u8f93\u51fa',
    completed: '\u5df2\u5b8c\u6210',
    failed: '\u5df2\u5931\u8d25',
  },
  en: {
    submitting: 'Submitting',
    queued: 'Queued',
    preparing_input: 'Preparing input',
    initializing_engine: 'Loading engine',
    preparing_isotherm: 'Preparing isotherm',
    running_bet: 'Running BET',
    rendering_plots: 'Rendering plots',
    packaging_result: 'Packaging result',
    launching: 'Launching ZEO++',
    reading_structure: 'Reading structure',
    initial_voronoi: 'Initial Voronoi',
    routing_network: 'Routing network',
    psd_setup: 'Starting PSD',
    psd_voronoi: 'PSD Voronoi',
    finding_channels: 'Finding channels',
    classifying_pores: 'Classifying pores',
    writing_output: 'Writing output',
    parsing_output: 'Parsing output',
    completed: 'Completed',
    failed: 'Failed',
  },
};

function translateStage(locale: Locale, stage?: string) {
  if (!stage) {
    return '';
  }
  return stageCopy[locale][stage] || stage;
}

function App() {
  const [locale, setLocale] = useState<Locale>('zh');
  const [activeTab, setActiveTab] = useState<ToolKey>('sesami');
  const [health, setHealth] = useState<Health | null>(null);
  const [zeoppStatus, setZeoppStatus] = useState<ZeoppStatus | null>(null);

  const [sesamiFile, setSesamiFile] = useState<File | null>(null);
  const [sesamiGas, setSesamiGas] = useState<string>('Argon');
  const [sesamiVersion, setSesamiVersion] = useState<string>('2.9');
  const [sesamiSubmitting, setSesamiSubmitting] = useState(false);
  const [sesamiJob, setSesamiJob] = useState<JobSnapshot<SesamiResult> | null>(null);
  const [sesamiError, setSesamiError] = useState('');
  const [sesamiWarning, setSesamiWarning] = useState('');
  const [sesamiResult, setSesamiResult] = useState<SesamiResult | null>(null);
  const [activeSesamiPlot, setActiveSesamiPlot] = useState<SesamiPlot | null>(null);

  const [zeoppFile, setZeoppFile] = useState<File | null>(null);
  const [chanRadius, setChanRadius] = useState<number | string>(1.86);
  const [probeRadius, setProbeRadius] = useState<number | string>(1.86);
  const [numSamples, setNumSamples] = useState<number | string>(10000);
  const [zeoppSubmitting, setZeoppSubmitting] = useState(false);
  const [zeoppJob, setZeoppJob] = useState<JobSnapshot<ZeoppResult> | null>(null);
  const [zeoppError, setZeoppError] = useState('');
  const [zeoppWarning, setZeoppWarning] = useState('');
  const [zeoppResult, setZeoppResult] = useState<ZeoppResult | null>(null);
  const [zeoppActionMessage, setZeoppActionMessage] = useState('');

  const t = copy[locale];
  const heroSubtitle = locale === 'zh' ? 'COF\u591a\u529f\u80fd\u8ba1\u7b97\u5de5\u5177\u7bb1' : 'Multipurpose COF Toolbox';
  const heroTitle = 'ChemEx';
  const heroLogoAlt = 'ChemEx logo';
  const heroLogoUrl = buildAppPath('chemex-logo.png');
  const heroBody =
    locale === 'zh'
      ? 'COF\u591a\u529f\u80fd\u8ba1\u7b97\u5de5\u5177\u7bb1\uff0c\u5df2\u63a5\u5165 SESAMI BET \u6bd4\u8868\u9762\u79ef\u4e0e ZEO\u002b\u002b \u5b54\u5f84\u5206\u5e03\u4e24\u6761\u771f\u5b9e\u8ba1\u7b97\u6d41\u7a0b\u3002'
      : 'A multipurpose COF computation toolbox with live SESAMI BET surface area and ZEO++ pore size distribution workflows.';
  const heroFootnote =
    locale === 'zh'
      ? '\u652f\u6301\u672c\u5730\u6587\u4ef6\u4e0a\u4f20\u3001\u4efb\u52a1\u8fdb\u5ea6\u8ddf\u8e2a\u4e0e\u7ed3\u679c\u56de\u4f20\u3002'
      : 'Supports local file upload, job progress tracking, and result inspection.';
  const sesamiVersionLabel = locale === 'zh' ? 'SESAMI \u7248\u672c' : 'SESAMI version';
  const onlineHealthy = health?.status === 'ok';
  const sesamiHealthy = Boolean(health?.sesamiReady);
  const zeoppHealthy = Boolean(health?.zeoppReady);
  const sesamiBusy = sesamiSubmitting || Boolean(sesamiJob && ACTIVE_JOB_STATUSES.includes(sesamiJob.status));
  const zeoppBusy = zeoppSubmitting || Boolean(zeoppJob && ACTIVE_JOB_STATUSES.includes(zeoppJob.status));
  const sesamiProgress = sesamiBusy ? (sesamiJob?.progress ?? 2) : 0;
  const zeoppProgress = zeoppBusy ? (zeoppJob?.progress ?? 2) : 0;
  const sesamiStageLabel = translateStage(locale, sesamiSubmitting && !sesamiJob ? 'submitting' : sesamiJob?.stage);
  const zeoppStageLabel = translateStage(locale, zeoppSubmitting && !zeoppJob ? 'submitting' : zeoppJob?.stage);

  useEffect(() => {
    void Promise.all([
      fetch(buildAppPath('api/health')).then((res) => res.json()),
      fetch(buildAppPath('api/zeopp/status')).then((res) => res.json()),
    ]).then(([healthData, zeoppData]) => {
      setHealth(healthData);
      setZeoppStatus(zeoppData);
    });
  }, []);

  useEffect(() => {
    if (!sesamiJob || !ACTIVE_JOB_STATUSES.includes(sesamiJob.status)) {
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch(buildAppPath(`api/jobs/${sesamiJob.jobId}`));
        const data = await readApiJson<JobSnapshot<SesamiResult> & { error?: string }>(response, locale, t.failed);
        if (!response.ok) {
          throw new Error(data.error || t.failed);
        }
        if (cancelled) {
          return;
        }
        setSesamiJob(data);
        if (data.status === 'completed') {
          setSesamiResult(normalizeSesamiResult(data.result || null));
          setSesamiWarning(data.warning || '');
        }
        if (data.status === 'failed') {
          setSesamiError(data.error || t.failed);
          setSesamiWarning(data.warning || '');
        }
      } catch (error) {
        if (!cancelled) {
          setSesamiError(error instanceof Error ? error.message : t.failed);
        }
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 150);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sesamiJob?.jobId, sesamiJob?.status, t.failed]);

  useEffect(() => {
    if (!zeoppJob || !ACTIVE_JOB_STATUSES.includes(zeoppJob.status)) {
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch(buildAppPath(`api/jobs/${zeoppJob.jobId}`));
        const data = await readApiJson<JobSnapshot<ZeoppResult> & { error?: string }>(response, locale, t.failed);
        if (!response.ok) {
          throw new Error(data.error || t.failed);
        }
        if (cancelled) {
          return;
        }
        setZeoppJob(data);
        if (data.status === 'completed') {
          setZeoppResult(data.result || null);
          setZeoppWarning(data.warning || '');
        }
        if (data.status === 'failed') {
          setZeoppError(data.error || t.failed);
          setZeoppWarning(data.warning || '');
        }
      } catch (error) {
        if (!cancelled) {
          setZeoppError(error instanceof Error ? error.message : t.failed);
        }
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 150);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [zeoppJob?.jobId, zeoppJob?.status, t.failed]);

  function getProgressStyle(value: number): CSSProperties {
    return { ['--progress-width' as string]: `${value}%` };
  }

  async function runSesami() {
    if (!sesamiFile) {
      setSesamiError(t.sesami.noFile);
      return;
    }

    setSesamiSubmitting(true);
    setSesamiError('');
    setSesamiWarning('');
    setSesamiResult(null);
    setSesamiJob(null);
    setActiveSesamiPlot(null);

    const formData = new FormData();
    formData.append('file', sesamiFile);
    formData.append('gas', sesamiGas);
    formData.append('version', sesamiVersion);

    try {
      const response = await fetch(buildAppPath('api/sesami/bet'), {
        method: 'POST',
        body: formData,
      });
      const data = await readApiJson<JobSnapshot<SesamiResult> & { error?: string }>(response, locale, t.failed);
      if (!response.ok) {
        throw new Error(data.error || t.failed);
      }
      setSesamiJob(data);
    } catch (error) {
      setSesamiError(error instanceof Error ? error.message : t.failed);
    } finally {
      setSesamiSubmitting(false);
    }
  }

  async function runZeopp() {
    if (!zeoppFile) {
      setZeoppError(t.zeopp.noFile);
      return;
    }

    setZeoppSubmitting(true);
    setZeoppError('');
    setZeoppWarning('');
    setZeoppResult(null);
    setZeoppJob(null);
    setZeoppActionMessage('');

    const formData = new FormData();
    formData.append('file', zeoppFile);
    formData.append('chanRadius', String(chanRadius));
    formData.append('probeRadius', String(probeRadius));
    formData.append('numSamples', String(numSamples));

    try {
      const response = await fetch(buildAppPath('api/zeopp/psd'), {
        method: 'POST',
        body: formData,
      });
      const data = await readApiJson<JobSnapshot<ZeoppResult> & { error?: string; hint?: string }>(response, locale, t.failed);
      if (!response.ok) {
        throw new Error(data.error || data.hint || t.failed);
      }
      setZeoppJob(data);
    } catch (error) {
      setZeoppError(error instanceof Error ? error.message : t.failed);
    } finally {
      setZeoppSubmitting(false);
    }
  }

  function flashZeoppActionMessage(message: string) {
    setZeoppActionMessage(message);
    window.setTimeout(() => {
      setZeoppActionMessage('');
    }, 1800);
  }

  async function copyZeoppRawOutput() {
    if (!zeoppResult?.rawOutput) {
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(zeoppResult.rawOutput);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = zeoppResult.rawOutput;
        textarea.setAttribute('readonly', 'true');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      flashZeoppActionMessage(locale === 'zh' ? '\u5df2\u590d\u5236\u539f\u59cb\u8f93\u51fa' : 'Raw output copied');
    } catch {
      flashZeoppActionMessage(locale === 'zh' ? '\u590d\u5236\u5931\u8d25' : 'Copy failed');
    }
  }

  function downloadZeoppRawOutput(format: 'txt' | 'md') {
    if (!zeoppResult?.rawOutput) {
      return;
    }

    const baseName = (zeoppJob?.filename || zeoppFile?.name || 'zeopp-psd').replace(/\.[^.]+$/, '');
    if (format === 'txt') {
      triggerTextDownload(`${baseName}-psd-raw.txt`, zeoppResult.rawOutput, 'text/plain;charset=utf-8');
      flashZeoppActionMessage(locale === 'zh' ? '\u5df2\u5bfc\u51fa TXT' : 'TXT exported');
      return;
    }

    const markdown = buildZeoppMarkdown(locale, zeoppResult, zeoppJob?.filename || zeoppFile?.name);
    triggerTextDownload(`${baseName}-psd-raw.md`, markdown, 'text/markdown;charset=utf-8');
    flashZeoppActionMessage(locale === 'zh' ? '\u5df2\u5bfc\u51fa MD' : 'Markdown exported');
  }

  return (
    <Box className="page-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <Paper className="app-frame" radius={32}>
        <Group justify="space-between" align="flex-start" className="topbar">
          <div>
            <Group gap="sm" mb={10}>
              <Badge variant="light" color="ocean" radius="xl">
                {heroSubtitle}
              </Badge>
              <Badge variant="white" radius="xl" className="ghost-badge">
                v0.5
              </Badge>
            </Group>
            <div className="hero-brand-row">
              <img className="hero-logo" src={heroLogoUrl} alt={heroLogoAlt} />
              <h1 className="hero-title">
                <span className="hero-wordmark" aria-label={heroTitle}>
                  <span>Che</span>
                  <span className="hero-accent">m</span>
                  <span>E</span>
                  <span className="hero-accent">x</span>
                </span>
              </h1>
            </div>
            <Text className="hero-text">{heroBody}</Text>
            <Text className="hero-footnote">{heroFootnote}</Text>
          </div>

          <Paper className="language-switch" radius="xl">
            <Group gap="xs" mb={8}>
              <ActionIcon variant="subtle" radius="xl" color="ocean">
                <IconLanguage size={18} />
              </ActionIcon>
              <Text size="sm" fw={600}>
                {t.languageLabel}
              </Text>
            </Group>
            <SegmentedControl
              value={locale}
              onChange={(value) => setLocale(value as Locale)}
              data={[
                { label: '中文', value: 'zh' },
                { label: 'English', value: 'en' },
              ]}
              fullWidth
              radius="xl"
            />
          </Paper>
        </Group>


        <Tabs value={activeTab} onChange={(value) => setActiveTab((value as ToolKey) || 'sesami')} className="workspace-tabs">
          <Tabs.List className="glass-tabs-list">
            <Tabs.Tab value="sesami" leftSection={<IconDroplet size={16} />}>
              {t.tabs.sesami}
            </Tabs.Tab>
            <Tabs.Tab value="zeopp" leftSection={<IconAtom2 size={16} />}>
              {t.tabs.zeopp}
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="sesami" pt="lg">
            <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
              <Paper className="glass-card feature-card" radius={28}>
                <Stack gap="md">
                  <div>
                    <Text className="panel-title">{t.sesami.title}</Text>
                    <Text className="panel-hint">{t.sesami.desc}</Text>
                  </div>

                  <FileButton onChange={setSesamiFile} accept=".csv,.aif">
                    {(props) => (
                      <Button {...props} leftSection={<IconUpload size={16} />} radius="xl" className="secondary-button">
                        {t.sesami.upload}
                      </Button>
                    )}
                  </FileButton>

                  <Paper className="mini-dropzone" radius="xl">
                    <Text fw={700}>{sesamiFile ? sesamiFile.name : t.sesami.noFile}</Text>
                    <Text size="sm" c="dimmed" mt={6}>
                      {t.sesami.accepted}
                    </Text>
                  </Paper>

                  <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                    <Select
                      label={sesamiVersionLabel}
                      value={sesamiVersion}
                      onChange={(value) => setSesamiVersion(value || '2.9')}
                      data={[
                        { value: '2.9', label: 'SESAMI 2.9' },
                        { value: '1.0', label: 'SESAMI 1.0' },
                      ]}
                      radius="xl"
                    />
                    <Select
                      label={t.sesami.gas}
                      value={sesamiGas}
                      onChange={(value) => setSesamiGas(value || 'Argon')}
                      data={[
                        { value: 'Argon', label: 'Argon (87 K)' },
                        { value: 'Nitrogen', label: 'Nitrogen (77 K)' },
                      ]}
                      radius="xl"
                    />
                  </SimpleGrid>

                  <Button
                    radius="xl"
                    className="primary-button progress-button"
                    style={getProgressStyle(sesamiProgress)}
                    onClick={() => void runSesami()}
                    disabled={sesamiBusy}
                  >
                    {sesamiBusy ? `${sesamiStageLabel} ${Math.round(sesamiProgress)}%` : t.sesami.run}
                  </Button>

                  {sesamiBusy ? <Text className="progress-meta">{sesamiStageLabel}</Text> : null}
                  {sesamiWarning ? <Text className="notice-text">{sesamiWarning}</Text> : null}
                  {sesamiError ? <Text className="error-text">{sesamiError}</Text> : null}
                </Stack>
              </Paper>

              <Paper className="glass-card feature-card" radius={28}>
                {sesamiResult ? (
                  <Stack gap="md">
                    <Group gap="xs">
                      <Badge radius="xl" variant="light" color="ocean">
                        {sesamiResult.engine || 'SESAMI'}
                      </Badge>
                      <Badge radius="xl" variant="white" className="ghost-badge">
                        BET
                      </Badge>
                    </Group>
                    <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm">
                      <MetricCard label={t.sesami.metrics.area} value={`${sesamiResult.area} m\u00b2/g`} />
                      <MetricCard label={t.sesami.metrics.qm} value={`${sesamiResult.qm} mol/kg`} />
                      <MetricCard label={t.sesami.metrics.c} value={`${sesamiResult.C}`} />
                      <MetricCard label={t.sesami.metrics.r2} value={`${sesamiResult.r2}`} />
                      <MetricCard
                        label={t.sesami.metrics.region}
                        value={`${Math.round(sesamiResult.linearRegion.lowPressurePa)}-${Math.round(sesamiResult.linearRegion.highPressurePa)} Pa`}
                      />
                      <MetricCard label={locale === 'zh' ? '\u70b9\u6570' : 'Points'} value={`${sesamiResult.selectedPoints.length || sesamiResult.linearRegion.count}`} />
                    </SimpleGrid>

                    {sesamiResult.plots.length ? (
                      <div>
                        <Text className="panel-title">{locale === 'zh' ? '\u7ed3\u679c\u56fe\u96c6' : 'Result gallery'}</Text>
                        <Text className="panel-hint">
                          {locale === 'zh'
                            ? '\u4ee5\u4e0b\u5c55\u793a\u672c\u6b21 BET \u5206\u6790\u751f\u6210\u7684\u5168\u90e8\u56fe\u50cf\uff0c\u70b9\u51fb\u4efb\u610f\u56fe\u53ef\u653e\u5927\u67e5\u770b\u3002'
                            : 'All figures generated in this BET analysis are shown below. Click any figure to enlarge it.'}
                        </Text>
                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm" mt="sm">
                          {sesamiResult.plots.map((plot) => {
                            const label = getSesamiPlotLabel(locale, plot.name);
                            return (
                              <button
                                key={plot.url}
                                type="button"
                                className="plot-card-button"
                                onClick={() => setActiveSesamiPlot(plot)}
                              >
                                <Text className="plot-card-title">{label}</Text>
                                <img className="result-image clickable-image" src={plot.url} alt={label} />
                              </button>
                            );
                          })}
                        </SimpleGrid>
                      </div>
                    ) : sesamiResult.plotUrl ? (
                      <button
                        type="button"
                        className="plot-card-button"
                        onClick={() =>
                          setActiveSesamiPlot({
                            name: 'isotherm.png',
                            url: sesamiResult.plotUrl as string,
                          })
                        }
                      >
                        <Text className="plot-card-title">{locale === 'zh' ? '\u7ed3\u679c\u56fe\u50cf' : 'Result figure'}</Text>
                        <img className="result-image clickable-image" src={sesamiResult.plotUrl} alt="SESAMI BET plot" />
                      </button>
                    ) : null}

                    <Paper className="result-preview region-summary-card" radius="xl">
                      <Text className="cluster-title">{locale === 'zh' ? 'BET \u62df\u5408\u533a\u95f4' : 'BET fitting region'}</Text>
                      <Text className="result-preview-text">{buildSesamiRegionSummary(locale, sesamiResult)}</Text>
                    </Paper>

                    <div>
                      <Text className="panel-title">{locale === 'zh' ? 'BET \u533a\u95f4\u70b9\u4f4d' : 'BET region points'}</Text>
                      <Text className="panel-hint">
                        {locale === 'zh'
                          ? '\u4e0b\u8868\u5217\u51fa\u672c\u6b21\u53c2\u4e0e BET \u7ebf\u6027\u62df\u5408\u7684\u6570\u636e\u70b9\u3002'
                          : 'The table below lists the points used in the BET linear fit.'}
                      </Text>
                      <div className="region-table-wrap">
                        <table className="region-table">
                          <thead>
                            <tr>
                              <th>#</th>
                              <th>P/P0</th>
                              <th>{locale === 'zh' ? '\u538b\u529b (Pa)' : 'Pressure (Pa)'}</th>
                              <th>{locale === 'zh' ? '\u5438\u9644\u91cf (mol/kg)' : 'Loading (mol/kg)'}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sesamiResult.selectedPoints.length ? (
                              sesamiResult.selectedPoints.map((point, index) => (
                                <tr key={`${point.Pressure ?? index}-${index}`}>
                                  <td>{index + 1}</td>
                                  <td>{formatSesamiNumber(point.P_rel, 6)}</td>
                                  <td>{formatSesamiNumber(point.Pressure, 2)}</td>
                                  <td>{formatSesamiNumber(point.Loading, 6)}</td>
                                </tr>
                              ))
                            ) : (
                              <tr>
                                <td colSpan={4}>{locale === 'zh' ? '\u6682\u65e0\u533a\u95f4\u70b9\u6570\u636e\u3002' : 'No BET region points returned.'}</td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </Stack>
                ) : (
                  <ResultPlaceholder title="SESAMI" body={t.sesami.desc} />
                )}
              </Paper>
            </SimpleGrid>
          </Tabs.Panel>

          <Tabs.Panel value="zeopp" pt="lg">
            <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
              <Paper className="glass-card feature-card" radius={28}>
                <Stack gap="md">
                  <div>
                    <Text className="panel-title">{t.zeopp.title}</Text>
                    <Text className="panel-hint">{t.zeopp.desc}</Text>
                  </div>

                  <FileButton onChange={setZeoppFile} accept=".cif,.cssr,.res,.cuc,.v1">
                    {(props) => (
                      <Button {...props} leftSection={<IconUpload size={16} />} radius="xl" className="secondary-button">
                        {t.zeopp.upload}
                      </Button>
                    )}
                  </FileButton>

                  <Paper className="mini-dropzone" radius="xl">
                    <Text fw={700}>{zeoppFile ? zeoppFile.name : t.zeopp.noFile}</Text>
                    <Text size="sm" c="dimmed" mt={6}>
                      {t.zeopp.accepted}
                    </Text>
                  </Paper>

                  <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm">
                    <NumberInput label={t.zeopp.chanRadius} value={chanRadius} onChange={setChanRadius} radius="xl" min={0} decimalScale={3} />
                    <NumberInput label={t.zeopp.probeRadius} value={probeRadius} onChange={setProbeRadius} radius="xl" min={0} decimalScale={3} />
                    <NumberInput label={t.zeopp.numSamples} value={numSamples} onChange={setNumSamples} radius="xl" min={100} step={1000} />
                  </SimpleGrid>

                  <Button
                    radius="xl"
                    className="primary-button progress-button"
                    style={getProgressStyle(zeoppProgress)}
                    onClick={() => void runZeopp()}
                    disabled={zeoppBusy}
                  >
                    {zeoppBusy ? `${zeoppStageLabel} ${Math.round(zeoppProgress)}%` : t.zeopp.run}
                  </Button>

                  {zeoppBusy ? <Text className="progress-meta">{zeoppStageLabel}</Text> : null}
                  {zeoppWarning ? <Text className="notice-text">{zeoppWarning}</Text> : null}
                  {zeoppError ? <Text className="error-text">{zeoppError}</Text> : null}
                </Stack>
              </Paper>

              <Paper className="glass-card feature-card" radius={28}>
                {zeoppStatus?.available && zeoppResult ? (
                  <Stack gap="md">
                    <Group gap="xs">
                      <Badge radius="xl" variant="light" color="ocean">
                        ZEO++
                      </Badge>
                      <Badge radius="xl" variant="white" className="ghost-badge">
                        PSD
                      </Badge>
                    </Group>
                    <MiniPlot rows={zeoppResult.rows} locale={locale} />
                    <Paper className="code-panel" radius="xl">
                      <Group justify="space-between" align="flex-start" gap="sm">
                        <Text className="cluster-title">{t.zeopp.rawOutput}</Text>
                        <Group gap="xs" className="raw-output-actions">
                          <Button size="xs" radius="xl" variant="default" onClick={() => void copyZeoppRawOutput()}>
                            {locale === 'zh' ? '\u590d\u5236' : 'Copy'}
                          </Button>
                          <Button size="xs" radius="xl" variant="default" onClick={() => downloadZeoppRawOutput('txt')}>
                            TXT
                          </Button>
                          <Button size="xs" radius="xl" variant="default" onClick={() => downloadZeoppRawOutput('md')}>
                            MD
                          </Button>
                        </Group>
                      </Group>
                      {zeoppActionMessage ? <Text className="copy-hint">{zeoppActionMessage}</Text> : null}
                      <Text component="pre" className="code-block">
                        {zeoppResult.rawOutput}
                      </Text>
                    </Paper>
                  </Stack>
                ) : (
                  <Stack gap="md" h="100%" justify="space-between">
                    <div>
                      <Text className="panel-title">{zeoppStatus?.available ? t.zeopp.title : t.zeopp.unavailableTitle}</Text>
                      <Text className="panel-hint">{zeoppStatus?.message || (zeoppStatus?.available ? t.zeopp.desc : t.zeopp.unavailableBody)}</Text>
                    </div>
                    <Paper className="result-preview" radius="xl">
                      <Group justify="space-between">
                        <div>
                          <Text className="result-preview-label">Runtime check</Text>
                          <Text className="result-preview-title">{zeoppStatus?.available ? 'Ready' : 'Blocked'}</Text>
                          <Text className="result-preview-text">{zeoppStatus?.binaryPath || zeoppStatus?.message || t.zeopp.unavailableBody}</Text>
                        </div>
                        <ActionIcon size={44} radius="xl" variant="light" color="ocean">
                          <IconSparkles size={20} />
                        </ActionIcon>
                      </Group>
                    </Paper>
                  </Stack>
                )}
              </Paper>
            </SimpleGrid>
          </Tabs.Panel>
        </Tabs>

        <Paper className="footer-note" radius="xl">
          <div className="footer-status-bar">
            <div>
              <Text className="footer-brand">ChemEx</Text>
              <Text className="footer-subcopy">
                {locale === 'zh' ? 'COF\u591a\u529f\u80fd\u8ba1\u7b97\u5de5\u5177\u7bb1 \u00b7 v0.5' : 'Multipurpose COF Toolbox \u00b7 v0.5'}
              </Text>
            </div>
            <div className="status-pill-group">
              <CompactStatusPill
                label={t.health.online}
                value={onlineHealthy ? (locale === 'zh' ? '\u6b63\u5e38' : 'Online') : '...'}
                hint={health ? (locale === 'zh' ? 'API \u5df2\u5c31\u7eea' : 'API ready') : 'Checking'}
                ok={onlineHealthy}
              />
              <CompactStatusPill
                label={t.health.sesami}
                value={sesamiHealthy ? 'Ready' : '...'}
                hint={health?.sesamiMessage || 'SESAMI BET engine'}
                ok={sesamiHealthy}
              />
              <CompactStatusPill
                label={t.health.zeopp}
                value={zeoppHealthy ? 'Ready' : 'Blocked'}
                hint={zeoppStatus?.message || health?.zeoppMessage || 'Checking'}
                ok={zeoppHealthy}
              />
            </div>
          </div>
        </Paper>
      </Paper>

      <Modal
        opened={Boolean(activeSesamiPlot)}
        onClose={() => setActiveSesamiPlot(null)}
        centered
        size="80rem"
        title={activeSesamiPlot ? getSesamiPlotLabel(locale, activeSesamiPlot.name) : ''}
      >
        {activeSesamiPlot ? (
          <img
            className="lightbox-image"
            src={activeSesamiPlot.url}
            alt={getSesamiPlotLabel(locale, activeSesamiPlot.name)}
          />
        ) : null}
      </Modal>
    </Box>
  );
}

function CompactStatusPill({ label, value, hint, ok }: { label: string; value: string; hint: string; ok: boolean }) {
  return (
    <div className={ok ? 'status-pill is-ok' : 'status-pill is-pending'} title={[label, hint].join(': ')}>
      <span className="status-pill-dot" aria-hidden="true" />
      <div className="status-pill-content">
        <Text className="status-pill-label">{label}</Text>
        <Text className="status-pill-value">{value}</Text>
        <Text className="status-pill-hint">{hint}</Text>
      </div>
    </div>
  );
}
function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Paper className="cluster-card" radius="xl">
      <Text className="cluster-title">{label}</Text>
      <Text className="summary-title">{value}</Text>
    </Paper>
  );
}

function normalizeSesamiResult(result: SesamiResult | null | undefined): SesamiResult | null {
  if (!result) {
    return null;
  }

  const plots = Array.isArray(result.plots)
    ? result.plots
        .filter((plot): plot is SesamiPlot => Boolean(plot?.url && plot?.name))
        .map((plot) => ({
          ...plot,
          url: normalizeAppUrl(plot.url) || plot.url,
        }))
    : [];

  if (!plots.length && result.plotUrl) {
    plots.push({ name: 'isotherm.png', url: normalizeAppUrl(result.plotUrl) || result.plotUrl });
  }

  const selectedPoints = Array.isArray(result.selectedPoints)
    ? result.selectedPoints
    : Array.isArray(result.linearRegionPoints)
      ? result.linearRegionPoints
      : [];

  return {
    ...result,
    plotUrl: normalizeAppUrl(result.plotUrl),
    plots,
    points: Array.isArray(result.points) ? result.points : [],
    selectedPoints,
    linearRegionPoints: selectedPoints,
  };
}

function normalizeBasePath(basePath: string) {
  if (!basePath || basePath === '/') {
    return '/';
  }

  const trimmed = basePath.replace(/^\/+|\/+$/g, '');
  return trimmed ? `/${trimmed}/` : '/';
}

function detectRuntimeBasePath() {
  if (typeof window === 'undefined') {
    return '/';
  }

  try {
    const assetDir = new URL('.', import.meta.url).pathname;
    if (assetDir.endsWith('/assets/')) {
      return normalizeBasePath(assetDir.slice(0, -'assets/'.length));
    }
    return normalizeBasePath(assetDir);
  } catch {
    return normalizeBasePath(window.location.pathname.startsWith('/chemex/') || window.location.pathname === '/chemex' ? '/chemex/' : '/');
  }
}

async function readApiJson<T>(response: Response, locale: Locale, fallbackMessage: string): Promise<T> {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  const rawText = await response.text();
  throw new Error(formatUnexpectedApiResponse(locale, response.status, rawText, fallbackMessage));
}

function formatUnexpectedApiResponse(locale: Locale, status: number, rawText: string, fallbackMessage: string) {
  if (status == 413) {
    return locale === 'zh'
      ? '\u4e0a\u4f20\u6587\u4ef6\u8fc7\u5927\uff0c\u670d\u52a1\u5668\u62d2\u7edd\u4e86\u672c\u6b21\u8bf7\u6c42\uff08HTTP 413\uff09\u3002\u8bf7\u538b\u7f29\u6587\u4ef6\u6216\u8054\u7cfb\u7ba1\u7406\u5458\u63d0\u9ad8\u4e0a\u4f20\u4e0a\u9650\u3002'
      : 'Upload rejected because the file is too large (HTTP 413). Compress the file or increase the server upload limit.';
  }

  const normalizedText = rawText.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  if (!normalizedText) {
    return fallbackMessage;
  }

  return locale === 'zh'
    ? `\u670d\u52a1\u5668\u8fd4\u56de\u4e86\u975e JSON \u54cd\u5e94\uff08HTTP ${status}\uff09\uff1a${normalizedText}`
    : `Server returned a non-JSON response (HTTP ${status}): ${normalizedText}`;
}

function buildAppPath(path: string) {
  return `${APP_BASE_PATH}${path.replace(/^\/+/, '')}`;
}

function normalizeAppUrl(url?: string | null) {
  if (!url) {
    return null;
  }
  if (/^[a-z]+:/i.test(url)) {
    return url;
  }
  return buildAppPath(url.replace(/^\/+/, ''));
}
function getSesamiPlotLabel(locale: Locale, filename: string) {
  const labels: Record<string, Record<Locale, string>> = {
    'isotherm.png': { zh: '\u7b49\u6e29\u7ebf\u56fe', en: 'Isotherm plot' },
    'BETPlotLinear.png': { zh: 'BET \u7ebf\u6027\u533a\u56fe', en: 'BET linear region plot' },
    'BETPlot.png': { zh: 'BET \u4e00\u81f4\u6027\u56fe', en: 'BET consistency plot' },
    'ESWPlot.png': { zh: 'ESW \u56fe', en: 'ESW plot' },
    'BETESWPlot.png': { zh: 'BET+ESW \u7ebf\u6027\u533a\u56fe', en: 'BET+ESW linear region plot' },
    'multiplot_0.png': { zh: 'SESAMI \u6c47\u603b\u56fe', en: 'SESAMI summary plot' },
  };
  return labels[filename]?.[locale] || filename;
}

function formatSesamiNumber(value?: number, decimals = 4) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '-';
  }
  return value.toFixed(decimals).replace(/0+$/, '').replace(/\.$/, '');
}

function buildSesamiRegionSummary(locale: Locale, result: SesamiResult) {
  const relativeValues = result.selectedPoints
    .map((point) => point.P_rel)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  const relativeSummary = relativeValues.length
    ? `P/P0 ${formatSesamiNumber(Math.min(...relativeValues), 6)} - ${formatSesamiNumber(Math.max(...relativeValues), 6)}`
    : null;
  const pressureSummary = `${Math.round(result.linearRegion.lowPressurePa)}-${Math.round(result.linearRegion.highPressurePa)} Pa`;
  const countSummary = locale === 'zh' ? `\u5171 ${result.selectedPoints.length || result.linearRegion.count} \u4e2a\u70b9` : `${result.selectedPoints.length || result.linearRegion.count} points`;

  if (locale === 'zh') {
    return [
      `\u538b\u529b\u8303\u56f4 ${pressureSummary}` ,
      relativeSummary,
      countSummary,
    ]
      .filter(Boolean)
      .join(' | ');
  }

  return [
    `Pressure range ${pressureSummary}`,
    relativeSummary,
    countSummary,
  ]
    .filter(Boolean)
    .join(' | ');
}

function triggerTextDownload(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function buildZeoppMarkdown(locale: Locale, result: ZeoppResult, filename?: string) {
  const title = locale === 'zh' ? '# ZEO++ PSD ????' : '# ZEO++ PSD Raw Output';
  const sourceLine = filename
    ? locale === 'zh'
      ? `- ??: ${filename}`
      : `- File: ${filename}`
    : null;
  const pointLine = locale === 'zh' ? `- ????: ${result.rows.length}` : `- Points: ${result.rows.length}`;
  return [title, sourceLine, pointLine, '', '```text', result.rawOutput.trimEnd(), '```'].filter(Boolean).join('\n');
}

function ResultPlaceholder({ title, body }: { title: string; body: string }) {
  return (
    <Stack justify="space-between" h="100%">
      <div>
        <Text className="panel-title">{title}</Text>
        <Text className="panel-hint">{body}</Text>
      </div>
      <Paper className="result-preview" radius="xl">
        <Text className="result-preview-label">Pending result</Text>
        <Text className="result-preview-title">Upload a file and run</Text>
        <Text className="result-preview-text">The returned metrics and plot will be rendered here.</Text>
      </Paper>
    </Stack>
  );
}

function buildTicks(min: number, max: number, count: number) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return [];
  }
  if (Math.abs(max - min) < 1e-9) {
    return [min];
  }
  return Array.from({ length: count }, (_, index) => min + ((max - min) * index) / (count - 1));
}

function formatTick(value: number, max: number) {
  if (max >= 100) {
    return value.toFixed(0);
  }
  if (max >= 10) {
    return value.toFixed(1).replace(/\.0$/, '');
  }
  if (max >= 1) {
    return value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
  }
  return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
}

function MiniPlot({ rows, locale }: { rows: Array<{ diameter: number; value: number }>; locale: Locale }) {
  const [hoveredPoint, setHoveredPoint] = useState<{
    diameter: number;
    value: number;
    svgX: number;
    svgY: number;
  } | null>(null);

  if (!rows.length) {
    return <Text size="sm">{locale === 'zh' ? '\u672a\u8fd4\u56de PSD \u6570\u636e\u70b9\u3002' : 'No PSD points returned.'}</Text>;
  }

  const width = 560;
  const height = 290;
  const chartLeft = 64;
  const chartRight = 20;
  const chartTop = 20;
  const chartBottom = 48;
  const chartWidth = width - chartLeft - chartRight;
  const chartHeight = height - chartTop - chartBottom;

  const diameters = rows.map((row) => row.diameter);
  const values = rows.map((row) => row.value);
  const positiveRows = rows.filter((row) => row.value > 0);
  const binSize = rows.length > 1 ? Math.max(Math.abs(rows[1].diameter - rows[0].diameter), 0.1) : 1;
  const lastMeaningfulDiameter = positiveRows.length ? positiveRows[positiveRows.length - 1].diameter : rows[rows.length - 1].diameter;
  const paddedMax = Math.max(lastMeaningfulDiameter + binSize * 2, lastMeaningfulDiameter * 1.08, binSize * 8);
  const xMin = 0;
  const xMax = Math.min(rows[rows.length - 1].diameter, paddedMax);
  const displayRows = rows.filter((row) => row.diameter <= xMax + 1e-9);
  const plotRows = displayRows.length >= 2 ? displayRows : rows;
  const yMin = 0;
  const yMax = Math.max(...plotRows.map((row) => row.value), 1);

  const xScale = (value: number) => chartLeft + ((value - xMin) / Math.max(xMax - xMin, 1e-9)) * chartWidth;
  const yScale = (value: number) => chartTop + chartHeight - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * chartHeight;

  const linePath = plotRows
    .map((row, index) => `${index === 0 ? 'M' : 'L'} ${xScale(row.diameter).toFixed(2)} ${yScale(row.value).toFixed(2)}`)
    .join(' ');
  const areaPath = `${linePath} L ${xScale(plotRows[plotRows.length - 1].diameter).toFixed(2)} ${(chartTop + chartHeight).toFixed(2)} L ${xScale(plotRows[0].diameter).toFixed(2)} ${(chartTop + chartHeight).toFixed(2)} Z`;

  const xTicks = buildTicks(xMin, xMax, 6);
  const yTicks = buildTicks(yMin, yMax, 5);
  const xLabel = locale === 'zh' ? '\u5b54\u5f84 (\u00c5)' : 'Pore diameter (\u00c5)';
  const yLabel = locale === 'zh' ? '\u8ba1\u6570' : 'Count';
  const ariaLabel = locale === 'zh' ? '\u5b54\u5f84\u5206\u5e03\u56fe' : 'Pore size distribution plot';

  const handlePointerMove = (event: ReactMouseEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const svgX = ((event.clientX - bounds.left) / bounds.width) * width;
    const clampedSvgX = Math.min(chartLeft + chartWidth, Math.max(chartLeft, svgX));
    const dataX = xMin + ((clampedSvgX - chartLeft) / chartWidth) * Math.max(xMax - xMin, 1e-9);

    let nearest = plotRows[0];
    for (const row of plotRows) {
      if (Math.abs(row.diameter - dataX) < Math.abs(nearest.diameter - dataX)) {
        nearest = row;
      }
    }

    setHoveredPoint({
      diameter: nearest.diameter,
      value: nearest.value,
      svgX: xScale(nearest.diameter),
      svgY: yScale(nearest.value),
    });
  };

  const tooltipWidth = 148;
  const tooltipHeight = 46;
  const tooltipX = hoveredPoint
    ? hoveredPoint.svgX > width - tooltipWidth - 16
      ? hoveredPoint.svgX - tooltipWidth - 12
      : hoveredPoint.svgX + 12
    : 0;
  const tooltipY = hoveredPoint
    ? hoveredPoint.svgY < chartTop + 44
      ? hoveredPoint.svgY + 12
      : hoveredPoint.svgY - tooltipHeight - 10
    : 0;

  return (
    <div className="plot-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="plot-svg" role="img" aria-label={ariaLabel}>
        <rect x="0" y="0" width={width} height={height} rx="24" fill="rgba(255,255,255,0.58)" />

        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line x1={chartLeft} y1={yScale(tick)} x2={chartLeft + chartWidth} y2={yScale(tick)} stroke="rgba(45,121,191,0.12)" strokeWidth="1" />
            <text x={chartLeft - 10} y={yScale(tick) + 4} textAnchor="end" fontSize="11" fill="rgba(19,38,58,0.62)">{formatTick(tick, yMax)}</text>
          </g>
        ))}

        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line x1={xScale(tick)} y1={chartTop} x2={xScale(tick)} y2={chartTop + chartHeight} stroke="rgba(45,121,191,0.08)" strokeWidth="1" />
            <text x={xScale(tick)} y={chartTop + chartHeight + 18} textAnchor="middle" fontSize="11" fill="rgba(19,38,58,0.62)">{formatTick(tick, xMax)}</text>
          </g>
        ))}

        <line x1={chartLeft} y1={chartTop + chartHeight} x2={chartLeft + chartWidth} y2={chartTop + chartHeight} stroke="rgba(19,38,58,0.4)" strokeWidth="1.25" />
        <line x1={chartLeft} y1={chartTop} x2={chartLeft} y2={chartTop + chartHeight} stroke="rgba(19,38,58,0.4)" strokeWidth="1.25" />

        <path d={areaPath} fill="rgba(45,121,191,0.14)" />
        <path d={linePath} fill="none" stroke="#2d79bf" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />

        {hoveredPoint ? (
          <g>
            <line x1={hoveredPoint.svgX} y1={chartTop} x2={hoveredPoint.svgX} y2={chartTop + chartHeight} stroke="rgba(45,121,191,0.22)" strokeWidth="1" strokeDasharray="4 4" />
            <circle cx={hoveredPoint.svgX} cy={hoveredPoint.svgY} r={5} fill="#2d79bf" stroke="white" strokeWidth="2" />
            <rect x={tooltipX} y={tooltipY} width={tooltipWidth} height={tooltipHeight} rx={12} fill="rgba(12, 28, 43, 0.9)" />
            <text x={tooltipX + 12} y={tooltipY + 18} fontSize="11" fill="white">{locale === 'zh' ? `\u5b54\u5f84 ${formatTick(hoveredPoint.diameter, xMax)} \u00c5` : `Diameter ${formatTick(hoveredPoint.diameter, xMax)} \u00c5`}</text>
            <text x={tooltipX + 12} y={tooltipY + 34} fontSize="11" fill="white">{locale === 'zh' ? `\u8ba1\u6570 ${formatTick(hoveredPoint.value, yMax)}` : `Count ${formatTick(hoveredPoint.value, yMax)}`}</text>
          </g>
        ) : null}

        <rect
          x={chartLeft}
          y={chartTop}
          width={chartWidth}
          height={chartHeight}
          fill="transparent"
          onMouseMove={handlePointerMove}
          onMouseLeave={() => setHoveredPoint(null)}
        />

        <text x={chartLeft + chartWidth / 2} y={height - 12} textAnchor="middle" fontSize="12" fontWeight="700" fill="rgba(19,38,58,0.78)">{xLabel}</text>
        <text x={18} y={chartTop + chartHeight / 2} textAnchor="middle" transform={`rotate(-90 18 ${chartTop + chartHeight / 2})`} fontSize="12" fontWeight="700" fill="rgba(19,38,58,0.78)">{yLabel}</text>
      </svg>
    </div>
  );
}

export default App;


