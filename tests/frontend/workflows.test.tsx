import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SesamiWorkbench } from '../../src/features/sesami/SesamiWorkbench';
import { ZeoppWorkbench } from '../../src/features/zeopp/ZeoppWorkbench';
import { submitSesamiJob, submitZeoppJob } from '../../src/lib/api';

function mount(engine: 'sesami' | 'zeopp') {
  return render(<MantineProvider>{engine === 'sesami'
    ? <SesamiWorkbench locale="en" />
    : <ZeoppWorkbench locale="en" zeoppReady />}</MantineProvider>);
}

function upload(container: HTMLElement, name: string) {
  fireEvent.change(container.querySelector('input[type="file"]')!, {
    target: { files: [new File(['input'], name)] },
  });
}

function reply(result: object, status = 'completed') {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    jobId: 'test', status, stage: status, progress: 100, result,
  }), { status: 202 })));
}

describe('workbench mode integration', () => {
  it.each([
    ['BET', 'bet'], ['BET+ESW', 'bet-esw'], ['BET-ML', 'betml'], ['Compare', 'compare'],
  ])('submits SESAMI %s and renders its result', async (tab, mode) => {
    reply({ mode, version: '2.9', area: 2430.91, betMl: { area: 2099.055 },
      comparison: mode === 'compare' ? [{ label: 'Legacy BET', metrics: { area: 2430.91 }, warning: 'Optional counterpart warning' }] : undefined });
    const user = userEvent.setup();
    const { container } = mount('sesami');
    await user.click(screen.getByRole('tab', { name: tab }));
    upload(container, 'sample.csv');
    fireEvent.submit(container.querySelector('form')!);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [endpoint, options] = vi.mocked(fetch).mock.calls[0];
    expect(endpoint).toBe(`./api/sesami/${mode}`);
    expect((options!.body as FormData).get('gas')).toBe('Argon');
    expect((options!.body as FormData).get('version')).toBe('2.9');
    await screen.findByText(mode, { selector: '.mantine-Badge-label' });
    if (mode === 'betml') expect(screen.getByText('2099.055 m²/g')).toBeTruthy();
    if (mode === 'compare') expect(screen.getByText('Optional counterpart warning')).toBeTruthy();
  });

  it('forces Compare to 2.9 after selecting legacy BET', async () => {
    reply({ mode: 'compare', version: '2.9' });
    const user = userEvent.setup();
    const { container } = mount('sesami');
    await user.click(screen.getByRole('textbox', { name: 'SESAMI version' }));
    await user.click(screen.getByRole('option', { name: 'SESAMI 1.0' }));
    await user.click(screen.getByRole('tab', { name: 'Compare' }));
    upload(container, 'sample.csv');
    fireEvent.submit(container.querySelector('form')!);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect((vi.mocked(fetch).mock.calls[0][1]!.body as FormData).get('version')).toBe('2.9');
  });

  it.each([
    ['PSD', 'psd'], ['RES / RESEX', 'res'], ['CHAN', 'chan'],
    ['SA', 'sa'], ['VOL', 'vol'], ['VOLPO', 'volpo'],
  ])('submits ZEO++ %s parameters and renders metrics with units', async (tab, mode) => {
    reply({ mode, rawOutput: 'engine output', metrics: [{ key: 'value', label: 'Verified metric', value: 12.5, unit: 'A^3' }] });
    const user = userEvent.setup();
    const { container } = mount('zeopp');
    await user.click(screen.getByRole('tab', { name: tab }));
    upload(container, 'sample.cif');
    fireEvent.submit(container.querySelector('form')!);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [endpoint, options] = vi.mocked(fetch).mock.calls[0];
    const form = options!.body as FormData;
    expect(endpoint).toBe(`./api/zeopp/${mode}`);
    if (mode === 'res') {
      expect(form.get('extended')).toBe('true');
      expect(form.has('probeRadius')).toBe(false);
    } else {
      expect(form.get('probeRadius')).toBe('1.86');
      expect(form.has('chanRadius')).toBe(mode !== 'chan');
      expect(form.has('numSamples')).toBe(mode !== 'chan');
    }
    await screen.findByText('Verified metric');
    expect(screen.getByText(/12.5/)).toBeTruthy();
    expect(screen.getByText('engine output')).toBeTruthy();
    expect(container.textContent).toContain('A^3');
  });

  it.each(['sesami', 'zeopp'] as const)('shows %s asynchronous worker failures', async (engine) => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ jobId: 'test', status: 'queued', stage: 'queued', progress: 0 }), { status: 202 }))
      .mockResolvedValue(new Response(JSON.stringify({ jobId: 'test', status: 'failed', stage: 'failed', progress: 100, error: 'Engine could not determine a result' }))));
    const { container } = mount(engine);
    upload(container, engine === 'sesami' ? 'sample.csv' : 'sample.cif');
    fireEvent.submit(container.querySelector('form')!);
    const alert = await screen.findByRole('alert', {}, { timeout: 3000 });
    expect(alert.textContent).toBe('Engine could not determine a result');
    expect(vi.mocked(fetch).mock.calls[1][0]).toBe('./api/jobs/test');
  });

  it('exports the completed result mode after switching tabs', async () => {
    reply({ mode: 'volpo', rawOutput: 'POAV_A^3: 12.5' });
    const user = userEvent.setup();
    const { container } = mount('zeopp');
    await user.click(screen.getByRole('tab', { name: 'VOLPO' }));
    upload(container, 'sample.cif');
    fireEvent.submit(container.querySelector('form')!);
    await screen.findByText('POAV_A^3: 12.5');
    await user.click(screen.getByRole('tab', { name: 'PSD' }));
    URL.createObjectURL = vi.fn(() => 'blob:test');
    URL.revokeObjectURL = vi.fn();
    let download = '';
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { download = this.download; });
    await user.click(screen.getByRole('button', { name: /TXT/i }));
    expect(download).toBe('chemex-volpo.txt');
  });
});

describe('request error handling', () => {
  it('preserves backend validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: 'Runtime unavailable' }), { status: 503 })));
    await expect(submitZeoppJob({ mode: 'sa', file: new File(['x'], 'x.cif') })).rejects.toThrow('Runtime unavailable');
  });
  it('forwards advanced BET+ESW controls', async () => {
    reply({});
    await submitSesamiJob({ mode: 'betEsw', file: new File(['x'], 'x.csv'), gas: 'Nitrogen', version: '2.9', advanced: { r2Cutoff: 0.995, legend: false } });
    const form = vi.mocked(fetch).mock.calls[0][1]!.body as FormData;
    expect(form.get('r2Cutoff')).toBe('0.995');
    expect(form.get('legend')).toBe('false');
    expect(form.get('gas')).toBe('Nitrogen');
  });
});
