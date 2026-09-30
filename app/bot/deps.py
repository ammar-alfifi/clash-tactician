"""Dependency container shared by all handlers."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.factory import build_shared_configs, build_user_configs
from app.ai.providers import AiConfig
from app.ai.vault import KeyVault
from app.coc.service import CocService
from app.config import Settings
from app.planner.service import PlannerService
from app.storage.database import Database
from app.storage.repositories import (
    AccountRepo,
    AiKeyRepo,
    ClanRoomRepo,
    PlanRepo,
    SnapshotRepo,
    SubscriptionRepo,
    TicketRepo,
    UserRepo,
    WarStateRepo,
)


@dataclass
class Deps:
    settings: Settings
    db: Database
    users: UserRepo
    accounts: AccountRepo
    keys: AiKeyRepo
    rooms: ClanRoomRepo
    subs: SubscriptionRepo
    snapshots: SnapshotRepo
    plans: PlanRepo
    tickets: TicketRepo
    war_state: WarStateRepo
    coc: CocService
    vault: KeyVault
    planner: PlannerService

    async def ai_configs(self, telegram_id: int) -> list[AiConfig]:
        key = await self.keys.get(telegram_id)
        api_key = self.vault.decrypt(key.encrypted_key) if key else None
        if key and api_key:
            return build_user_configs(self.settings, key, api_key)
        return build_shared_configs(self.settings)

    async def has_ai(self, telegram_id: int) -> bool:
        return bool(await self.ai_configs(telegram_id))

    def is_admin(self, telegram_id: int) -> bool:
        return self.settings.is_admin(telegram_id)

    async def primary_tag(self, telegram_id: int) -> str | None:
        account = await self.accounts.primary(telegram_id)
        return account.player_tag if account else None


def build_deps(settings: Settings) -> Deps:
    database = Database(settings.database_path)
    return Deps(
        settings=settings,
        db=database,
        users=UserRepo(database),
        accounts=AccountRepo(database),
        keys=AiKeyRepo(database),
        rooms=ClanRoomRepo(database),
        subs=SubscriptionRepo(database),
        snapshots=SnapshotRepo(database),
        plans=PlanRepo(database),
        tickets=TicketRepo(database),
        war_state=WarStateRepo(database),
        coc=CocService(_coc_client(settings)),
        vault=KeyVault(settings.ai_key_encryption_key),
        planner=PlannerService(settings),
    )


def _coc_client(settings: Settings):
    from app.coc.client import CocClient

    return CocClient(
        settings.coc_api_token,
        base_url=settings.coc_base_url,
        timeout_seconds=settings.coc_timeout_seconds,
        cache_seconds=settings.coc_cache_seconds,
    )
