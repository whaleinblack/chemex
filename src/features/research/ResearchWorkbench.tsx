import { useEffect, useState } from 'react';
import { Accordion, Alert, Anchor, Badge, Button, Checkbox, FileInput, Group, Image, Paper, Progress, SimpleGrid, Stack, Table, Text, Textarea, TextInput, Title } from '@mantine/core';
import { IconSearch, IconFlask, IconDownload, IconPlus, IconTrash } from '@tabler/icons-react';
import { downloadTextArtifact, fetchJob } from '../../lib/api';
import type { JobSnapshot, Locale } from '../../lib/types';
import './research.css';

type Source = { url: string; title: string };
type Monomer = { input?: string; name: string; cas: string | null; aliases: string[]; backbone: string; confidence?: string; notes?: string; sourceUrls?: string[]; aliasText?: string };
type Identity = { monomers: Monomer[]; warnings: string[]; sources: Source[]; mode: string };
type Evidence = { value: string | null; sourceUrls: string[]; evidence: string | null };
type PaperResult = { title: string; doi: string | null; url: string; year: number | null; journal: string; match: 'exact' | 'backbone' | 'candidate'; matchReason: string; access: string; fields: Record<string, Evidence> };
type Report = { papers: PaperResult[]; summary: string; conclusion: string; queries: string[]; sources: Source[]; limitations: string[]; searchedAt: string; monomers: Monomer[]; mode: string };
type Status = { available: boolean; enhanced: boolean; vision: boolean; mode: string };
type InputRow = { text: string; file: File | null };

const labels: Record<string, [string, string]> = {
  monomerCombination: ['单体组合证据', 'Monomer combination evidence'], linkage: ['连接键类型', 'Linkage'],
  solvents: ['溶剂与配比', 'Solvents and ratios'], temperature: ['温度', 'Temperature'], duration: ['反应时间', 'Reaction time'],
  modulator: ['Modulator / 催化剂与用量', 'Modulator / catalyst and amount'], stoichiometry: ['单体配比', 'Monomer stoichiometry'],
  singleCrystal: ['是否单晶', 'Single crystal'], scxrd: ['SCXRD 结构解析', 'SCXRD structure solution'],
  pxrdModel: ['PXRD 模拟与结构模型', 'PXRD simulation and structural model'], pawley: ['Pawley 拟合', 'Pawley fitting'],
  rietveld: ['Rietveld 精修', 'Rietveld refinement'], applications: ['文章中的应用', 'Applications'],
};

const safeUrl = (url: string) => /^https?:\/\//i.test(url) ? url : undefined;

async function readResponse(response: Response) {
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body;
}

function StructurePreview({ file }: { file: File | null }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    if (!file) { setUrl(''); return; }
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return url ? <Image src={url} h={140} fit="contain" alt="Monomer structure" className="research-image" /> : null;
}

function reportMarkdown(report: Report, locale: Locale) {
  const isZh = locale === 'zh';
  const lines = ['# COF实验设计 / COF Experiment Design', '', `检索时间 / Searched at: ${report.searchedAt}`, '', report.summary,
    '', '## 单体 / Monomers', ...report.monomers.map(m => `- ${m.name} | CAS: ${m.cas || '—'} | ${m.backbone}`),
    '', '## 检索范围 / Search scope', ...report.queries.map(q => `- ${q}`), '', '## 局限 / Limitations', ...report.limitations.map(l => `- ${l}`)];
  for (const p of report.papers) {
    lines.push('', `## ${p.title}`, `${p.journal} · ${p.year || '—'} · DOI: ${p.doi || '—'}`, p.url, `Match: ${p.match}`, p.matchReason, `Access: ${p.access}`);
    for (const [key, names] of Object.entries(labels)) {
      const e = p.fields[key];
      lines.push('', `### ${names[isZh ? 0 : 1]}`, e?.value || (isZh ? '未报告 / 未核实' : 'Not reported / not verified'));
      if (e?.evidence) lines.push(e.evidence);
      lines.push(...(e?.sourceUrls || []));
    }
  }
  lines.push('', '## 来源 / Sources', ...report.sources.map(s => `- ${s.title}: ${s.url}`));
  return lines.join('\n');
}

