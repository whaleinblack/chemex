import { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  FileButton,
  Group,
  Modal,
  NumberInput,
  Paper,
  Select,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
} from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { fetchJob, submitSesamiJob } from '../../lib/api';
import type {
  JobSnapshot,
  Locale,
  SesamiPoint,
  SesamiResult,
  SesamiSubtab,
  SesamiVersion,
} from '../../lib/types';

type Props = {
  locale: Locale;
};

type SesamiStrings = {
  subtabs: Record<SesamiSubtab, string>;
  descriptions: Record<SesamiSubtab, string>;
  upload: string;
  noFile: string;
  gas: string;
  version: string;
  run: string;
  runAdvanced: string;
  analysis: string;
  compareHint: string;
  betmlHint: string;
  advHint: string;
  pending: string;
  emptyTitle: string;
  emptyBody: string;
  regionTitle: string;
  plotsTitle: string;
  comparisonTitle: string;
  metrics: {
    area: string;
    qm: string;
    c: string;
    r2: string;
    region: string;
    betMl: string;
  };
  advanced: {
    r2Cutoff: string;
    r2Min: string;
    dpi: string;
    fontSize: string;
    legend: string;
  };
  versionFixed: string;
};

const copy: Record<Locale, SesamiStrings> = {
  zh: {
    subtabs: {
      bet: 'BET',
      betEsw: 'BET+ESW',
      betMl: 'BET-ML',
      compare: 'Compare',
      advanced: 'Advanced',
    },
    descriptions: {
      bet: '上传 CSV / AIF，使用所选 SESAMI 版本执行 BET 比表面积计算，并返回线性区与全套图像。',
      betEsw: '使用 SESAMI 2.9 的 BET+ESW 逻辑，强制拟合区包含第一个 ESW minimum。',
      betMl: '使用 SESAMI 2.9 的机器学习模型快速预测表面积，适合做快速筛查。',
      compare: '同一份等温线同时比较 BET、BET+ESW、Legacy BET 与 BET-ML，便于交叉判断。',
      advanced: '专家模式可调整 R²、dpi、字体与图例，并选择以 BET 或 BET+ESW 方式运行。',
    },
    upload: '上传等温线文件',
    noFile: '未选择 CSV / AIF 文件',
    gas: '吸附气体',
    version: 'SESAMI 版本',
    run: '开始计算',
    runAdvanced: '运行高级分析',
    analysis: '分析模式',
    compareHint: 'Compare 固定使用 SESAMI 2.9 主结果并尽可能附带 legacy / ML 对照。',
    betmlHint: 'BET-ML 由 SESAMI 2.9 模型给出预测面积，当前仍接受 CSV / AIF 上传。',
    advHint: '当分析模式切换为 BET+ESW 时，会自动使用 SESAMI 2.9。',
    pending: '上传文件后开始计算，结果、图像与线性区会显示在这里。',
    emptyTitle: '等待计算结果',
    emptyBody: '当前页面已接入真实 job 轮询，提交后会自动更新进度与结果。',
    regionTitle: 'BET 线性区点位',
    plotsTitle: '输出图像',
    comparisonTitle: '对比结果',
    metrics: {
      area: '表面积',
      qm: 'qm',
      c: 'C 常数',
      r2: '线性 R²',
      region: '线性区',
      betMl: 'ML 预测面积',
    },
    advanced: {
      r2Cutoff: 'R² cutoff',
      r2Min: 'R² min',
      dpi: '图像 DPI',
      fontSize: '字体大小',
      legend: '显示图例',
    },
    versionFixed: '该模式固定使用 SESAMI 2.9',
  },
  en: {
    subtabs: {
      bet: 'BET',
      betEsw: 'BET+ESW',
      betMl: 'BET-ML',
      compare: 'Compare',
      advanced: 'Advanced',
    },
    descriptions: {
      bet: 'Upload CSV / AIF and run BET surface-area analysis with the selected SESAMI version, including the linear region and full plot set.',
      betEsw: 'Run the SESAMI 2.9 BET+ESW workflow, forcing the selected region to include the first ESW minimum.',
      betMl: 'Use the SESAMI 2.9 machine-learning model for a fast surface-area prediction workflow.',
      compare: 'Run BET, BET+ESW, Legacy BET, and BET-ML side by side on the same isotherm for cross-checking.',
      advanced: 'Expert mode exposes R² thresholds, dpi, font, legend, and a selectable BET / BET+ESW analysis target.',
    },
    upload: 'Upload isotherm file',
    noFile: 'No CSV / AIF selected',
    gas: 'Adsorbate gas',
    version: 'SESAMI version',
    run: 'Run analysis',
    runAdvanced: 'Run advanced analysis',
    analysis: 'Analysis mode',
    compareHint: 'Compare uses the SESAMI 2.9 modern workflow and adds legacy / ML counterparts when available.',
    betmlHint: 'BET-ML returns a fast predicted surface area from the SESAMI 2.9 model.',
    advHint: 'When the advanced mode switches to BET+ESW, the run automatically uses SESAMI 2.9.',
    pending: 'Upload a file and start the run. Metrics, plots, and selected points will appear here.',
    emptyTitle: 'Waiting for results',
    emptyBody: 'This page is already wired to real job polling and will update automatically after submission.',
    regionTitle: 'BET linear-region points',
    plotsTitle: 'Generated figures',
    comparisonTitle: 'Comparison results',
    metrics: {
      area: 'Surface area',
      qm: 'qm',
      c: 'C constant',
      r2: 'Linear R²',
      region: 'Linear region',
      betMl: 'ML predicted area',
    },
    advanced: {
      r2Cutoff: 'R² cutoff',
      r2Min: 'R² min',
      dpi: 'Figure DPI',
      fontSize: 'Font size',
      legend: 'Show legend',
    },
    versionFixed: 'This mode always uses SESAMI 2.9',
  },
};

