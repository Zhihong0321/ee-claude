"""Runtime-editable settings, backed by the app_settings table.

A row in app_settings overrides the matching .env default; an empty/missing
row falls back to .env (see app/config.py). This lets the in-app Settings
page change API keys/tokens without a restart, while keeping .env as the
first-boot default.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AppSetting


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    description: str
    env_default: str | None
    secret: bool = True  # secrets are masked in the API/UI; URLs are shown in full
    group: str | None = None  # groups rows visually in the settings UI (e.g. paired base URL + key)


KNOWN_SETTINGS: list[SettingSpec] = [
    SettingSpec(
        key="llm_primary_base_url",
        label="AI Base URL (primary)",
        description="Each API key is issued by a specific third-party proxy, so its base URL travels with it.",
        env_default=settings.anthropic_base_url,
        secret=False,
        group="llm_primary",
    ),
    SettingSpec(
        key="llm_primary_api_key",
        label="AI API Key (primary)",
        description="Overrides ANTHROPIC_AUTH_TOKEN for the primary LLM provider.",
        env_default=settings.anthropic_auth_token,
        group="llm_primary",
    ),
    SettingSpec(
        key="llm_backup_base_url",
        label="AI Base URL (backup)",
        description="Base URL for the backup provider - pair with the API key below, they belong to the same third-party provider.",
        env_default=settings.backup_anthropic_base_url,
        secret=False,
        group="llm_backup",
    ),
    SettingSpec(
        key="llm_backup_api_key",
        label="AI API Key (backup)",
        description="Used automatically if the primary provider fails.",
        env_default=settings.backup_anthropic_api_key,
        group="llm_backup",
    ),
    SettingSpec(
        key="github_token",
        label="GitHub Token",
        description="Personal access token so the Agent (Builder mode) can read, write, and publish to GitHub via git/gh.",
        env_default=None,
    ),
]

KNOWN_KEYS = {spec.key for spec in KNOWN_SETTINGS}


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


async def get_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.get(AppSetting, key)
    if row is not None and row.value:
        return row.value
    for spec in KNOWN_SETTINGS:
        if spec.key == key:
            return spec.env_default
    return None


async def get_settings(session: AsyncSession, keys: list[str]) -> dict[str, str | None]:
    result = await session.execute(select(AppSetting).where(AppSetting.key.in_(keys)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value}
    env_defaults = {spec.key: spec.env_default for spec in KNOWN_SETTINGS if spec.key in keys}
    return {key: overrides.get(key) or env_defaults.get(key) for key in keys}


async def set_setting(session: AsyncSession, key: str, value: str | None) -> None:
    row = await session.get(AppSetting, key)
    value = value.strip() if value else None
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    await session.commit()


async def list_settings_status(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(AppSetting).where(AppSetting.key.in_(KNOWN_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value}
    out = []
    for spec in KNOWN_SETTINGS:
        override_value = overrides.get(spec.key)
        current_value = override_value or spec.env_default
        source = "override" if override_value else ("env_default" if spec.env_default else "unset")
        displayed = None
        if current_value:
            displayed = _mask(current_value) if spec.secret else current_value
        out.append(
            {
                "key": spec.key,
                "label": spec.label,
                "description": spec.description,
                "source": source,
                "masked": displayed,
                "secret": spec.secret,
                "group": spec.group,
            }
        )
    return out
