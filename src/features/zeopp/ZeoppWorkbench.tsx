import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  FileButton,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
} from '@mantine/core';
import { IconAtom2, IconChartHistogram, IconCopy, IconDownload, IconUpload } from '@tabler/icons-react';
import { downloadTextArtifact, fetchJob, submitZeoppJob } from '../../lib/api';
import type {
  JobSnapshot,
  Locale,
  ZeoppChannelSummary,
  ZeoppMetric,
  ZeoppResult,
  ZeoppSeriesRow,
  ZeoppSubtab,
} from '../../lib/types';

type Props = {
  locale: Locale;
  zeoppReady: boolean;
};

type ZeoppStrings = {
  subtabs: Record<ZeoppSubtab, string>;
  descriptions: Record<ZeoppSubtab, string>;
  upload: string;
  noFile: string;
  probeRadius: string;
  chanRadius: string;
  numSamples: string;
  run: string;
  pending: string;
  emptyTitle: string;
  emptyBody: string;
  rawOutput: string;
  series: string;
  count: string;
  derivative: string;
  extended: string;
  standard: string;
  copy: string;
  exportTxt: string;
  exportMd: string;
  tooltip: {
    x: string;
    y: string;
  };
};

const copy: Record<Locale, ZeoppStrings> = {
  zh: {
    subtabs: {
      psd: 'PSD',
      res: 'RES / RESEX',
      chan: 'CHAN',
      sa: 'SA',
      vol: 'VOL',
      volpo: 'VOLPO',
    },
    descriptions: {
      psd: 'Pore size distribution，返回孔径直方图与采样统计。',
      res: '最大内切球、最大自由球与扩展轴向自由球 / 内切球结果。',
      chan: '通道数、维度与每条通道的 Di / Df / Dif。',
      sa: 'Accessible / non-accessible surface area 与 channel / pocket contribution。',
      vol: 'Accessible / non-accessible volume 与 channel / pocket contribution。',
      volpo: 'Probe-occupiable volume 工作流，返回 POAV / PONAV 等体积指标。',
    },
    upload: '上传结构文件',
    noFile: '未选择结构文件',
    probeRadius: 'Probe radius (Å)',
    chanRadius: 'Channel radius (Å)',
    numSamples: '采样点数',
    run: '开始计算',
    pending: '提交后会显示真实任务进度、结构化结果与原始输出。',
    emptyTitle: '等待结果',
    emptyBody: '当前 subtab 已接入真实 ZEO++ 命令执行与 job 轮询。',
    rawOutput: '原始输出',
    series: '曲线',
    count: 'Count',
    derivative: 'Derivative',
    extended: 'Extended',
    standard: 'Standard',
    copy: '复制',
    exportTxt: '导出 TXT',
    exportMd: '导出 MD',
    tooltip: {
      x: '孔径',
      y: '数值',
    },
  },
  en: {
    subtabs: {
      psd: 'PSD',
      res: 'RES / RESEX',
      chan: 'CHAN',
      sa: 'SA',
      vol: 'VOL',
      volpo: 'VOLPO',
    },
    descriptions: {
      psd: 'Pore size distribution with histogram-style output and sampling statistics.',
      res: 'Largest included sphere, largest free sphere, and extended axis-wise free / included sphere outputs.',
      chan: 'Channel count, dimensionality, and Di / Df / Dif for each channel.',
      sa: 'Accessible / non-accessible surface area with channel / pocket contributions.',
      vol: 'Accessible / non-accessible volume with channel / pocket contributions.',
      volpo: 'Probe-occupiable volume workflow returning POAV / PONAV volume metrics.',
    },
    upload: 'Upload structure file',
    noFile: 'No structure file selected',
    probeRadius: 'Probe radius (A)',
    chanRadius: 'Channel radius (A)',
    numSamples: 'Number of samples',
    run: 'Run calculation',
    pending: 'Real job progress, structured outputs, and raw command output will appear after submission.',
    emptyTitle: 'Waiting for results',
    emptyBody: 'This subtab is already wired to real ZEO++ command execution and job polling.',
    rawOutput: 'Raw output',
    series: 'Series',
    count: 'Count',
    derivative: 'Derivative',
    extended: 'Extended',
    standard: 'Standard',
    copy: 'Copy',
    exportTxt: 'Export TXT',
    exportMd: 'Export MD',
    tooltip: {
      x: 'Diameter',
      y: 'Value',
    },
  },
};

