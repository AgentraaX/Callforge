import logging
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")
    LIVEKIT_AGENT_NAME: str = os.getenv("LIVEKIT_AGENT_NAME", "callforge-voice-agent")

    VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
    VLLM_MODEL: str = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct-AWQ")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