export function ResearchWorkbench({ locale }: { locale: Locale }) {
  const zh = locale === 'zh';
  const t = (cn: string, en: string) => zh ? cn : en;
  const [status, setStatus] = useState<Status | null>(null);
  const [rows, setRows] = useState<InputRow[]>([{ text: '', file: null }, { text: '', file: null }]);
  const [monomers, setMonomers] = useState<Monomer[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [notes, setNotes] = useState('');
  const [job, setJob] = useState<JobSnapshot<Identity | Report> | null>(null);
  const [action, setAction] = useState<'identify' | 'search'>('identify');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState<Report | null>(null);
  const [identityWarnings, setIdentityWarnings] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    fetch('./api/research/status').then(readResponse).then(value => { if (active) setStatus(value); })
      .catch(() => { if (active) setStatus(null); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!job || !busy) return;
    const id = job.jobId;
    let active = true;
    let timer: number;
    let failures = 0;
    const poll = async () => {
      try {
        const next = await fetchJob<Identity | Report>(id);
        if (!active) return;
        failures = 0;
        setJob(next);
        if (next.status === 'completed' && next.result) {
          if (action === 'identify') {
            const identity = next.result as Identity;
            setMonomers(identity.monomers);
            setIdentityWarnings(identity.warnings || []);
            setConfirmed(false);
          } else setReport(next.result as Report);
          setBusy(false);
          return;
        }
        if (next.status === 'failed') {
          setError(next.error || 'Research failed'); setBusy(false); return;
        }
      } catch (e) {
        if (!active) return;
        failures += 1;
        if (failures >= 3) {
          setError(t('无法读取任务状态；此次检索没有可用结论，请重试。', 'Cannot read job status; no conclusion is available. Please retry.'));
          setBusy(false); return;
        }
      }
      if (active) timer = window.setTimeout(poll, 2000);
    };
    poll();
    return () => { active = false; window.clearTimeout(timer); };
    // Poll one job; individual snapshots must not restart the polling loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.jobId, busy, action]);

  function updateRow(index: number, patch: Partial<InputRow>) {
    setRows(current => current.map((r, i) => i === index ? { ...r, ...patch } : r));
    setMonomers([]); setConfirmed(false); setReport(null); setError('');
  }

  function updateMonomer(index: number, patch: Partial<Monomer>) {
    setMonomers(current => current.map((m, i) => i === index ? { ...m, ...patch } : m));
    setConfirmed(false); setReport(null);
  }

  async function start(nextAction: 'identify' | 'search') {
    setError(''); setBusy(true); setJob(null); setAction(nextAction); setReport(null);
    try {
      let response: Response;
      if (nextAction === 'identify') {
        const form = new FormData();
        form.append('monomers', JSON.stringify(rows.map(r => ({ text: r.text }))));
        rows.forEach((r, i) => { if (r.file) form.append(`image${i}`, r.file); });
        response = await fetch('./api/research/identify', { method: 'POST', body: form });
      } else {
        response = await fetch('./api/research/search', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ monomers, confirmed, notes, locale }) });
      }
      setJob(await readResponse(response));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setBusy(false);
    }
  }

  const readyToIdentify = rows.every(r => r.text.trim() || r.file) && (!rows.some(r => r.file) || status?.vision);
  const readyToSearch = monomers.length >= 2 && monomers.every(m => m.name.trim()) && confirmed;
  const stages: Record<string, string> = { identifying: t('查询并识别单体', 'Resolving monomers'), searching: t('搜索文献与主体组合', 'Searching papers and backbone combinations'),
    extracting: t('整理条件与结构解析证据', 'Extracting evidence'), finalizing: t('核对报告与来源', 'Checking the report'), queued: t('等待检索', 'Queued'), completed: t('完成', 'Completed') };

  return <Stack gap="lg" className="research-workbench">
    <Group justify="space-between" align="flex-start">
      <div><Title order={2}>{t('COF实验设计', 'COF Experiment Design')}</Title>
        <Text c="dimmed" mt="xs">{t('从单体组合出发，寻找已有报道与可追溯的实验依据。不限于亚胺键。', 'Start from a monomer combination and find reported COFs and traceable experimental evidence, across linkage types.')}</Text></div>
      <Badge size="lg" variant="light">{status?.enhanced ? t('联网深度检索', 'Web research') : t('基础文献检索', 'Metadata research')}</Badge>
    </Group>
    {!status && <Alert color="red">{t('检索后端尚未连接，暂时无法提交任务。', 'Research backend is unavailable; tasks cannot be submitted.')}</Alert>}
    {status && !status.enhanced && <Alert color="blue" title={t('基础检索可用', 'Metadata search available')}>
      {t('名称和 CAS 可查询 PubChem 与 Crossref。当前返回待核对文献候选；图片自动识别、主体骨架自动匹配及全文条件提取尚未配置。可手动补充名称、简称和骨架扩展检索。', 'Names and CAS can query PubChem and Crossref. Results are unverified literature candidates. Image recognition, automatic backbone matching, and full-text extraction are not configured; add names, aliases and backbones manually.')}
    </Alert>}
    <Paper className="research-card" radius="xl" p="lg">
      <Group justify="space-between" mb="md"><Title order={3}>{t('1 · 输入单体组合', '1 · Enter monomers')}</Title>
        <Button variant="light" leftSection={<IconPlus size={16} />} disabled={busy || rows.length >= 4} onClick={() => { setRows([...rows, { text: '', file: null }]); setMonomers([]); setReport(null); setConfirmed(false); }}>{t('添加单体', 'Add monomer')}</Button></Group>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {rows.map((row, index) => <Paper key={index} className="research-monomer" radius="lg" p="md">
          <Group justify="space-between"><Text fw={700}>{t('单体', 'Monomer')} {index + 1}</Text>
            {rows.length > 2 && <Button variant="subtle" color="red" size="compact-xs" disabled={busy} aria-label={t('删除单体', 'Remove monomer')} onClick={() => { setRows(rows.filter((_, i) => i !== index)); setMonomers([]); setReport(null); setConfirmed(false); }}><IconTrash size={16} /></Button>}</Group>
          <TextInput mt="sm" label={t('名称 / CAS number', 'Name / CAS number')} placeholder={t('例如 108-45-2 或完整化学名称', 'e.g. 108-45-2 or a full chemical name')} value={row.text} maxLength={500} disabled={busy} onChange={e => updateRow(index, { text: e.currentTarget.value })} />
          <FileInput mt="sm" label={t('结构图片（可选）', 'Structure image (optional)')} placeholder="PNG / JPEG / WebP · ≤ 5 MB" accept="image/png,image/jpeg,image/webp" clearable disabled={busy} value={row.file} onChange={file => {
            if (file && file.size > 5 * 1024 * 1024) { setError(t('每张图片不能超过 5 MB。', 'Each image must be under 5 MB.')); return; }
            updateRow(index, { file });
          }} />
          <StructurePreview file={row.file} />
          {row.file && !status?.vision && <Text size="sm" c="orange" mt="xs">{t('尚未开启图片识别。请移除图片并输入名称或 CAS；图片不能代替已确认的单体身份。', 'Image recognition is not enabled. Remove the image and enter a name or CAS; an image cannot replace a confirmed identity.')}</Text>}
        </Paper>)}
      </SimpleGrid>
      <Group mt="md"><Button leftSection={<IconSearch size={16} />} disabled={!status || busy || !readyToIdentify} onClick={() => start('identify')}>{t('识别并核对单体', 'Identify monomers')}</Button>
        <Text size="sm" c="dimmed">{t('先确认位置异构体和官能团，再搜索组合。', 'Confirm positional isomers and functional groups before searching.')}</Text></Group>
    </Paper>
    {monomers.length > 0 && <Paper className="research-card" radius="xl" p="lg">
      <Title order={3} mb="md">{t('2 · 确认单体身份', '2 · Confirm identities')}</Title>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>{monomers.map((m, i) => <Stack key={i} gap="sm">
        <Text fw={700}>{t('单体', 'Monomer')} {i + 1}</Text>
        <TextInput label={t('完整名称', 'Full name')} value={m.name} disabled={busy} maxLength={500} onChange={e => updateMonomer(i, { name: e.currentTarget.value })} />
        <TextInput label="CAS" value={m.cas || ''} disabled={busy} maxLength={500} onChange={e => updateMonomer(i, { cas: e.currentTarget.value })} />
        <TextInput label={t('别名 / 简称（用分号分隔）', 'Aliases / abbreviations (semicolon separated)')} value={m.aliasText ?? m.aliases.join('; ')} disabled={busy} onChange={e => updateMonomer(i, { aliasText: e.currentTarget.value, aliases: e.currentTarget.value.split(';').map(a => a.trim()).filter(Boolean) })} />
        <TextInput label={t('主体骨架（可编辑）', 'Core backbone (editable)')} placeholder={t('如 pyrene、triphenylbenzene，注明取代位置', 'e.g. pyrene, triphenylbenzene; include substitution positions')} value={m.backbone} maxLength={500} disabled={busy} onChange={e => updateMonomer(i, { backbone: e.currentTarget.value })} />
        {m.notes && <Text size="sm" c="dimmed">{m.notes}</Text>}
        {m.sourceUrls?.map(url => <Anchor key={url} href={safeUrl(url)} target="_blank" rel="noopener noreferrer" size="sm">{t('核对单体来源', 'Check identity source')}</Anchor>)}
      </Stack>)}</SimpleGrid>
      {identityWarnings.map(w => <Alert key={w} color="orange" mt="sm">{w}</Alert>)}
      <Checkbox mt="lg" label={t('我已核对各单体的结构、取代位置和名称，确认以上组合。', 'I have checked the structures, substitution positions and names, and confirm this combination.')} checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.currentTarget.checked)} />
      <Textarea mt="md" label={t('补充检索要求（可选）', 'Additional research context (optional)')} placeholder={t('例如重点关注单晶、指定连接键，或说明图片中的保护基', 'e.g. prioritize single crystals or a linkage; describe protecting groups')} value={notes} maxLength={2000} disabled={busy} onChange={e => { setNotes(e.currentTarget.value); setReport(null); }} />
      <Button mt="md" leftSection={<IconFlask size={16} />} disabled={!readyToSearch || busy || !status} onClick={() => start('search')}>{t('检索这个组合', 'Research this combination')}</Button>
    </Paper>}
    {busy && <Paper className="research-card" radius="xl" p="lg"><Text mb="sm">{stages[job?.stage || 'queued'] || job?.stage}</Text><Progress value={job?.progress || 0} animated aria-label={t('检索任务进度', 'Research progress')} /><Text size="sm" c="dimmed" mt="sm">{t('进度来自后端任务。检索范围或文献访问可能影响耗时。', 'Progress reflects the backend task. Search scope and access may affect duration.')}</Text></Paper>}
    {error && <Alert color="red" title={t('任务未完成', 'Task incomplete')}>{error}</Alert>}
    {report && <Stack gap="md">
      <Paper className="research-card" radius="xl" p="lg">
        <Group justify="space-between"><Title order={3}>{report.conclusion === 'reported' ? t('找到相同组合的报道', 'Reported combination found') : report.conclusion === 'inconclusive' ? t('组合是否已有报道，尚未核实', 'Whether this combination is reported remains unverified') : t('暂未检索到相同组合的可靠报道', 'No verified exact report found in this search')}</Title>
          <Group><Button variant="light" leftSection={<IconDownload size={16} />} onClick={() => downloadTextArtifact('cof-experiment-research.md', reportMarkdown(report, locale))}>Markdown</Button><Button variant="light" onClick={() => downloadTextArtifact('cof-experiment-research.json', JSON.stringify(report, null, 2))}>JSON</Button></Group></Group>
        <Text mt="md">{report.summary}</Text>
        <Text size="sm" c="dimmed" mt="sm">{t('检索时间', 'Searched at')}: {new Date(report.searchedAt).toLocaleString(locale === 'zh' ? 'zh-CN' : 'en-US')}</Text>
        <Alert color="orange" mt="md">{t('暂未检索到 ≠ 无人做过。相似骨架不等于相同单体组合；未报告的条件不能当作实验建议。', 'No results does not prove novelty. Similar backbones are not identical combinations. Missing conditions are not experimental recommendations.')}</Alert>
      </Paper>
      {report.papers.map((p, i) => <Paper key={p.doi || p.url} className="research-card" radius="xl" p="lg">
        <Group mb="sm"><Badge color={p.match === 'exact' ? 'teal' : 'blue'}>{p.match === 'exact' ? t('相同组合', 'Exact combination') : p.match === 'backbone' ? t('相似骨架', 'Related backbone') : t('待核对候选', 'Unverified candidate')}</Badge><Text size="sm" c="dimmed">{p.journal} · {p.year || '—'}</Text></Group>
        <Anchor fw={700} size="lg" href={safeUrl(p.url)} target="_blank" rel="noopener noreferrer">{i + 1}. {p.title}</Anchor>
        {p.doi && <Text size="sm" mt="xs">DOI: {p.doi}</Text>}
        <Text mt="sm">{p.matchReason}</Text><Text size="sm" c="dimmed" mt="xs">{t('已读取资料', 'Access level')}: {p.access}</Text>
        <Accordion mt="md" variant="contained" radius="md"><Accordion.Item value="details"><Accordion.Control>{t('合成条件、结构解析与应用', 'Synthesis, structure and applications')}</Accordion.Control><Accordion.Panel><Table className="research-evidence"><Table.Tbody>{Object.entries(labels).map(([key, names]) => {
          const e = p.fields[key];
          return <Table.Tr key={key}><Table.Th>{names[zh ? 0 : 1]}</Table.Th><Table.Td><Text size="sm">{e?.value || t('未报告 / 未核实', 'Not reported / not verified')}</Text>
            {e?.evidence && <Text size="xs" c="dimmed" mt="xs">{e.evidence}</Text>}
            <Group gap="xs" mt={e?.sourceUrls.length ? 'xs' : 0}>{e?.sourceUrls.map((url, k) => <Anchor key={url} size="xs" href={safeUrl(url)} target="_blank" rel="noopener noreferrer">{t('依据', 'Evidence')} {k + 1}</Anchor>)}</Group>
          </Table.Td></Table.Tr>;
        })}</Table.Tbody></Table></Accordion.Panel></Accordion.Item></Accordion>
      </Paper>)}
      <Accordion variant="separated" radius="lg"><Accordion.Item value="scope"><Accordion.Control>{t('检索词、来源与局限', 'Queries, sources and limitations')}</Accordion.Control><Accordion.Panel>
        <Stack gap="sm">{report.queries.map(q => <Text key={q} size="sm">{q}</Text>)}{report.limitations.map(l => <Text key={l} size="sm" c="dimmed">{l}</Text>)}{report.sources.map(s => <Anchor key={s.url} size="sm" href={safeUrl(s.url)} target="_blank" rel="noopener noreferrer">{s.title}</Anchor>)}</Stack>
      </Accordion.Panel></Accordion.Item></Accordion>
    </Stack>}
  </Stack>;
}
