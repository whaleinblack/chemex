import type { Health, JobSnapshot, SesamiResult, SesamiSubtab, SesamiVersion, ZeoppResult, ZeoppStatus, ZeoppSubtab } from './types';

async function readJsonOrThrow(response: Response) {
  const text = await response.text();
  let payload: unknown = null;

  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  if (!response.ok) {
    const message =
      payload && typeof payload === 'object' && 'error' in payload && typeof payload.error === 'string'
        ? payload.error
        : `${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  return payload;
}

export async function fetchHealth() {
  return (await readJsonOrThrow(await fetch('./api/health'))) as Health;
}

export async function fetchZeoppStatus() {
  return (await readJsonOrThrow(await fetch('./api/zeopp/status'))) as ZeoppStatus;
}

export async function fetchJob<T>(jobId: string) {
  return (await readJsonOrThrow(await fetch(`./api/jobs/${jobId}`))) as JobSnapshot<T>;
}

export async function submitSesamiJob(options: {
  mode: SesamiSubtab;
  file: File;
  gas: string;
  version: SesamiVersion;
  advanced?: Record<string, string | number | boolean | null | undefined>;
}) {
  const form = new FormData();
  form.append('file', options.file);
  form.append('gas', options.gas);
  form.append('version', options.version);
  Object.entries(options.advanced ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      form.append(key, String(value));
    }
  });

  const endpoint =
    options.mode === 'bet'
      ? './api/sesami/bet'
      : options.mode === 'betEsw'
        ? './api/sesami/bet-esw'
        : options.mode === 'betMl'
          ? './api/sesami/betml'
          : options.mode === 'compare'
            ? './api/sesami/compare'
            : './api/sesami/bet';

  return (await readJsonOrThrow(
    await fetch(endpoint, {
      method: 'POST',
      body: form,
    }),
  )) as JobSnapshot<SesamiResult>;
}

export async function submitZeoppJob(options: {
  mode: ZeoppSubtab;
  file: File;
  params?: Record<string, string | number | boolean | null | undefined>;
}) {
  const form = new FormData();
  form.append('file', options.file);
  Object.entries(options.params ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      form.append(key, String(value));
    }
  });

  const endpointMap: Record<ZeoppSubtab, string> = {
    psd: './api/zeopp/psd',
    res: './api/zeopp/res',
    chan: './api/zeopp/chan',
    sa: './api/zeopp/sa',
    vol: './api/zeopp/vol',
    volpo: './api/zeopp/volpo',
  };

  return (await readJsonOrThrow(
    await fetch(endpointMap[options.mode], {
      method: 'POST',
      body: form,
    }),
  )) as JobSnapshot<ZeoppResult>;
}

export function downloadTextArtifact(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