function formatNumber(value: number | null | undefined, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'N/A';
  }
  return value.toFixed(digits);
}

function ResultMetricCards({ locale, result }: { locale: Locale; result: SesamiResult }) {
  const t = copy[locale];
  const regionLabel = locale === 'zh' ? '线性区间' : 'Linear region';
  const pointsLabel = locale === 'zh' ? '点数' : 'Points';
  const pointCount = result.selectedPoints?.length || result.linearRegion?.count || null;
  const regionValue = result.linearRegion
    ? `${Math.round(result.linearRegion.lowPressurePa)}-${Math.round(result.linearRegion.highPressurePa)} Pa`
    : 'N/A';
  const metrics = [
    { label: t.metrics.area, value: `${formatNumber(result.area ?? result.betMl?.area, 3)} m²/g` },
    { label: t.metrics.qm, value: `${formatNumber(result.qm, 4)} mol/kg` },
    { label: t.metrics.c, value: formatNumber(result.C, 4) },
    { label: t.metrics.r2, value: formatNumber(result.r2, 6) },
    { label: regionLabel, value: regionValue },
    { label: pointsLabel, value: pointCount === null ? 'N/A' : String(pointCount) },
  ];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="md">
      {metrics.map((metric) => (
        <Paper key={metric.label} radius={22} className="cluster-card">
          <div className="cluster-title">{metric.label}</div>
          <div className="summary-title">{metric.value}</div>
        </Paper>
      ))}
    </SimpleGrid>
  );
}

