import { useEffect, useMemo, useState } from 'react';
import {
  ActionIcon,
  Badge,
  Group,
  Modal,
  Paper,
  SegmentedControl,
  Stack,
  Tabs,
  Text,
} from '@mantine/core';
import { IconAtom2, IconLanguage, IconSparkles } from '@tabler/icons-react';
import { fetchHealth } from './lib/api';
import { copy } from './lib/copy';
import type { Health, Locale, ToolKey } from './lib/types';
import { SesamiWorkbench } from './features/sesami/SesamiWorkbench';
import { ZeoppWorkbench } from './features/zeopp/ZeoppWorkbench';

function BrandWordmark() {
  return (
    <span className="hero-wordmark" aria-label="ChemEx">
      <span>C</span>
      <span>h</span>
      <span>e</span>
      <span className="hero-accent">m</span>
      <span>E</span>
      <span className="hero-accent">x</span>
    </span>
  );
}

type StatusPillProps = {
  label: string;
  value: string;
  hint: string;
  ok: boolean;
};

function StatusPill({ label, value, hint, ok }: StatusPillProps) {
  return (
    <div className={`status-pill${ok ? ' is-ok' : ''}`}>
      <span className="status-pill-dot" />
      <div className="status-pill-content">
        <div className="status-pill-label">{label}</div>
        <div className="status-pill-value">{value}</div>
        <div className="status-pill-hint">{hint}</div>
      </div>
    </div>
  );
}

export default function App() {
  const [locale, setLocale] = useState<Locale>('zh');
  const [tool, setTool] = useState<ToolKey>('sesami');
  const [health, setHealth] = useState<Health | null>(null);
  const [guideOpened, setGuideOpened] = useState(false);

  const t = copy[locale];

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const next = await fetchHealth();
        if (!cancelled) {
          setHealth(next);
        }
      } catch {
        if (!cancelled) {
          setHealth(null);
        }
      }
    };

    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const statusPills = useMemo(
    () => [
      {
        label: t.footer.status.api,
        value: health?.status === 'ok' ? t.footer.online : t.footer.offline,
        hint: health?.status === 'ok' ? t.footer.apiReady : t.footer.apiUnknown,
        ok: health?.status === 'ok',
      },
      {
        label: t.footer.status.sesami,
        value: health?.sesamiReady ? t.footer.ready : t.footer.unavailable,
        hint: health?.sesamiMessage ?? t.footer.pending,
        ok: Boolean(health?.sesamiReady),
      },
      {
        label: t.footer.status.zeopp,
        value: health?.zeoppReady ? t.footer.ready : t.footer.unavailable,
        hint: health?.zeoppMessage ?? t.footer.pending,
        ok: Boolean(health?.zeoppReady),
      },
    ],
    [health, t],
  );

  return (
    <div className="page-shell">
      <div className="ambient" />
      <Paper radius={32} className="app-frame">
        <Stack gap="xl">
          <Group align="flex-start" justify="space-between" className="topbar" wrap="wrap">
            <Stack gap="md" maw={860}>
              <Group gap="sm">
                <Badge radius="xl" size="lg" variant="light" color="ocean" className="ghost-badge">
                  {t.badges.toolbox}
                </Badge>
                <Badge radius="xl" size="lg" variant="white" className="ghost-badge">
                  {t.badges.release}
                </Badge>
              </Group>

              <div className="hero-brand-row">
                <img src="./chemex-logo.png" alt="ChemEx" className="hero-logo" />
                <div>
                  <h1 className="hero-title">
                    <BrandWordmark />
                  </h1>
                  <Group gap="xs" wrap="nowrap" align="center" className="hero-subtitle-row">
                    <Text className="hero-subtitle">{t.heroSubtitle}</Text>
                    <ActionIcon
                      variant="transparent"
                      radius="xl"
                      className="guide-help-button"
                      aria-label={t.guide.buttonLabel}
                      title={t.guide.buttonLabel}
                      onClick={() => setGuideOpened(true)}
                    >
                      <span className="guide-help-mark">?</span>
                    </ActionIcon>
                  </Group>
                </div>
              </div>

              <Text className="hero-text">{t.heroBody}</Text>
              <Text className="hero-footnote">{t.heroFootnote}</Text>
            </Stack>

            <Paper radius={30} className="language-switch">
              <Stack gap="md">
                <Group gap="xs">
                  <IconLanguage size={18} color="#4b8cc8" />
                  <Text fw={800}>{t.languageLabel}</Text>
                </Group>
                <SegmentedControl
                  fullWidth
                  radius="xl"
                  value={locale}
                  onChange={(value) => setLocale(value as Locale)}
                  data={[
                    { label: '中文', value: 'zh' },
                    { label: 'English', value: 'en' },
                  ]}
                />
              </Stack>
            </Paper>
          </Group>

          <div className="workspace-tabs">
            <Tabs value={tool} onChange={(value) => setTool((value as ToolKey) ?? 'sesami')}>
              <Tabs.List className="glass-tabs-list">
                <Tabs.Tab value="sesami" leftSection={<IconSparkles size={16} />}>
                  {t.tabs.sesami}
                </Tabs.Tab>
                <Tabs.Tab value="zeopp" leftSection={<IconAtom2 size={16} />}>
                  {t.tabs.zeopp}
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="sesami" pt="xl">
                <SesamiWorkbench locale={locale} />
              </Tabs.Panel>

              <Tabs.Panel value="zeopp" pt="xl">
                <ZeoppWorkbench locale={locale} zeoppReady={Boolean(health?.zeoppReady)} />
              </Tabs.Panel>
            </Tabs>
          </div>

          <Paper radius={26} className="footer-note">
            <div className="footer-status-bar">
              <div>
                <div className="footer-brand">{t.footer.brand}</div>
                <div className="footer-subcopy">{t.footer.description}</div>
              </div>
              <div className="status-pill-group">
                {statusPills.map((pill) => (
                  <StatusPill key={pill.label} {...pill} />
                ))}
              </div>
            </div>
          </Paper>
        </Stack>
      </Paper>

      <Modal
        opened={guideOpened}
        onClose={() => setGuideOpened(false)}
        centered
        radius={28}
        size="42rem"
        title={t.guide.title}
        classNames={{
          content: 'guide-modal-content',
          header: 'guide-modal-header',
          title: 'guide-modal-title',
          body: 'guide-modal-body',
        }}
      >
        <Stack gap="md">
          <Text className="guide-intro">{t.guide.intro}</Text>

          <Paper radius={24} className="guide-section-card">
            <div className="guide-section-title">{t.guide.implementedTitle}</div>
            <div className="guide-list">
              {t.guide.implementedItems.map((item) => (
                <div key={item} className="guide-list-item">
                  <span className="guide-list-bullet" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Paper>

          <Paper radius={24} className="guide-section-card">
            <div className="guide-section-title">{t.guide.usageTitle}</div>
            <div className="guide-list">
              {t.guide.usageItems.map((item) => (
                <div key={item} className="guide-list-item">
                  <span className="guide-list-bullet" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Paper>

          <Text className="guide-note">{t.guide.note}</Text>
        </Stack>
      </Modal>
    </div>
  );
}

