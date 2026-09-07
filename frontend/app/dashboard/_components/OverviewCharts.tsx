"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  LabelList,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "../../components/ui/chart";
import { formatMoney } from "./ui";

function fmtDay(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function EmptyOverlay({ text }: { text: string }) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <span className="rounded-full bg-[rgba(255,255,255,0.05)] px-3 py-1 text-[11px] text-[var(--color-slate)]/70 ring-1 ring-[rgba(255,255,255,0.08)]">
        {text}
      </span>
    </div>
  );
}

/* ── 14-day call volume ─────────────────────────────────────────────── */

const volumeConfig = {
  count: { label: "Calls", color: "var(--color-signal)" },
} satisfies ChartConfig;

export function CallVolumeChart({
  data,
}: {
  data: { date: string; count: number }[];
}) {
  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <div>
      <div className="relative">
        <ChartContainer config={volumeConfig} className="aspect-auto h-[150px] w-full">
          <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.07)" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={fmtDay}
              tick={{ fontSize: 10 }}
            />
            <YAxis
              width={40}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              domain={[0, (max: number) => Math.max(4, max)]}
              tick={{ fontSize: 10 }}
            />
            <ChartTooltip
              cursor={{ fill: "rgba(255,255,255,0.05)" }}
              content={
                <ChartTooltipContent
                  labelFormatter={(v) => fmtDay(String(v))}
                  indicator="dot"
                />
              }
            />
            <Bar dataKey="count" fill="var(--color-count)" radius={[3, 3, 0, 0]} maxBarSize={22} />
          </BarChart>
        </ChartContainer>
        {total === 0 && <EmptyOverlay text="No calls in this range yet" />}
      </div>
      <p className="mt-2 text-[11px] text-[var(--color-slate)]/60">
        <span className="font-semibold tabular-nums text-[var(--color-ink)]">{total}</span> calls in
        the last 14 days
      </p>
    </div>
  );
}

/* ── Pipeline by stage ──────────────────────────────────────────────── */

const stageConfig = {
  count: { label: "Deals", color: "var(--color-signal)" },
} satisfies ChartConfig;

export function PipelineChart({
  stages,
}: {
  stages: { stage: string; count: number; total_amount: number }[];
}) {
  const rows = stages.map((s) => ({
    ...s,
    stageLabel: s.stage.charAt(0).toUpperCase() + s.stage.slice(1),
  }));
  const totalDeals = rows.reduce((s, r) => s + r.count, 0);

  return (
    <div className="relative">
      <ChartContainer
        config={stageConfig}
        className="aspect-auto w-full"
        style={{ height: rows.length * 34 + 8 }}
      >
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 0, right: 28, left: 0, bottom: 0 }}
        >
          <XAxis type="number" hide allowDecimals={false} domain={[0, (max: number) => Math.max(1, max)]} />
          <YAxis
            type="category"
            dataKey="stageLabel"
            width={92}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11.5 }}
          />
          <ChartTooltip
            cursor={{ fill: "rgba(255,255,255,0.05)" }}
            content={<ChartTooltipContent indicator="dot" hideLabel />}
          />
          <Bar dataKey="count" fill="var(--color-count)" radius={4} barSize={16}>
            <LabelList
              dataKey="count"
              position="right"
              offset={8}
              className="fill-[var(--color-slate)]"
              fontSize={11}
            />
          </Bar>
        </BarChart>
      </ChartContainer>
      {totalDeals === 0 && <EmptyOverlay text="No deals in the pipeline yet" />}
    </div>
  );
}

/* ── Pipeline value by stage (interactive donut) ──────────────────────
   Deliberately monochrome-blue rather than a rainbow palette — deals read
   as "more committed" the deeper the blue, then pop gold on Won, the one
   accent color this theme reserves for a genuine high point. */

const STAGE_FILLS: Record<string, string> = {
  new: "rgba(59, 111, 229, 0.32)",
  qualified: "rgba(59, 111, 229, 0.48)",
  demo: "rgba(59, 111, 229, 0.64)",
  proposal: "rgba(59, 111, 229, 0.8)",
  negotiation: "var(--color-signal)",
  won: "var(--color-gold)",
};