function formatValue(metric: ZeoppMetric) {
  if (metric.value === null || metric.value === undefined) {
    return '—';
  }
  if (typeof metric.value === 'number') {
    return `${metric.value.toFixed(Math.abs(metric.value) >= 100 ? 2 : 4)}${metric.unit ? ` ${metric.unit}` : ''}`;
  }
  return `${metric.value}${metric.unit ? ` ${metric.unit}` : ''}`;
}

function niceMax(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return 1;
  }
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const nice = normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return nice * magnitude;
}

function meaningfulPsdRows(rows: ZeoppSeriesRow[]) {
  if (!rows.length) {
    return rows;
  }

  let lastMeaningfulIndex = -1;
  for (let index = 0; index < rows.length; index += 1) {
    const row = rows[index];
    const count = row.count ?? row.value ?? 0;
    const derivative = row.derivative ?? 0;
    const cumulative = row.cumulative ?? 0;
    if (Math.abs(count) > 1e-9 || Math.abs(derivative) > 1e-9 || (cumulative > 0 && cumulative < 1)) {
      lastMeaningfulIndex = index;
    }
  }

  if (lastMeaningfulIndex === -1) {
    return rows.slice(0, Math.min(rows.length, 2));
  }

  const paddedEnd = Math.min(rows.length, lastMeaningfulIndex + 3);
  return rows.slice(0, paddedEnd);
}

