"use client";

import { motion, useReducedMotion } from "motion/react";
import {
  Lightning,
  FileText,
  Brain,
  UserSwitch,
  type IconProps,
} from "@phosphor-icons/react";
import type { ComponentType } from "react";

interface Step {
  num: number;
  title: string;
  desc: string;
  color: string;
  badge: string;
  badgeType: "pulse" | "shimmer" | "shimmer" | "success";
  Icon: ComponentType<IconProps>;
}

const steps: Step[] = [
  {
    num: 1,
    title: "Trigger Detected",
    desc: "AI identifies escalation triggers: VIP account, complaint sentiment, regulatory query, or explicit human request",
    color: "#DC2626",
    badge: "High Priority",
    badgeType: "pulse",
    Icon: Lightning,
  },
  {
    num: 2,
    title: "Case Created",
    desc: "Automatic case creation with full transcript, lead data, and urgency classification",
    color: "#EAB308",
    badge: "Processing",
    badgeType: "shimmer",
    Icon: FileText,
  },
  {
    num: 3,
    title: "AI Summary",
    desc: "Concise summary for human agent: key issues, sentiment, recommended actions",
    color: "#3B82F6",
    badge: "Generating",
    badgeType: "shimmer",
    Icon: Brain,
  },
  {
    num: 4,
    title: "Human Handoff",
    desc: "Seamless transfer with zero hold time. Human joins with full context.",
    color: "var(--color-signal)",
    badge: "Complete",
    badgeType: "success",
    Icon: UserSwitch,
  },
];

function PulseRing({ color }: { color: string }) {
  return (
    <span
      className="absolute inset-0 rounded-full"
      style={{
        boxShadow: `0 0 0 0 ${color}50`,
        animation: `step-pulse-ring 2s ease-in-out infinite`,
      }}
    />
  );
}

function StepNode({ step, index }: { step: Step; index: number }) {
  const shouldReduce = useReducedMotion();
  const { Icon } = step;

  return (
    <motion.div
      className="relative flex flex-col lg:flex-row items-start gap-4 lg:gap-6"
      initial={shouldReduce ? { opacity: 1 } : { opacity: 0, x: -32 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{
        duration: 0.5,
        delay: index * 0.15,
        ease: [0.25, 0.1, 0.25, 1],
      }}
    >
      {/* Node circle + line */}
      <div className="relative flex flex-col items-center shrink-0">
        <div className="relative z-10">
          <motion.div
            className="relative w-14 h-14 rounded-full flex items-center justify-center"
            style={{ backgroundColor: step.color }}
            initial={shouldReduce ? {} : { scale: 0 }}
            whileInView={{ scale: 1 }}
            viewport={{ once: true }}
            transition={{
              type: "spring",
              stiffness: 200,
              damping: 15,
              delay: index * 0.15 + 0.1,
            }}
          >
            {step.num === 1 && <PulseRing color={step.color} />}
            <Icon size={24} weight="fill" color="#fff" />
          </motion.div>
        </div>

        {/* Vertical connector line (mobile) */}
        {index < steps.length - 1 && (
          <div className="w-0.5 h-16 lg:hidden relative overflow-hidden mt-2">
            <motion.div
              className="absolute top-0 left-0 w-full rounded-full"
              style={{ backgroundColor: step.color }}
              initial={shouldReduce ? { height: "100%" } : { height: 0 }}
              whileInView={{ height: "100%" }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: index * 0.15 + 0.3 }}
            />
          </div>
        )}
      </div>

      {/* Card */}
      <div
        className={`flex-1 card-ring p-5 relative overflow-hidden ${
          step.badgeType === "shimmer" ? "shimmer-bg" : ""
        }`}
        style={{
          borderLeft: `3px solid ${step.color}`,
        }}
      >
        {/* Badge */}
        <div className="flex items-center gap-2 mb-3">
          <span
            className={`text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full ${
              step.badgeType === "pulse" ? "badge-pulse-glow" : ""
            }`}
            style={{
              color: step.color,
              backgroundColor: `${step.color}14`,
              ...(step.badgeType === "pulse"
                ? { boxShadow: `0 0 8px ${step.color}30` }
                : {}),
            }}
          >
            {step.badge === "Complete" ? (
              <span className="flex items-center gap-1">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-signal)]" />
                {step.badge}
              </span>
            ) : (
              step.badge
            )}
          </span>
        </div>

        <h3 className="text-[15px] font-semibold text-[var(--color-ink)]">
          {step.title}
        </h3>
        <p className="mt-1.5 text-[13px] text-[var(--color-slate)] leading-[21px]">
          {step.desc}
        </p>

        {/* Success glow for last step */}
        {step.badgeType === "success" && (
          <div
            className="absolute -bottom-6 -right-6 w-24 h-24 rounded-full opacity-10 blur-xl pointer-events-none"
            style={{ backgroundColor: step.color }}
          />
        )}
      </div>
    </motion.div>
  );
}

export default function EscalationFlow() {
  const shouldReduce = useReducedMotion();

  return (
    <div className="mt-10 relative">
      {/* Horizontal connector line (desktop only) */}
      <div className="hidden lg:block absolute top-7 left-[7%] right-[7%] h-0.5 overflow-hidden rounded-full">
        <motion.div
          className="h-full rounded-full"
          style={{
            background: `linear-gradient(to right, #DC2626, #EAB308, #3B82F6, var(--color-signal))`,
          }}
          initial={shouldReduce ? { width: "100%" } : { width: 0 }}
          whileInView={{ width: "100%" }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 1.2, ease: "easeInOut" }}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 lg:gap-5">
        {steps.map((step, i) => (
          <StepNode key={step.num} step={step} index={i} />
        ))}
      </div>
    </div>
  );
}
