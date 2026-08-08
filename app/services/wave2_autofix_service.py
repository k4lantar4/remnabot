import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import and_, case, func, select

from app.config import settings
from app.database.database import db_manager
from app.database.models import Subscription, SubscriptionStatus, User
from app.utils.timezone import format_local_datetime


logger = structlog.get_logger(__name__)


@dataclass
class Wave2AutofixRunResult:
    scanned_groups: int
    fixed_groups: int
    disabled_subscriptions: int
    report_path: str | None


class Wave2AutofixService:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False
        self._bot: Any | None = None

    def set_bot(self, bot: Any) -> None:
        self._bot = bot

    def is_enabled(self) -> bool:
        return bool(getattr(settings, 'WAVE2_AUTOFIX_ENABLED', False))

    def get_interval_minutes(self) -> int:
        try:
            value = int(getattr(settings, 'WAVE2_AUTOFIX_INTERVAL_MINUTES', 10))
        except (TypeError, ValueError):
            value = 10
        return max(1, value)

    def get_report_dir(self) -> Path:
        raw = str(getattr(settings, 'WAVE2_AUTOFIX_REPORT_DIR', 'var/wave2_autofix') or '').strip()
        if not raw:
            raw = 'var/wave2_autofix'
        return Path(raw)

    def get_max_changes_per_run(self) -> int:
        try:
            value = int(getattr(settings, 'WAVE2_AUTOFIX_MAX_CHANGES_PER_RUN', 50))
        except (TypeError, ValueError):
            value = 50
        return max(1, value)

    def get_max_groups_per_run(self) -> int:
        try:
            value = int(getattr(settings, 'WAVE2_AUTOFIX_MAX_GROUPS_PER_RUN', 200))
        except (TypeError, ValueError):
            value = 200
        return max(1, value)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        if not self.is_enabled():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run_once(self) -> Wave2AutofixRunResult:
        now = datetime.now(UTC)
        live_statuses = {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.LIMITED.value,
            SubscriptionStatus.TRIAL.value,
        }

        max_groups = self.get_max_groups_per_run()
        max_changes = self.get_max_changes_per_run()
        report_dir = self.get_report_dir()
        report_dir.mkdir(parents=True, exist_ok=True)

        note_tag = f'auto_fix:wave2_dedupe_remnawave_uuid {now.strftime("%Y-%m-%d")}'

        report: dict[str, Any] = {
            'run_at_utc': now.isoformat(),
            'run_at_local': format_local_datetime(now, '%Y-%m-%d %H:%M:%S %Z'),
            'max_groups_per_run': max_groups,
            'max_changes_per_run': max_changes,
            'groups': [],
        }

        scanned_groups = 0
        fixed_groups = 0
        disabled_subscriptions = 0

        async with db_manager.session(read_only=False) as db:
            dup_uuids_result = await db.execute(
                select(Subscription.remnawave_uuid)
                .where(
                    and_(
                        Subscription.remnawave_uuid.is_not(None),
                        Subscription.status.in_(list(live_statuses)),
                        Subscription.end_date > now,
                    )
                )
                .group_by(Subscription.remnawave_uuid)
                .having(func.count(Subscription.id) > 1)
                .order_by(func.max(Subscription.updated_at).desc())
                .limit(max_groups)
            )
            dup_uuids = [row[0] for row in dup_uuids_result.all() if row and row[0]]

            if not dup_uuids:
                report_path = self._write_report(report_dir, report)
                return Wave2AutofixRunResult(
                    scanned_groups=0,
                    fixed_groups=0,
                    disabled_subscriptions=0,
                    report_path=report_path,
                )

            status_priority = case(
                (Subscription.status == SubscriptionStatus.ACTIVE.value, 0),
                (Subscription.status == SubscriptionStatus.LIMITED.value, 1),
                (Subscription.status == SubscriptionStatus.TRIAL.value, 2),
                else_=3,
            )

            subs_result = await db.execute(
                select(Subscription, User.telegram_id)
                .join(User, User.id == Subscription.user_id)
                .where(
                    and_(
                        Subscription.remnawave_uuid.in_(dup_uuids),
                        Subscription.status.in_(list(live_statuses)),
                        Subscription.end_date > now,
                    )
                )
                .order_by(
                    Subscription.remnawave_uuid.asc(),
                    status_priority.asc(),
                    Subscription.end_date.desc().nulls_last(),
                    Subscription.updated_at.desc().nulls_last(),
                    Subscription.created_at.desc(),
                    Subscription.id.desc(),
                )
            )

            by_uuid: dict[str, list[tuple[Subscription, int | None]]] = {}
            for sub, telegram_id in subs_result.all():
                uuid = (sub.remnawave_uuid or '').strip()
                if not uuid:
                    continue
                by_uuid.setdefault(uuid, []).append((sub, telegram_id))

            for uuid, items in by_uuid.items():
                if len(items) <= 1:
                    continue

                scanned_groups += 1
                survivor, survivor_tid = items[0]
                to_disable: list[tuple[Subscription, int | None]] = items[1:]

                changes_in_group = 0
                disabled_ids: list[int] = []
                disabled_user_ids: list[int] = []

                for sub, _tid in to_disable:
                    if disabled_subscriptions >= max_changes:
                        break
                    if sub.status == SubscriptionStatus.DISABLED.value:
                        continue
                    sub.status = SubscriptionStatus.DISABLED.value
                    sub.updated_at = now
                    existing_note = (sub.purchase_note or '').strip()
                    if note_tag not in existing_note:
                        sub.purchase_note = note_tag if not existing_note else f'{existing_note} | {note_tag}'
                    disabled_subscriptions += 1
                    changes_in_group += 1
                    disabled_ids.append(sub.id)
                    disabled_user_ids.append(sub.user_id)

                if changes_in_group > 0:
                    fixed_groups += 1

                report['groups'].append(
                    {
                        'remnawave_uuid': uuid,
                        'survivor': {
                            'subscription_id': survivor.id,
                            'user_id': survivor.user_id,
                            'telegram_id': survivor_tid,
                            'status': survivor.status,
                            'end_date': survivor.end_date.isoformat() if survivor.end_date else None,
                            'updated_at': survivor.updated_at.isoformat() if survivor.updated_at else None,
                            'remnawave_short_uuid': survivor.remnawave_short_uuid,
                            'remnawave_short_id': survivor.remnawave_short_id,
                        },
                        'disabled_subscription_ids': disabled_ids,
                        'disabled_user_ids': disabled_user_ids,
                        'capped_by_max_changes': disabled_subscriptions >= max_changes,
                    }
                )

                if disabled_subscriptions >= max_changes:
                    break

        report_path = self._write_report(report_dir, report)
        return Wave2AutofixRunResult(
            scanned_groups=scanned_groups,
            fixed_groups=fixed_groups,
            disabled_subscriptions=disabled_subscriptions,
            report_path=report_path,
        )

    def _write_report(self, report_dir: Path, report: dict[str, Any]) -> str:
        now = datetime.now(UTC)
        name = f'wave2_autofix_{now.strftime("%Y%m%d_%H%M%S")}_utc.json'
        path = report_dir / name
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        latest = report_dir / 'latest.json'
        try:
            latest.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            latest.symlink_to(path.name)
        except Exception:
            latest.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
        return str(path)

    async def _loop(self) -> None:
        interval = self.get_interval_minutes()
        logger.info('Wave2Autofix loop started', interval_minutes=interval)
        while self._running:
            try:
                result = await self.run_once()
                logger.info(
                    'Wave2Autofix run finished',
                    scanned_groups=result.scanned_groups,
                    fixed_groups=result.fixed_groups,
                    disabled_subscriptions=result.disabled_subscriptions,
                    report_path=result.report_path,
                )
            except Exception as e:
                logger.error('Wave2Autofix run failed', error=e)
            await asyncio.sleep(interval * 60)


wave2_autofix_service = Wave2AutofixService()

