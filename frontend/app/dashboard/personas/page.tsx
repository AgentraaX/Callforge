"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  CircleNotch,
  MicrophoneStage,
  PencilSimple,
  PhoneCall,
  Plus,
  SpeakerHigh,
  Trash,
  UploadSimple,
  X,
} from "@phosphor-icons/react";
import {
  cloneVoice,
  createPersona,
  deletePersona,
  fetchPersonas,
  fetchVoices,
  previewPersonaVoice,
  updatePersona,
  type ElevenLabsVoice,
  type PersonaInput,
  type PersonaPayload,
} from "../../../lib/api";

const EMOTIONS = ["confident", "warm", "enthusiastic", "empathetic", "neutral", "urgent"];

const EMPTY_FORM: PersonaInput = {
  name: "",
  company: "",
  product_pitch: "",
  personality: "Warm, confident, and genuinely curious about the caller's situation.",
  knowledge_text: "",
  opening_line: "",
  call_goal: "book a short follow-up call",
  elevenlabs_voice_id: "",
  default_emotion: "confident",
  language_mode: "auto",
};

export default function PersonasPage() {
  const [personas, setPersonas] = useState<PersonaPayload[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<PersonaInput>(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const [cloningVoice, setCloningVoice] = useState(false);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [voices, setVoices] = useState<ElevenLabsVoice[]>([]);
  const [voicesLoading, setVoicesLoading] = useState(true);
  const [customVoiceId, setCustomVoiceId] = useState(false);
  const [playingSampleId, setPlayingSampleId] = useState<string | null>(null);

  function load() {
    setLoading(true);
    fetchPersonas()
      .then(setPersonas)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load personas"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  useEffect(() => {
    fetchVoices()
      .then(setVoices)
      .catch(() => setVoices([]))
      .finally(() => setVoicesLoading(false));
  }, []);

  function playSample(voice: ElevenLabsVoice) {
    if (!voice.preview_url || !audioRef.current) return;
    setPlayingSampleId(voice.voice_id);
    audioRef.current.src = voice.preview_url;
    audioRef.current.play().catch(() => setPlayingSampleId(null));
  }

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setCustomVoiceId(false);
    setShowForm(true);
  }

  function openEdit(p: PersonaPayload) {
    setEditingId(p.id);
    setForm({
      name: p.name,
      company: p.company,
      product_pitch: p.product_pitch,
      personality: p.personality,
      knowledge_text: p.knowledge_text,
      opening_line: p.opening_line,
      call_goal: p.call_goal,
      elevenlabs_voice_id: p.elevenlabs_voice_id,
      default_emotion: p.default_emotion,
      language_mode: p.language_mode || "auto",
    });
    setCustomVoiceId(
      !!p.elevenlabs_voice_id && !voices.some((v) => v.voice_id === p.elevenlabs_voice_id),
    );
    setShowForm(true);
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        await updatePersona(editingId, form);
      } else {
        await createPersona(form);
      }
      setShowForm(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save persona");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this persona? This can't be undone.")) return;
    try {
      await deletePersona(id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete persona");
    }
  }

  async function handlePreview(id: string, language: "en" | "ur" = "en") {
    setPreviewingId(`${id}:${language}`);
    try {
      const { audio, mime } = await previewPersonaVoice(id, language);
      if (audioRef.current) {
        audioRef.current.src = `data:${mime};base64,${audio}`;
        await audioRef.current.play();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice preview failed");
    } finally {
      setPreviewingId(null);
    }
  }

  async function handleCloneVoice(file: File) {
    setCloningVoice(true);
    setError("");
    try {
      const { voice_id } = await cloneVoice(form.name || "Custom Voice", file);
      setForm((f) => ({ ...f, elevenlabs_voice_id: voice_id }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice cloning failed -- check ELEVENLABS_API_KEY");
    } finally {
      setCloningVoice(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-[var(--color-signal)]">Command Center</p>
          <h1 className="mt-1.5 text-[26px] font-semibold tracking-[-0.01em] text-[var(--color-ink)] sm:text-[30px]">
            Sales Personas
          </h1>
          <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-[var(--color-slate)]">
            Build the identity your agent calls as -- name, company, pitch, personality, what it's
            allowed to claim, and its voice. Every persona follows the same cold-calling technique;
            these fields decide what it sells and how it sounds.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-[var(--color-signal)] px-4 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)]"
        >
          <Plus size={15} weight="bold" />
          New Persona
        </button>
      </header>

      {error && (
        <div className="rounded-xl bg-red-500/15 px-4 py-3 text-[13px] text-red-300 ring-1 ring-red-100">{error}</div>
      )}

      {loading ? (
        <p className="text-[13px] text-[var(--color-slate)]">Loading…</p>
      ) : personas.length === 0 ? (
        <div className="rounded-2xl bg-[var(--color-card)] p-8 text-center shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
          <p className="text-[14px] text-[var(--color-slate)]">No personas yet -- create your first one to start testing calls.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {personas.map((p) => (
            <div key={p.id} className="rounded-2xl bg-[var(--color-card)] p-5 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[15px] font-semibold text-[var(--color-ink)]">{p.name}</p>
                  <p className="truncate text-[12px] text-[var(--color-slate)]">{p.company || "No company set"}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => handlePreview(p.id, "en")}
                    disabled={previewingId === `${p.id}:en`}
                    title="Preview voice -- English"
                    className="flex h-8 items-center justify-center gap-1 rounded-lg px-2 text-[11px] font-semibold text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-signal)] disabled:opacity-50"
                  >
                    {previewingId === `${p.id}:en` ? (
                      <CircleNotch size={13} className="animate-spin" />
                    ) : (
                      <SpeakerHigh size={13} weight="fill" />
                    )}
                    EN
                  </button>
                  <button
                    onClick={() => handlePreview(p.id, "ur")}
                    disabled={previewingId === `${p.id}:ur`}
                    title="Preview voice -- Urdu"
                    className="flex h-8 items-center justify-center gap-1 rounded-lg px-2 text-[11px] font-semibold text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-signal)] disabled:opacity-50"
                  >
                    {previewingId === `${p.id}:ur` ? (
                      <CircleNotch size={13} className="animate-spin" />
                    ) : (
                      <SpeakerHigh size={13} weight="fill" />
                    )}
                    UR
                  </button>
                  <button
                    onClick={() => openEdit(p)}
                    title="Edit"
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-ink)]"
                  >
                    <PencilSimple size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    title="Delete"
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-red-500 ring-1 ring-[rgba(255,255,255,0.10)] transition-colors hover:bg-red-500/15"
                  >
                    <Trash size={14} />
                  </button>
                </div>
              </div>
              <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-[var(--color-slate)]">
                {p.product_pitch || "No pitch written yet."}
              </p>
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--color-signal-tint)] px-2.5 py-1 text-[10.5px] font-semibold capitalize text-[var(--color-signal)]">
                    {p.default_emotion}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(255,255,255,0.07)] px-2.5 py-1 text-[10.5px] font-semibold text-[var(--color-slate)]">
                    {p.language_mode === "english" ? "English only" : "Auto (EN/UR)"}
                  </span>
                </div>
                <a
                  href={`/dashboard/dialer?persona_id=${p.id}`}
                  className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-[var(--color-signal)] hover:underline"
                >
                  <PhoneCall size={12} weight="fill" />
                  Dial with this persona
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[rgba(0,0,0,0.55)] px-4 py-8">
          <div className="w-full max-w-xl rounded-2xl bg-[var(--color-card)] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-6 py-4">
              <p className="text-[15px] font-semibold text-[var(--color-ink)]">
                {editingId ? "Edit Persona" : "New Persona"}
              </p>
              <button
                onClick={() => setShowForm(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-slate)] hover:bg-[rgba(255,255,255,0.04)]"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleSave} className="max-h-[70vh] space-y-4 overflow-y-auto px-6 py-5">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Name">
                  <input
                    required
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Saad"
                    className={inputClass}
                  />
                </Field>
                <Field label="Company">
                  <input
                    value={form.company}
                    onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                    placeholder="Acme Inc."
                    className={inputClass}
                  />
                </Field>
              </div>

              <Field label="What you're selling">
                <textarea
                  value={form.product_pitch}
                  onChange={(e) => setForm((f) => ({ ...f, product_pitch: e.target.value }))}
                  placeholder="A one-sentence description of the product or service being pitched."
                  rows={2}
                  className={inputClass}
                />
              </Field>

              <Field label="Personality">
                <textarea
                  value={form.personality}
                  onChange={(e) => setForm((f) => ({ ...f, personality: e.target.value }))}
                  rows={2}
                  className={inputClass}
                />
              </Field>

              <Field label="Knowledge base -- pricing, features, FAQs (the only facts the agent may state)">
                <textarea
                  value={form.knowledge_text}
                  onChange={(e) => setForm((f) => ({ ...f, knowledge_text: e.target.value }))}
                  placeholder={"Plan: $49/mo, includes X, Y, Z.\nFree trial: 14 days.\nCommon question: ..."}
                  rows={5}
                  className={inputClass}
                />
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Opening line (optional)">
                  <input
                    value={form.opening_line}
                    onChange={(e) => setForm((f) => ({ ...f, opening_line: e.target.value }))}
                    placeholder="Auto-generated if left blank"
                    className={inputClass}
                  />
                </Field>
                <Field label="Call goal">
                  <input
                    value={form.call_goal}
                    onChange={(e) => setForm((f) => ({ ...f, call_goal: e.target.value }))}
                    className={inputClass}
                  />
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Default emotion">
                  <select
                    value={form.default_emotion}
                    onChange={(e) => setForm((f) => ({ ...f, default_emotion: e.target.value }))}
                    className={inputClass}
                  >
                    {EMOTIONS.map((e) => (
                      <option key={e} value={e}>{e}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Language">
                  <select
                    value={form.language_mode}
                    onChange={(e) => setForm((f) => ({ ...f, language_mode: e.target.value }))}
                    className={inputClass}
                  >
                    <option value="auto">Auto (mirror the caller -- English or Urdu)</option>
                    <option value="english">English only</option>
                  </select>
                </Field>
              </div>

              <Field label="Voice">
                {voicesLoading ? (
                  <p className="text-[12.5px] text-[var(--color-slate)]">Loading your ElevenLabs voices…</p>
                ) : voices.length === 0 || customVoiceId ? (
                  <div className="space-y-1.5">
                    <input
                      value={form.elevenlabs_voice_id}
                      onChange={(e) => setForm((f) => ({ ...f, elevenlabs_voice_id: e.target.value }))}
                      placeholder="Paste a voice ID or clone below"
                      className={inputClass}
                    />
                    {voices.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setCustomVoiceId(false)}
                        className="text-[11.5px] font-semibold text-[var(--color-signal)] hover:underline"
                      >
                        Choose from your ElevenLabs voices instead
                      </button>
                    )}
                    {voices.length === 0 && (
                      <p className="text-[11.5px] text-[var(--color-slate)]/70">
                        No voices found -- check ELEVENLABS_API_KEY is configured on the backend, or clone one below.
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <select
                        value={form.elevenlabs_voice_id}
                        onChange={(e) => setForm((f) => ({ ...f, elevenlabs_voice_id: e.target.value }))}
                        className={inputClass}
                      >
                        <option value="">Select a voice…</option>
                        {voices.map((v) => (
                          <option key={v.voice_id} value={v.voice_id}>
                            {v.name}{v.category ? ` (${v.category})` : ""}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          const v = voices.find((v) => v.voice_id === form.elevenlabs_voice_id);
                          if (v) playSample(v);
                        }}
                        disabled={!form.elevenlabs_voice_id}
                        title="Play a sample of this voice"
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-signal)] disabled:opacity-40"
                      >
                        {playingSampleId === form.elevenlabs_voice_id ? (
                          <CircleNotch size={14} className="animate-spin" />
                        ) : (
                          <SpeakerHigh size={14} weight="fill" />
                        )}
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => setCustomVoiceId(true)}
                      className="text-[11.5px] font-semibold text-[var(--color-signal)] hover:underline"
                    >
                      Or paste a voice ID manually
                    </button>
                  </div>
                )}
              </Field>

              <div className="rounded-xl bg-[rgba(255,255,255,0.04)] p-3 ring-1 ring-[rgba(255,255,255,0.08)]">
                <p className="mb-2 flex items-center gap-1.5 text-[11.5px] font-semibold text-[var(--color-slate)]">
                  <MicrophoneStage size={13} />
                  Clone a natural voice from a short recording (ElevenLabs Instant Voice Cloning)
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleCloneVoice(file);
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={cloningVoice}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-card)] px-3 py-1.5 text-[12px] font-semibold text-[var(--color-signal)] ring-1 ring-[rgba(5,118,118,0.25)] transition-colors hover:bg-[rgba(5,118,118,0.06)] disabled:opacity-50"
                >
                  {cloningVoice ? (
                    <CircleNotch size={13} className="animate-spin" />
                  ) : (
                    <UploadSimple size={13} weight="bold" />
                  )}
                  {cloningVoice ? "Cloning…" : "Upload reference audio"}
                </button>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[rgba(255,255,255,0.08)] pt-4">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="rounded-lg px-3.5 py-2 text-[12.5px] font-semibold text-[var(--color-slate)] hover:bg-[rgba(255,255,255,0.04)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving || !form.name.trim()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-signal)] px-4 py-2 text-[12.5px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)] disabled:opacity-50"
                >
                  {saving && <CircleNotch size={13} className="animate-spin" />}
                  {editingId ? "Save changes" : "Create persona"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <audio ref={audioRef} onEnded={() => setPlayingSampleId(null)} className="hidden" />
    </div>
  );
}

const inputClass =
  "w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 py-2 text-[13.5px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.10)] transition-shadow placeholder:text-[var(--color-slate)]/50 focus:bg-[var(--color-card)] focus:ring-2 focus:ring-[var(--color-signal)]/40";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70">
        {label}
      </span>
      {children}
    </label>
  );
}
