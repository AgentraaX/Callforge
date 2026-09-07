"""CallForge production configuration via Pydantic Settings."""
from __future__ import annotations
from pydantic_settings import BaseSettings
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

class Settings(BaseSettings):
    # --- Core ---
    app_name: str = "CallForge AI Sales Voice Agent"
    debug: bool = False
    
    # --- Alibaba Cloud Model Studio ---
    dashscope_api_key: str = ""
    dashscope_app_id: str = ""
    dashscope_region: Literal["intl", "cn"] = "intl"
    
    # --- STT ---
    stt_engine: Literal["vibevoice", "whisper", "remote", "groq", "mock"] = "mock"
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute: str = "int8"
    voice_speech_base_url: str = ""
    voice_ai_token: str = ""
    
    # --- TTS ---
    tts_engine: Literal["cosyvoice", "edge", "elevenlabs", "uplift", "remote", "mock"] = "mock"
    elevenlabs_api_key: str = ""
    fish_api_key: str = ""
    voice_clone_ref_dir: str = "voice-samples"
    # Edge TTS speaking rate, e.g. "+0%", "+8%", "-5%". A slightly brisk
    # default reads more like a live phone agent than Edge's default pace.
    # Not applicable to Uplift AI (no speed param in its documented API) or
    # ElevenLabs (untested here -- no ELEVENLABS_API_KEY configured yet).
    tts_speaking_rate: str = "+6%"

    # --- Uplift AI (native Urdu TTS, ~300ms latency) ---
    uplift_api_key: str = ""
    uplift_output_format: str = "MP3_22050_128"
    uplift_phrase_replacement_config_id: str = ""
    # Engine used for English chunks + as an Urdu degrade path if Uplift fails.
    # "auto" picks elevenlabs when a key is configured, otherwise the free edge engine.
    uplift_english_engine: Literal["auto", "elevenlabs", "edge"] = "auto"

    # --- LLM ---
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_timeout_s: float = 12.0
    llm_temperature: float = 0.25

    # --- Groq STT (independent of which provider LLM_BASE_URL points at --
    # confirmed live: when LLM_BASE_URL was switched to a non-Groq endpoint,
    # groq_stt.py's old fallback to llm_api_key started sending that
    # endpoint's key/placeholder to Groq's transcription API instead,
    # silently 401'ing on every utterance) ---
    groq_api_key: str = ""

    # --- Urdu LLM fallback -- confirmed live: the small local-GPU model
    # (qwen2.5:7b / qwen3:8b via Ollama) produces broken, hallucinated Urdu,
    # while Groq's larger openai/gpt-oss-120b is fluent and stays grounded
    # in the same facts. English turns stay on the free/fast local GPU;
    # only turns detected as Urdu pay Groq's latency/rate-limit cost.
    # Falls back to GROQ_API_KEY (the STT key) if not set separately.
    urdu_llm_base_url: str = "https://api.groq.com/openai/v1"
    urdu_llm_api_key: str = ""
    urdu_llm_model: str = "openai/gpt-oss-120b"
    
    # --- Database (CRM persistence) ---
    # SQLAlchemy URL. Accepts a plain "postgresql://" or an explicit
    # "postgresql+asyncpg://" -- db_async_url / db_sync_url normalise it for
    # the async engine and for Alembic respectively. Empty => CRM endpoints
    # return 503 and the rest of the app runs unchanged.
    database_url: str = ""
    redis_url: str = ""
    # Dev convenience: create CRM tables from the models on startup when no
    # migration has run yet. Production uses `alembic upgrade head` instead.
    crm_auto_create_tables: bool = True
    
    # --- Call settings ---
    hold_ms: int = 8000
    max_call_duration_s: int = 600

    # --- Telnyx (real outbound phone calls + numbers) ---
    telnyx_api_key: str = ""
    # The "Voice API App" (formerly "Call Control Application") ID that
    # your Telnyx number is assigned to -- created in the Telnyx portal
    # under Voice > Programmable Voice > Voice API Apps.
    telnyx_connection_id: str = ""
    telnyx_from_number: str = ""
    # This backend's public HTTPS/WSS base URL -- Telnyx must be able to
    # reach it for the status webhook and the bidirectional Media
    # Streaming WebSocket. Use ngrok (or similar) in local dev, e.g.
    # https://abcd1234.ngrok.app
    public_base_url: str = ""

    # --- LiveKit (browser voice call -- real WebRTC, VAD, barge-in) ---
    # From a LiveKit Cloud project (cloud.livekit.io) -- free tier is
    # enough for a demo. The agent worker (app/voice_agent/agent.py)
    # connects out to this URL; no inbound ports needed on our side.
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # --- Internal (agent-worker <-> backend service calls) ---
    # The LiveKit agent worker is a SEPARATE OS process from this FastAPI
    # app -- it has no access to our in-memory persona/lead/booking/
    # escalation/call stores, so it reaches them over HTTP through the
    # /internal/* endpoints, guarded by this shared secret (never exposed
    # to the frontend). Generate any random string for local dev.
    internal_api_key: str = ""
    # This backend's URL as seen by the agent worker -- usually just
    # http://localhost:8000 when both run on the same machine.
    internal_backend_url: str = "http://localhost:8000"

    # --- OAuth (Google / GitHub) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    # This backend's own public URL -- used to build the callback redirect_uri
    # (e.g. http://localhost:8000/api/auth/oauth/google/callback). Must match
    # exactly what's registered in the Google/GitHub OAuth app settings.
    oauth_redirect_base_url: str = "http://localhost:8000"
    # Where the browser is sent back to once OAuth completes.
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def dashscope_base_url(self) -> str:
        if self.dashscope_region == "cn":
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    @property
    def effective_llm_base_url(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url
        if self.dashscope_api_key:
            return self.dashscope_base_url
        return ""

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.dashscope_api_key or "not-needed"

    @property
    def db_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def db_async_url(self) -> str:
        """Normalised URL for the async SQLAlchemy engine (asyncpg driver).

        Strips "sslmode"/"channel_binding" query params -- confirmed live
        that asyncpg's connect() doesn't accept them (crashes app startup
        with "connect() got an unexpected keyword argument 'sslmode'"),
        even though managed Postgres hosts like Neon include them by
        default in their libpq-style connection strings. SSL itself is
        still enforced -- see db_connect_args below, which asyncpg wants
        as an explicit ssl= kwarg instead of a URL query param.
        """
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            pass
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):  # some hosts still emit the old scheme
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        else:
            return url

        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k not in ("sslmode", "channel_binding")]
        return urlunsplit(parts._replace(query=urlencode(query)))

    @property
    def db_connect_args(self) -> dict:
        """asyncpg-specific connect() kwargs -- currently just SSL, derived
        from the original URL's sslmode (asyncpg wants this as a real
        kwarg, not a query param -- see db_async_url above)."""
        query = dict(parse_qsl(urlsplit(self.database_url).query))
        sslmode = query.get("sslmode", "")
        if sslmode in ("require", "verify-ca", "verify-full"):
            return {"ssl": "require"}
        return {}

    @property
    def db_sync_url(self) -> str:
        """Normalised URL for Alembic migrations (synchronous psycopg2 driver)."""
        url = self.database_url
        for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg2://" + url[len(prefix):]
        return url

    @property
    def telnyx_configured(self) -> bool:
        return bool(self.telnyx_api_key and self.telnyx_connection_id and self.telnyx_from_number)

    @property
    def livekit_configured(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)


settings = Settings()
