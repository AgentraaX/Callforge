"use client";

import { motion, useReducedMotion } from "motion/react";
import { PERSONAS, type Persona } from "../../lib/site-metrics";

function AgentCard({ agent, index }: { agent: Persona; index: number }) {
  const shouldReduce = useReducedMotion();
  const [from, to] = agent.gradient;

  return (
    <motion.div
      className="agent-card group relative h-full"
      initial={shouldReduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.45, delay: index * 0.08, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="relative flex h-full flex-col items-center rounded-2xl bg-card p-6 text-center shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] transition-transform duration-300 ease-out hover:-translate-y-1">
        {/* hover glow */}
        <div
          className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
          style={{ boxShadow: `inset 0 0 0 1.5px ${agent.color}55, 0 12px 32px ${agent.color}14` }}
        />

        {/* avatar */}
        <div className="relative mb-5 mt-1">
          <div
            className="agent-ring-outer absolute inset-[-10px] rounded-full"
            style={{
              border: `1.5px dashed ${agent.color}30`,
              animation: shouldReduce ? "none" : "ring-spin 20s linear infinite",
            }}
          />
          <div
            className="agent-ring-outer absolute inset-[-20px] rounded-full"
            style={{
              border: `1px dotted ${agent.color}20`,
              animation: shouldReduce ? "none" : "ring-spin-reverse 15s linear infinite",
            }}
          />
          <div
            className="relative z-10 flex h-16 w-16 select-none items-center justify-center rounded-full text-[28px] font-bold text-white"
            style={{ background: `linear-gradient(135deg, ${from}, ${to})` }}
          >
            {agent.name[0]}
            <span
              className="status-dot absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full border-2 border-white"
              style={{ backgroundColor: "#22C55E" }}
            />
          </div>
        </div>

        <h3 className="text-[16px] font-semibold text-ink">{agent.name}</h3>
        <p
          className="mt-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.14em]"
          style={{ color: agent.color }}
        >
          {agent.role}
        </p>

        <div
          className="my-3 h-0.5 w-8 rounded-full opacity-50"
          style={{ backgroundColor: agent.color }}
        />

        {/* description fills the flexible space so pills bottom-align across cards */}
        <p className="flex-1 text-[13px] leading-[1.5] text-slate">{agent.desc}</p>

        <div className="mt-4 flex flex-wrap justify-center gap-1.5">
          {agent.specialties.map((s) => (
            <span
              key={s}
              className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: agent.color, backgroundColor: `${agent.color}12` }}
            >
              {s}
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

export default function AgentCards() {
  return (
    <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {PERSONAS.map((agent, i) => (
        <AgentCard key={agent.name} agent={agent} index={i} />
      ))}
    </div>
  );
}
