import { Box, Text } from '@mantine/core';
import { useMemo, useState, type PointerEvent } from 'react';
import type { Locale, ZeoppSeriesRow } from '../../lib/types';

type Props = {
  locale: Locale;
  rows: ZeoppSeriesRow[];
};

type Point = {
  x: number;
  y: number;
  rawX: number;
  rawY: number;
};

function niceCeil(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return 1;
  }
  const exponent = Math.floor(Math.log10(value));
  const base = 10 ** exponent;
  const scaled = value / base;
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10;
  return step * base;
}

function buildTicks(maxValue: number, count = 6) {
  const safeMax = Math.max(maxValue, 1);
  const step = niceCeil(safeMax / (count - 1));
  const ticks: number[] = [];
  for (let value = 0; value <= safeMax + step; value += step) {
    ticks.push(Number(value.toFixed(6)));
  }
  if (ticks[ticks.length - 1] < safeMax) {
    ticks.push(niceCeil(safeMax));
  }
  return Array.from(new Set(ticks));
}

export function ZeoppPlot({ locale, rows }: Props) {
  const [hoverPoint, setHoverPoint] = useState<Point | null>(null);
  const [isHovering, setIsHovering] = useState(false);

  const width = 860;
  const height = 360;
  const margins = { top: 22, right: 24, bottom: 46, left: 60 };
  const innerWidth = width - margins.left - margins.right;
  const innerHeight = height - margins.top - margins.bottom;

  const data = useMemo(
    () =>
      rows
        .filter((row) => Number.isFinite(row.diameter) && Number.isFinite(row.value))
        .map((row) => ({
          x: Number(row.diameter),
          y: Number(row.value),
          rawX: Number(row.diameter),
          rawY: Number(row.value),
        }))
        .sort((a, b) => a.x - b.x),
    [rows],
  );

  const { xMax, yMax, points, xTicks, yTicks } = useMemo(() => {
    if (data.length === 0) {
      return {
        xMax: 1,
        yMax: 1,
        points: [] as Point[],
        xTicks: [0, 1],
        yTicks: [0, 1],
      };
    }

    const rawXMax = data[data.length - 1].x;
    const rawYMax = Math.max(...data.map((point) => point.y));
    const paddedXMax = niceCeil(Math.max(rawXMax + Math.max(rawXMax * 0.18, 2), rawXMax * 1.1));
    const paddedYMax = niceCeil(rawYMax + Math.max(rawYMax * 0.15, 1));
    const xTicks = buildTicks(paddedXMax);
    const yTicks = buildTicks(paddedYMax);
    const points = data.map((point) => ({
      ...point,
      x: margins.left + (point.x / paddedXMax) * innerWidth,
      y: margins.top + innerHeight - (point.y / paddedYMax) * innerHeight,
    }));
    return {
      xMax: paddedXMax,
      yMax: paddedYMax,
      points,
      xTicks,
      yTicks,
    };
  }, [data, innerHeight, innerWidth, margins.left, margins.top]);

  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');
  const areaPath = points.length
    ? `${linePath} L ${points[points.length - 1].x.toFixed(2)} ${(margins.top + innerHeight).toFixed(2)} L ${points[0].x.toFixed(2)} ${(margins.top + innerHeight).toFixed(2)} Z`
    : '';

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (points.length === 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const clampedX = Math.min(Math.max(x, margins.left), width - margins.right);
    const target = points.reduce(
      (best, point) => (Math.abs(point.x - clampedX) < Math.abs(best.x - clampedX) ? point : best),
      points[0],
    );
    setHoverPoint(target);
    setIsHovering(true);
  };

  if (data.length === 0) {
    return (
      <Box
        h={height}
        style={{
          display: 'grid',
          placeItems: 'center',
          borderRadius: 24,
          border: '1px solid rgba(220, 229, 238, 0.95)',
          background: 'linear-gradient(180deg, #ffffff, #f4f8fc)',
        }}
      >
        <Text c="dimmed">{locale === 'zh' ? '当前结果没有可绘制的数据。' : 'No plottable data has been returned yet.'}</Text>
      </Box>
    );
  }

  return (
    <Box
      style={{ position: 'relative' }}
      onPointerMove={handlePointerMove}
      onPointerEnter={() => setIsHovering(true)}
      onPointerLeave={() => {
        setIsHovering(false);
        setHoverPoint(null);
      }}
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="plot-svg">
        <defs>
          <linearGradient id="zeoppPlotFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4d96d8" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#4d96d8" stopOpacity="0.03" />
          </linearGradient>
        </defs>

        <line x1={margins.left} y1={margins.top + innerHeight} x2={width - margins.right} y2={margins.top + innerHeight} stroke="#adc2d6" />
        <line x1={margins.left} y1={margins.top} x2={margins.left} y2={margins.top + innerHeight} stroke="#adc2d6" />

        {xTicks.map((tick) => {
          const x = margins.left + (tick / xMax) * innerWidth;
          return (
            <g key={`x-${tick}`}>
              <line x1={x} y1={margins.top + innerHeight} x2={x} y2={margins.top + innerHeight + 6} stroke="#8ba6bf" />
              <text x={x} y={height - 14} textAnchor="middle" fontSize="11" fill="#55728b">
                {tick.toFixed(tick >= 10 ? 0 : 1)}
              </text>
            </g>
          );
        })}

        {yTicks.map((tick) => {
          const y = margins.top + innerHeight - (tick / yMax) * innerHeight;
          return (
            <g key={`y-${tick}`}>
              <line x1={margins.left - 6} y1={y} x2={margins.left} y2={y} stroke="#8ba6bf" />
              <text x={margins.left - 10} y={y + 4} textAnchor="end" fontSize="11" fill="#55728b">
                {tick.toFixed(tick >= 10 ? 0 : 1)}
              </text>
            </g>
          );
        })}

        {areaPath && <path d={areaPath} fill="url(#zeoppPlotFill)" />}
        {linePath && <path d={linePath} fill="none" stroke="#2f75b8" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />}

        {points.map((point, index) => (
          <circle key={`${point.rawX}-${index}`} cx={point.x} cy={point.y} r="4.5" fill="#ffffff" stroke="#2f75b8" strokeWidth="2" />
        ))}

        {hoverPoint && isHovering && (
          <>
            <line x1={hoverPoint.x} y1={margins.top} x2={hoverPoint.x} y2={margins.top + innerHeight} stroke="#2f75b8" strokeDasharray="5 4" opacity="0.55" />
            <circle cx={hoverPoint.x} cy={hoverPoint.y} r="6.5" fill="#2f75b8" opacity="0.16" />
            <circle cx={hoverPoint.x} cy={hoverPoint.y} r="5" fill="#ffffff" stroke="#2f75b8" strokeWidth="2.5" />
          </>
        )}

        <text x={width / 2} y={height - 4} textAnchor="middle" fontSize="12" fill="#4a769c" fontWeight="700">
          {locale === 'zh' ? '孔径 (Å)' : 'Pore diameter (Å)'}
        </text>
        <text
          x={18}
          y={height / 2}
          transform={`rotate(-90 18 ${height / 2})`}
          textAnchor="middle"
          fontSize="12"
          fill="#4a769c"
          fontWeight="700"
        >
          {locale === 'zh' ? '计数 / 归一化值' : 'Count / normalized value'}
        </text>
      </svg>

      {hoverPoint && isHovering && (
        <div
          style={{
            position: 'absolute',
            left: Math.min(Math.max(hoverPoint.x + 14, margins.left), width - 180),
            top: Math.max(margins.top + 6, hoverPoint.y - 48),
            pointerEvents: 'none',
            background: 'rgba(255,255,255,0.95)',
            border: '1px solid rgba(170, 191, 213, 0.85)',
            borderRadius: 16,
            padding: '10px 12px',
            boxShadow: '0 10px 26px rgba(33, 73, 109, 0.12)',
            minWidth: 150,
          }}
        >
          <Text size="xs" fw={800} c="blue">
            {locale === 'zh' ? '曲线坐标' : 'Curve coordinates'}
          </Text>
          <Text size="sm" fw={700}>
            {locale === 'zh'
              ? `孔径: ${hoverPoint.rawX.toFixed(2)} Å`
              : `Diameter: ${hoverPoint.rawX.toFixed(2)} Å`}
          </Text>
          <Text size="sm" fw={700}>
            {locale === 'zh' ? `数值: ${hoverPoint.rawY.toFixed(4)}` : `Value: ${hoverPoint.rawY.toFixed(4)}`}
          </Text>
        </div>
      )}
    </Box>
  );
}