function RegionTable({ locale, points }: { locale: Locale; points: SesamiPoint[] }) {
  const t = copy[locale];
  if (!points.length) {
    return null;
  }
  return (
    <Paper radius={24} className="region-summary-card glass-card">
      <div className="summary-title">{t.regionTitle}</div>
      <div className="region-table-wrap">
        <table className="region-table">
          <thead>
            <tr>
              <th>P/P0</th>
              <th>Pressure (Pa)</th>
              <th>Loading (mol/kg)</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point, index) => (
              <tr key={`${point.Pressure ?? index}-${index}`}>
                <td>{point.P_rel ?? 'N/A'}</td>
                <td>{point.Pressure ?? 'N/A'}</td>
                <td>{point.Loading ?? 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Paper>
  );
}

function PlotGallery({ locale, result, onOpen }: { locale: Locale; result: SesamiResult; onOpen: (plot: { name: string; url: string }) => void }) {
  const t = copy[locale];
  if (!result.plots?.length) {
    return null;
  }
  return (
    <Stack gap="sm">
      <Text className="summary-title">{t.plotsTitle}</Text>
      <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="md">
        {result.plots.map((plot) => (
          <button key={plot.url} type="button" className="plot-card-button" onClick={() => onOpen(plot)}>
            <div className="plot-card-title">{plot.name}</div>
            <img src={plot.url} alt={plot.name} className="result-image clickable-image" />
          </button>
        ))}
      </SimpleGrid>
    </Stack>
  );
}

function ComparisonCards({ locale, result }: { locale: Locale; result: SesamiResult }) {
  const t = copy[locale];
  if (!result.comparison?.length) {
    return null;
  }
  return (
    <Stack gap="sm">
      <Text className="summary-title">{t.comparisonTitle}</Text>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        {result.comparison.map((entry) => (
          <Paper key={entry.label} radius={22} className="cluster-card">
            <div className="cluster-title">{entry.engine ?? 'SESAMI'}</div>
            <div className="summary-title">{entry.label}</div>
            <div className="cluster-item">
              {entry.metrics?.area !== undefined ? `${formatNumber(entry.metrics.area, 3)} m²/g` : 'N/A'}
            </div>
            <div className="cluster-item">
              {entry.metrics?.r2 !== undefined ? `R² ${formatNumber(entry.metrics.r2, 6)}` : 'R² N/A'}
            </div>
            {entry.warning ? <Text className="notice-text">{entry.warning}</Text> : null}
          </Paper>
        ))}
      </SimpleGrid>
    </Stack>
  );
}

function EmptyState({ locale }: { locale: Locale }) {
  const t = copy[locale];
  return (
    <Paper radius={24} className="result-preview">
      <div className="result-preview-label">Pending Result</div>
      <div className="result-preview-title">{t.emptyTitle}</div>
      <div className="result-preview-text">{t.emptyBody}</div>
    </Paper>
  );
}

function SubmitButton({ loading, progress, label }: { loading: boolean; progress: number; label: string }) {
  return (
    <Button
      fullWidth
      radius="xl"
      size="md"
      className="primary-button progress-button"
      loading={loading}
      style={{ ['--progress-width' as string]: `${progress}%` }}
      type="submit"
    >
      {loading ? `${label} · ${progress}%` : label}
    </Button>
  );
}

export function SesamiWorkbench({ locale }: Props) {
  const t = copy[locale];
  const [subtab, setSubtab] = useState<SesamiSubtab>('bet');
  const [file, setFile] = useState<File | null>(null);
  const [gas, setGas] = useState('Argon');
  const [version, setVersion] = useState<SesamiVersion>('2.9');
  const [advancedMode, setAdvancedMode] = useState<'bet' | 'betEsw'>('bet');
  const [advancedSettings, setAdvancedSettings] = useState({
    r2Cutoff: 0.9995,
    r2Min: 0.998,
    dpi: 150,
    fontSize: 12,
    legend: 'true',
  });
  const [job, setJob] = useState<JobSnapshot<SesamiResult> | null>(null);
  const [activePlot, setActivePlot] = useState<{ name: string; url: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const actualMode = useMemo(() => {
    if (subtab === 'advanced') {
      return advancedMode;
    }
    return subtab;
  }, [advancedMode, subtab]);

  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') {
      return undefined;
    }
    const timer = window.setInterval(async () => {
      try {
        const snapshot = await fetchJob<SesamiResult>(job.jobId);
        setJob(snapshot);
      } catch (nextError) {
        const message = nextError instanceof Error ? nextError.message : 'Failed to poll job status.';
        setError(message);
        setJob((current) =>
          current
            ? {
                ...current,
                status: 'failed',
                error: message,
              }
            : current,
        );
      }
    }, 900);

    return () => window.clearInterval(timer);
  }, [job]);

  const running = job?.status === 'queued' || job?.status === 'running';
  const currentResult = job?.result ?? null;

  const submit = async (mode: SesamiSubtab | 'bet' | 'betEsw') => {
    if (!file) {
      setError(t.noFile);
      return;
    }

    try {
      setError(null);
      setJob(null);
      const next = await submitSesamiJob({
        mode: mode as SesamiSubtab,
        file,
        gas,
        version: mode === 'betEsw' || mode === 'betMl' ? '2.9' : version,
        advanced:
          subtab === 'advanced'
            ? {
                r2Cutoff: advancedSettings.r2Cutoff,
                r2Min: advancedSettings.r2Min,
                dpi: advancedSettings.dpi,
                fontSize: advancedSettings.fontSize,
                legend: advancedSettings.legend,
              }
            : undefined,
      });
      setJob(next);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Request failed.');
    }
  };

  const formCard = (
    <Paper radius={28} className="feature-card glass-card">
      <Stack gap="lg">
        <div>
          <Text className="panel-title">{t.subtabs[subtab]}</Text>
          <Text className="panel-hint">{t.descriptions[subtab]}</Text>
        </div>

        <Stack gap="sm">
          <Text fw={700}>{t.upload}</Text>
          <FileButton onChange={setFile} accept=".csv,.aif">
            {(props) => (
              <Button {...props} radius="xl" size="md" variant="light" leftSection={<IconUpload size={16} />}>
                {t.upload}
              </Button>
            )}
          </FileButton>
          <Paper radius={20} className="mini-dropzone">
            <Text fw={700}>{file ? file.name : t.noFile}</Text>
            <Text size="sm" c="dimmed">
              {file ? `${(file.size / 1024).toFixed(1)} KB` : '.csv / .aif'}
            </Text>
          </Paper>
        </Stack>

        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          <Select
            label={t.gas}
            value={gas}
            onChange={(value) => setGas(value ?? 'Argon')}
            data={[
              { label: 'Argon (87 K)', value: 'Argon' },
              { label: 'Nitrogen (77 K)', value: 'Nitrogen' },
            ]}
            radius="xl"
          />
          {subtab === 'bet' || subtab === 'advanced' ? (
            <Select
              label={t.version}
              value={subtab === 'advanced' && advancedMode === 'betEsw' ? '2.9' : version}
              onChange={(value) => setVersion((value as SesamiVersion) ?? '2.9')}
              data={[
                { label: 'SESAMI 2.9', value: '2.9' },
                { label: 'SESAMI 1.0', value: '1.0' },
              ]}
              disabled={subtab === 'advanced' && advancedMode === 'betEsw'}
              radius="xl"
            />
          ) : (
            <Paper radius={20} className="cluster-card">
              <div className="cluster-title">{t.version}</div>
              <div className="summary-title">SESAMI 2.9</div>
              <div className="cluster-item">{t.versionFixed}</div>
            </Paper>
          )}
        </SimpleGrid>

        {subtab === 'advanced' ? (
          <Stack gap="md">
            <Select
              label={t.analysis}
              value={advancedMode}
              onChange={(value) => setAdvancedMode((value as 'bet' | 'betEsw') ?? 'bet')}
              data={[
                { label: 'BET', value: 'bet' },
                { label: 'BET+ESW', value: 'betEsw' },
              ]}
              radius="xl"
            />
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
              <NumberInput
                label={t.advanced.r2Cutoff}
                value={advancedSettings.r2Cutoff}
                onChange={(value) => setAdvancedSettings((current) => ({ ...current, r2Cutoff: Number(value) || 0.9995 }))}
                decimalScale={4}
                step={0.0001}
                radius="xl"
              />
              <NumberInput
                label={t.advanced.r2Min}
                value={advancedSettings.r2Min}
                onChange={(value) => setAdvancedSettings((current) => ({ ...current, r2Min: Number(value) || 0.998 }))}
                decimalScale={4}
                step={0.0001}
                radius="xl"
              />
              <NumberInput
                label={t.advanced.dpi}
                value={advancedSettings.dpi}
                onChange={(value) => setAdvancedSettings((current) => ({ ...current, dpi: Number(value) || 150 }))}
                radius="xl"
              />
              <NumberInput
                label={t.advanced.fontSize}
                value={advancedSettings.fontSize}
                onChange={(value) => setAdvancedSettings((current) => ({ ...current, fontSize: Number(value) || 12 }))}
                radius="xl"
              />
            </SimpleGrid>
            <SegmentedControl
              fullWidth
              radius="xl"
              value={advancedSettings.legend}
              onChange={(value) => setAdvancedSettings((current) => ({ ...current, legend: value }))}
              data={[
                { label: `${t.advanced.legend} On`, value: 'true' },
                { label: `${t.advanced.legend} Off`, value: 'false' },
              ]}
            />
            <Text size="sm" c="dimmed">
              {t.advHint}
            </Text>
          </Stack>
        ) : null}

        {subtab === 'compare' ? (
          <Text size="sm" c="dimmed">
            {t.compareHint}
          </Text>
        ) : null}
        {subtab === 'betMl' ? (
          <Text size="sm" c="dimmed">
            {t.betmlHint}
          </Text>
        ) : null}

        {job ? <Text className="progress-meta">{job.stage} · {job.progress}%</Text> : null}
        {error ? <Text className="error-text">{error}</Text> : null}
        {job?.warning ? <Text className="notice-text">{job.warning}</Text> : null}

        <SubmitButton
          loading={Boolean(running)}
          progress={job?.progress ?? 0}
          label={subtab === 'advanced' ? t.runAdvanced : t.run}
        />
      </Stack>
    </Paper>
  );

  return (
    <Stack gap="lg">
      <Tabs value={subtab} onChange={(value) => setSubtab((value as SesamiSubtab) ?? 'bet')}>
        <Tabs.List className="subtabs-list">
          <Tabs.Tab value="bet">BET</Tabs.Tab>
          <Tabs.Tab value="betEsw">BET+ESW</Tabs.Tab>
          <Tabs.Tab value="betMl">BET-ML</Tabs.Tab>
          <Tabs.Tab value="compare">Compare</Tabs.Tab>
          <Tabs.Tab value="advanced">Advanced</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="lg">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit(actualMode);
          }}
        >
          {formCard}
        </form>

        <Paper radius={28} className="feature-card glass-card">
          <Stack gap="lg">
            <div>
              <Text className="panel-title">SESAMI</Text>
              <Text className="panel-hint">{t.pending}</Text>
            </div>

            {currentResult ? (
              <Stack gap="lg">
                <Group gap="sm">
                  <Badge radius="xl" color="ocean" variant="light">
                    {currentResult.engine ?? 'SESAMI'}
                  </Badge>
                  <Badge radius="xl" color="green" variant="light">
                    {currentResult.mode ?? subtab}
                  </Badge>
                  {currentResult.version ? (
                    <Badge radius="xl" color="gray" variant="light">
                      v{currentResult.version}
                    </Badge>
                  ) : null}
                </Group>

                {currentResult.mode === 'betml' ? (
                  <Paper radius={24} className="result-preview">
                    <div className="result-preview-label">BET-ML</div>
                    <div className="result-preview-title">
                      {formatNumber(currentResult.betMl?.area ?? null, 3)} m²/g
                    </div>
                    <div className="result-preview-text">{t.metrics.betMl}</div>
                  </Paper>
                ) : null}

                {currentResult.mode !== 'betml' && (currentResult.area !== undefined || currentResult.linearRegion) ? <ResultMetricCards locale={locale} result={currentResult} /> : null}
                <ComparisonCards locale={locale} result={currentResult} />
                <PlotGallery locale={locale} result={currentResult} onOpen={setActivePlot} />
                <RegionTable locale={locale} points={currentResult.selectedPoints ?? []} />
              </Stack>
            ) : (
              <EmptyState locale={locale} />
            )}
          </Stack>
        </Paper>
      </SimpleGrid>

      <Modal
        opened={Boolean(activePlot)}
        onClose={() => setActivePlot(null)}
        size="calc(100vw - 96px)"
        title={activePlot?.name ?? 'Plot'}
        centered
      >
        {activePlot ? <img src={activePlot.url} alt={activePlot.name} className="lightbox-image" /> : null}
      </Modal>
    </Stack>
  );
}