function PsdChart({ locale, rows }: { locale: Locale; rows: ZeoppSeriesRow[] }) {
  const t = copy[locale];
  const [series, setSeries] = useState<'count' | 'derivative'>('count');
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);

  const width = 760;
  const height = 360;
  const margin = { top: 24, right: 26, bottom: 52, left: 62 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const visibleRows = meaningfulPsdRows(rows);
  const values = visibleRows.map((row) => (series === 'count' ? row.count ?? row.value ?? 0 : row.derivative ?? row.value ?? 0));
  const rawXMax = Math.max(...visibleRows.map((row) => row.diameter), 1);
  const xMax = niceMax(rawXMax * 1.05);
  const yMax = niceMax(Math.max(...values, 1));

  const xScale = (value: number) => margin.left + (value / xMax) * plotWidth;
  const yScale = (value: number) => margin.top + plotHeight - (value / yMax) * plotHeight;

  const path = visibleRows
    .map((row, index) => `${index === 0 ? 'M' : 'L'} ${xScale(row.diameter).toFixed(2)} ${yScale(series === 'count' ? row.count ?? row.value ?? 0 : row.derivative ?? row.value ?? 0).toFixed(2)}`)
    .join(' ');

  const area = `${path} L ${xScale(visibleRows[visibleRows.length - 1]?.diameter ?? 0).toFixed(2)} ${yScale(0).toFixed(2)} L ${xScale(visibleRows[0]?.diameter ?? 0).toFixed(2)} ${yScale(0).toFixed(2)} Z`;
  const hovered = hoverIndex !== null ? visibleRows[hoverIndex] : null;

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="center">
        <Text className="summary-title">PSD</Text>
        <SegmentedControl
          radius="xl"
          value={series}
          onChange={(value) => setSeries((value as 'count' | 'derivative') ?? 'count')}
          data={[
            { label: t.count, value: 'count' },
            { label: t.derivative, value: 'derivative' },
          ]}
        />
      </Group>

      <div className="plot-shell" ref={shellRef}>
        <svg
          className="plot-svg"
          viewBox={`0 0 ${width} ${height}`}
          onMouseLeave={() => setHoverIndex(null)}
          onMouseMove={(event) => {
            if (!shellRef.current || !visibleRows.length) {
              return;
            }
            const rect = shellRef.current.getBoundingClientRect();
            const x = ((event.clientX - rect.left) / rect.width) * width;
            const domainX = ((x - margin.left) / plotWidth) * xMax;
            let nextIndex = 0;
            let minDistance = Number.POSITIVE_INFINITY;
            visibleRows.forEach((row, index) => {
              const distance = Math.abs(row.diameter - domainX);
              if (distance < minDistance) {
                minDistance = distance;
                nextIndex = index;
              }
            });
            setHoverIndex(nextIndex);
          }}
        >
          {Array.from({ length: 6 }).map((_, index) => {
            const yValue = (yMax / 5) * index;
            const y = yScale(yValue);
            return (
              <g key={`grid-y-${index}`}>
                <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} stroke="rgba(84, 122, 158, 0.12)" strokeDasharray="4 6" />
                <text x={margin.left - 12} y={y + 4} textAnchor="end" fontSize="12" fill="#597692">
                  {yValue.toFixed(0)}
                </text>
              </g>
            );
          })}
          {Array.from({ length: 6 }).map((_, index) => {
            const value = (xMax / 5) * index;
            const x = xScale(value);
            return (
              <g key={`grid-x-${index}`}>
                <line x1={x} x2={x} y1={margin.top} y2={height - margin.bottom} stroke="rgba(84, 122, 158, 0.10)" />
                <text x={x} y={height - margin.bottom + 24} textAnchor="middle" fontSize="12" fill="#597692">
                  {value.toFixed(0)}
                </text>
              </g>
            );
          })}
          <line x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} stroke="#4a769c" strokeWidth="1.5" />
          <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} stroke="#4a769c" strokeWidth="1.5" />
          <path d={area} fill="rgba(69, 135, 203, 0.12)" />
          <path d={path} fill="none" stroke="#2d79bf" strokeWidth="2.25" />
          {hovered ? (
            <g>
              <circle cx={xScale(hovered.diameter)} cy={yScale(series === 'count' ? hovered.count ?? hovered.value ?? 0 : hovered.derivative ?? hovered.value ?? 0)} r="5" fill="#2d79bf" />
            </g>
          ) : null}
          <text x={width / 2} y={height - 10} textAnchor="middle" fontSize="13" fill="#355f83">
            {locale === 'zh' ? '孔径 (Å)' : 'Pore diameter (A)'}
          </text>
          <text transform={`translate(18 ${height / 2}) rotate(-90)`} textAnchor="middle" fontSize="13" fill="#355f83">
            {series === 'count' ? t.count : t.derivative}
          </text>
        </svg>
        {hovered ? (
          <Paper radius={16} className="footer-note" style={{ marginTop: 10 }}>
            <Text size="sm">
              {t.tooltip.x}: {hovered.diameter.toFixed(2)} Å
            </Text>
            <Text size="sm">
              {t.tooltip.y}: {(series === 'count' ? hovered.count ?? hovered.value ?? 0 : hovered.derivative ?? hovered.value ?? 0).toFixed(4)}
            </Text>
          </Paper>
        ) : null}
      </div>
    </Stack>
  );
}

function MetricGrid({ metrics }: { metrics: ZeoppMetric[] }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
      {metrics.map((metric) => (
        <Paper key={metric.key} radius={22} className="cluster-card">
          <div className="cluster-title">{metric.label}</div>
          <div className="summary-title">{formatValue(metric)}</div>
        </Paper>
      ))}
    </SimpleGrid>
  );
}

function ChannelSummary({ channels }: { channels: ZeoppChannelSummary }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="md">
      {channels.largestIncludedSpheres.map((value, index) => (
        <Paper key={`${value}-${index}`} radius={22} className="cluster-card">
          <div className="cluster-title">Channel {index}</div>
          <div className="cluster-item">Dimensionality: {channels.dimensionalities[index] ?? '—'}</div>
          <div className="cluster-item">Di: {value.toFixed(4)} Å</div>
          <div className="cluster-item">Df: {(channels.largestFreeSpheres[index] ?? 0).toFixed(4)} Å</div>
          <div className="cluster-item">Dif: {(channels.largestIncludedFreeSpheres[index] ?? 0).toFixed(4)} Å</div>
        </Paper>
      ))}
    </SimpleGrid>
  );
}