const valueConfig = {
  amount: { label: "Value" },
} satisfies ChartConfig;

export function PipelineValueChart({
  stages,
}: {
  stages: { stage: string; count: number; total_amount: number }[];
}) {
  const rows = stages
    .filter((s) => s.total_amount > 0)
    .map((s) => ({
      stage: s.stage,
      stageLabel: s.stage.charAt(0).toUpperCase() + s.stage.slice(1),
      amount: s.total_amount,
      fill: STAGE_FILLS[s.stage] || "var(--color-signal)",
    }));
  const total = rows.reduce((sum, r) => sum + r.amount, 0);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const active = activeIndex !== null ? rows[activeIndex] : null;

  if (total === 0) {
    return (
      <div className="relative flex h-[220px] items-center justify-center">
        <span className="rounded-full bg-[rgba(255,255,255,0.05)] px-3 py-1 text-[11px] text-[var(--color-slate)]/70 ring-1 ring-[rgba(255,255,255,0.08)]">
          No deal value in the pipeline yet
        </span>
      </div>
    );
  }

  return (
    <div>
      <ChartContainer config={valueConfig} className="mx-auto aspect-square h-[220px]">
        <PieChart>
          <ChartTooltip
            content={
              <ChartTooltipContent
                hideLabel
                formatter={(value, _name, item) => (
                  <div className="flex w-full items-center justify-between gap-3">
                    <span className="flex items-center gap-1.5 text-[var(--color-slate)]">
                      <span
                        className="h-2 w-2 shrink-0 rounded-[2px]"
                        style={{ backgroundColor: item.payload.fill }}
                      />
                      {item.payload.stageLabel}
                    </span>
                    <span className="font-mono font-medium tabular-nums text-[var(--color-ink)]">
                      {formatMoney(value as number, "USD")}
                    </span>
                  </div>
                )}
              />
            }
          />
          <Pie
            data={rows}
            dataKey="amount"
            nameKey="stageLabel"
            innerRadius={62}
            outerRadius={88}
            strokeWidth={2}
            stroke="var(--color-card)"
            onMouseEnter={(_, index) => setActiveIndex(index)}
            onMouseLeave={() => setActiveIndex(null)}
          >
            {rows.map((r, i) => (
              <Cell
                key={r.stage}
                fill={r.fill}
                opacity={activeIndex === null || activeIndex === i ? 1 : 0.35}
              />
            ))}
            <Label
              content={({ viewBox }) => {
                if (!viewBox || !("cx" in viewBox)) return null;
                const label = active ? active.stageLabel : "Pipeline";
                const value = active ? active.amount : total;
                return (
                  <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                    <tspan
                      x={viewBox.cx}
                      y={(viewBox.cy || 0) - 6}
                      className="fill-[var(--color-ink)] text-[16px] font-semibold tabular-nums"
                    >
                      {formatMoney(value, "USD")}
                    </tspan>
                    <tspan
                      x={viewBox.cx}
                      y={(viewBox.cy || 0) + 14}
                      className="fill-[var(--color-slate)] text-[10.5px]"
                    >
                      {label}
                    </tspan>
                  </text>
                );
              }}
            />
          </Pie>
        </PieChart>
      </ChartContainer>
      <div className="mt-1 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5">
        {rows.map((r, i) => (
          <button
            key={r.stage}
            type="button"
            onMouseEnter={() => setActiveIndex(i)}
            onMouseLeave={() => setActiveIndex(null)}
            className="flex items-center gap-1.5 text-[11px] text-[var(--color-slate)] transition-opacity"
            style={{ opacity: activeIndex === null || activeIndex === i ? 1 : 0.45 }}
          >
            <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ backgroundColor: r.fill }} />
            {r.stageLabel}
          </button>
        ))}
      </div>
    </div>
  );
}