function SubmitButton({ loading, progress, label, disabled }: { loading: boolean; progress: number; label: string; disabled?: boolean }) {
  return (
    <Button
      fullWidth
      radius="xl"
      size="md"
      className="primary-button progress-button"
      loading={loading}
      disabled={disabled}
      styles={{ root: { ['--progress-width' as string]: `${progress}%` } }}
      type="submit"
    >
      {loading ? `${label} · ${progress}%` : label}
    </Button>
  );
}

export function ZeoppWorkbench({ locale, zeoppReady }: Props) {
  const t = copy[locale];
  const [subtab, setSubtab] = useState<ZeoppSubtab>('psd');
  const [file, setFile] = useState<File | null>(null);
  const [chanRadius, setChanRadius] = useState(1.86);
  const [probeRadius, setProbeRadius] = useState(1.86);
  const [numSamples, setNumSamples] = useState(10000);
  const [resMode, setResMode] = useState<'standard' | 'extended'>('extended');
  const [job, setJob] = useState<JobSnapshot<ZeoppResult> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') {
      return undefined;
    }
    const timer = window.setInterval(async () => {
      try {
        const snapshot = await fetchJob<ZeoppResult>(job.jobId);
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
  const result = job?.result ?? null;

  const submit = async () => {
    if (!file) {
      setError(t.noFile);
      return;
    }
    try {
      setError(null);
      setJob(null);
      const params: Record<string, string | number | boolean> = {};
      if (subtab === 'res') {
        params.extended = resMode === 'extended';
      } else if (subtab === 'chan') {
        params.probeRadius = probeRadius;
      } else {
        params.chanRadius = chanRadius;
        params.probeRadius = probeRadius;
        params.numSamples = numSamples;
      }
      const next = await submitZeoppJob({
        mode: subtab,
        file,
        params,
      });
      setJob(next);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Request failed.');
    }
  };

  const rawOutput = result?.rawOutput ?? '';

  const rawMarkdown = useMemo(() => {
    const lines = [
      '# ChemEx ZEO++ Output',
      '',
      `- Mode: ${result?.mode ?? subtab}`,
      `- File: ${file?.name ?? 'N/A'}`,
      '',
      '```text',
      rawOutput,
      '```',
    ];
    return lines.join('\n');
  }, [file?.name, rawOutput, result?.mode, subtab]);

  return (
    <Stack gap="lg">
      {!zeoppReady ? (
        <Alert radius="xl" color="yellow" variant="light">
          ZEO++ runtime is not ready on this machine. The UI is available, but execution requires the compiled network binary.
        </Alert>
      ) : null}

      <Tabs value={subtab} onChange={(value) => setSubtab((value as ZeoppSubtab) ?? 'psd')}>
        <Tabs.List className="subtabs-list">
          <Tabs.Tab value="psd">PSD</Tabs.Tab>
          <Tabs.Tab value="res">RES / RESEX</Tabs.Tab>
          <Tabs.Tab value="chan">CHAN</Tabs.Tab>
          <Tabs.Tab value="sa">SA</Tabs.Tab>
          <Tabs.Tab value="vol">VOL</Tabs.Tab>
          <Tabs.Tab value="volpo">VOLPO</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="lg">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <Paper radius={28} className="feature-card glass-card">
            <Stack gap="lg">
              <div>
                <Text className="panel-title">{t.subtabs[subtab]}</Text>
                <Text className="panel-hint">{t.descriptions[subtab]}</Text>
              </div>

              <Stack gap="sm">
                <Text fw={700}>{t.upload}</Text>
                <FileButton onChange={setFile} accept=".cssr,.cif,.cuc,.v1,.res,.xyz,.pdb,.mol,.mol2,.txt">
                  {(props) => (
                    <Button {...props} radius="xl" size="md" variant="light" leftSection={<IconUpload size={16} />}>
                      {t.upload}
                    </Button>
                  )}
                </FileButton>
                <Paper radius={20} className="mini-dropzone">
                  <Text fw={700}>{file ? file.name : t.noFile}</Text>
                  <Text size="sm" c="dimmed">
                    {file ? `${(file.size / 1024).toFixed(1)} KB` : '.cssr / .cif / .cuc / .v1'}
                  </Text>
                </Paper>
              </Stack>

              {subtab === 'res' ? (
                <SegmentedControl
                  fullWidth
                  radius="xl"
                  value={resMode}
                  onChange={(value) => setResMode((value as 'standard' | 'extended') ?? 'extended')}
                  data={[
                    { label: t.standard, value: 'standard' },
                    { label: t.extended, value: 'extended' },
                  ]}
                />
              ) : null}

              {subtab === 'chan' ? (
                <NumberInput
                  label={t.probeRadius}
                  value={probeRadius}
                  onChange={(value) => setProbeRadius(Number(value) || 1.86)}
                  decimalScale={2}
                  radius="xl"
                />
              ) : null}

              {subtab !== 'res' && subtab !== 'chan' ? (
                <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                  <NumberInput
                    label={t.chanRadius}
                    value={chanRadius}
                    onChange={(value) => setChanRadius(Number(value) || 1.86)}
                    decimalScale={2}
                    radius="xl"
                  />
                  <NumberInput
                    label={t.probeRadius}
                    value={probeRadius}
                    onChange={(value) => setProbeRadius(Number(value) || 1.86)}
                    decimalScale={2}
                    radius="xl"
                  />
                  <NumberInput
                    label={t.numSamples}
                    value={numSamples}
                    onChange={(value) => setNumSamples(Number(value) || 10000)}
                    radius="xl"
                  />
                </SimpleGrid>
              ) : null}

              {job ? <Text className="progress-meta">{job.stage} · {job.progress}%</Text> : null}
              {error ? <Text className="error-text">{error}</Text> : null}
              {job?.warning ? <Text className="notice-text">{job.warning}</Text> : null}

              <SubmitButton loading={Boolean(running)} progress={job?.progress ?? 0} label={t.run} disabled={!zeoppReady} />
            </Stack>
          </Paper>
        </form>

        <Paper radius={28} className="feature-card glass-card">
          <Stack gap="lg">
            <div>
              <Text className="panel-title">ZEO++</Text>
              <Text className="panel-hint">{t.pending}</Text>
            </div>

            {result ? (
              <Stack gap="lg">
                <Group gap="sm">
                  <Badge radius="xl" color="ocean" variant="light">
                    {result.mode?.toUpperCase() ?? subtab.toUpperCase()}
                  </Badge>
                  {result.warning ? (
                    <Badge radius="xl" color="yellow" variant="light">
                      warning
                    </Badge>
                  ) : null}
                </Group>

                {result.rows?.length ? <PsdChart locale={locale} rows={result.rows} /> : null}
                {result.metrics?.length ? <MetricGrid metrics={result.metrics} /> : null}
                {result.channels ? <ChannelSummary channels={result.channels} /> : null}

                <Paper radius={24} className="code-panel">
                  <Stack gap="sm">
                    <Group justify="space-between" align="center">
                      <Text className="summary-title">{t.rawOutput}</Text>
                      <Group gap="xs" className="raw-output-actions">
                        <Button
                          radius="xl"
                          variant="light"
                          leftSection={<IconCopy size={16} />}
                          onClick={async () => {
                            if (rawOutput) {
                              await navigator.clipboard.writeText(rawOutput);
                            }
                          }}
                        >
                          {t.copy}
                        </Button>
                        <Button
                          radius="xl"
                          variant="light"
                          leftSection={<IconDownload size={16} />}
                          onClick={() => downloadTextArtifact(`chemex-${subtab}.txt`, rawOutput)}
                        >
                          {t.exportTxt}
                        </Button>
                        <Button
                          radius="xl"
                          variant="light"
                          leftSection={<IconDownload size={16} />}
                          onClick={() => downloadTextArtifact(`chemex-${subtab}.md`, rawMarkdown)}
                        >
                          {t.exportMd}
                        </Button>
                      </Group>
                    </Group>
                    <pre className="code-block">{rawOutput}</pre>
                  </Stack>
                </Paper>
              </Stack>
            ) : (
              <Paper radius={24} className="result-preview">
                <div className="result-preview-label">Pending Result</div>
                <div className="result-preview-title">{t.emptyTitle}</div>
                <div className="result-preview-text">{t.emptyBody}</div>
              </Paper>
            )}
          </Stack>
        </Paper>
      </SimpleGrid>
    </Stack>
  );
}
