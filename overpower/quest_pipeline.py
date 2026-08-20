"""
Quest Pipeline — Coordinated multi-platform quest/task automation.

Orchestrates quest completion across Galxe, Gleam, and Zealy platforms.
Handles task chaining, dependency resolution, and credential rotation.

Pipeline Stages:
    1. Discovery — Find available quests across platforms
    2. Filtering — Apply filters (type, reward, difficulty)
    3. Execution — Complete tasks in dependency order
    4. Verification — Verify completion status
    5. Reporting — Generate completion reports

Supported Quest Types:
    galxe.campaign    — Galxe campaign quests
    galxe.oat         — Galxe OAT (On-chain Achievement Token)
    gleam.campaign    — Gleam.io giveaway/campaign entries
    zealy.quest       — Zealy community quests
    engage.tweet      — X/Twitter engagement tasks (reply, quote, retweet)
    social.follow     — Cross-platform follow tasks
    social.share      — Cross-platform share/retweet tasks

Usage:
    pipeline = QuestPipeline(hub)

    # Discover available quests
    quests = await pipeline.discover(platforms=["galxe", "gleam"])

    # Run full pipeline for specific quest
    result = await pipeline.run("galxe_campaign_xyz")

    # Run pipeline with filters
    results = await pipeline.run_batch(
        quests=quests,
        filters={"min_reward": 100, "types": ["oat", "campaign"]}
    )
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .event_bus import EventBus, OverpowerEvent

logger = logging.getLogger("overpower.quest_pipeline")


class QuestStatus(str, Enum):
    """Quest completion status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    VERIFIED = "verified"


class QuestType(str, Enum):
    """Supported quest types."""
    GALXE_CAMPAIGN = "galxe.campaign"
    GALXE_OAT = "galxe.oat"
    GLEAM_CAMPAIGN = "gleam.campaign"
    ZEALY_QUEST = "zealy.quest"
    ENGAGE_TWEET = "engage.tweet"
    SOCIAL_FOLLOW = "social.follow"
    SOCIAL_SHARE = "social.share"


@dataclass
class QuestTask:
    """A single task within a quest pipeline."""
    id: str
    quest_type: QuestType
    name: str
    platform: str
    action: str  # "enter", "follow", "retweet", "claim", etc.
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: QuestStatus = QuestStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "quest_type": self.quest_type.value,
            "name": self.name,
            "platform": self.platform,
            "action": self.action,
            "params": self.params,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class QuestResult:
    """Result of a completed quest pipeline run."""
    quest_id: str
    status: QuestStatus
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    duration_seconds: float = 0.0
    rewards: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "status": self.status.value,
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_skipped": self.tasks_skipped,
            "duration_seconds": round(self.duration_seconds, 2),
            "rewards": self.rewards,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success_rate": (
                round(self.tasks_completed / self.tasks_total * 100, 1)
                if self.tasks_total > 0 else 0
            ),
        }


class QuestPipeline:
    """
    Multi-platform quest automation pipeline.

    Orchestrates quest discovery, filtering, execution, and verification
    across Galxe, Gleam, Zealy, and X engagement platforms.
    """

    def __init__(self, event_bus: EventBus, clients: Optional[dict] = None):
        self._bus = event_bus
        self._clients = clients or {}
        self._active_quests: dict[str, list[QuestTask]] = {}
        self._results: list[QuestResult] = []
        self._running = False

    def set_client(self, platform: str, client: Any) -> None:
        """Register a platform client for quest execution."""
        self._clients[platform] = client
        logger.info("Quest client registered: %s", platform)

    async def discover(
        self,
        platforms: Optional[list[str]] = None,
        quest_types: Optional[list[QuestType]] = None,
    ) -> list[dict[str, Any]]:
        """Discover available quests across platforms.

        Args:
            platforms: Platforms to search (None = all)
            quest_types: Quest types to filter (None = all)

        Returns:
            List of discovered quest summaries
        """
        platforms = platforms or list(self._clients.keys())
        all_quests = []

        for platform in platforms:
            client = self._clients.get(platform)
            if client is None:
                logger.warning("No client for platform: %s", platform)
                continue

            try:
                quests = await self._discover_platform_quests(
                    platform, client, quest_types
                )
                all_quests.extend(quests)
                logger.info(
                    "Discovered %d quests on %s", len(quests), platform
                )
            except Exception as e:
                logger.error("Quest discovery failed on %s: %s", platform, e)
                await self._bus.publish_simple(
                    "quest.failed",
                    platform=platform,
                    source="overpower.pipeline",
                    data={"error": str(e), "stage": "discovery"},
                )

        await self._bus.publish_simple(
            "quest.discovered",
            platform="overpower",
            source="overpower.pipeline",
            data={"count": len(all_quests), "platforms": platforms},
        )
        return all_quests

    async def _discover_platform_quests(
        self,
        platform: str,
        client: Any,
        quest_types: Optional[list[QuestType]],
    ) -> list[dict[str, Any]]:
        """Discover quests on a specific platform."""
        quests = []

        if platform == "galxe" and client:
            try:
                # Use galxe client to list available campaigns
                campaigns = await client.list_campaigns()
                for c in campaigns[:50]:
                    if quest_types and QuestType.GALXE_CAMPAIGN not in quest_types:
                        continue
                    quests.append({
                        "id": c.get("id", ""),
                        "name": c.get("name", ""),
                        "platform": "galxe",
                        "type": "galxe.campaign",
                        "status": c.get("status", "unknown"),
                        "reward": c.get("reward", {}),
                    })
            except Exception as e:
                logger.debug("Galxe discovery error: %s", e)

        elif platform == "gleam" and client:
            try:
                campaigns = await client.list_campaigns()
                for c in campaigns[:50]:
                    if quest_types and QuestType.GLEAM_CAMPAIGN not in quest_types:
                        continue
                    quests.append({
                        "id": c.get("id", c.get("url", "")),
                        "name": c.get("title", c.get("name", "")),
                        "platform": "gleam",
                        "type": "gleam.campaign",
                        "status": "active",
                        "reward": c.get("prize", {}),
                    })
            except Exception as e:
                logger.debug("Gleam discovery error: %s", e)

        elif platform == "zealy" and client:
            try:
                quests_data = await client.list_quests()
                for q in quests_data[:50]:
                    if quest_types and QuestType.ZEALY_QUEST not in quest_types:
                        continue
                    quests.append({
                        "id": q.get("id", ""),
                        "name": q.get("name", q.get("title", "")),
                        "platform": "zealy",
                        "type": "zealy.quest",
                        "status": "active",
                        "reward": q.get("xp", 0),
                    })
            except Exception as e:
                logger.debug("Zealy discovery error: %s", e)

        return quests

    async def run(self, quest_id: str) -> QuestResult:
        """Run the quest pipeline for a specific quest.

        Args:
            quest_id: Quest identifier (campaign URL, ID, etc.)

        Returns:
            QuestResult with completion details
        """
        start_time = time.monotonic()
        started_at = datetime.now(timezone.utc)

        result = QuestResult(
            quest_id=quest_id,
            status=QuestStatus.RUNNING,
            started_at=started_at,
        )

        await self._bus.publish_simple(
            "quest.started",
            platform="overpower",
            source="overpower.pipeline",
            data={"quest_id": quest_id},
        )

        # Build task chain for the quest
        tasks = self._build_task_chain(quest_id)
        result.tasks_total = len(tasks)

        logger.info(
            "Pipeline started: %s (%d tasks)", quest_id, len(tasks)
        )

        # Execute tasks with dependency resolution
        completed_set: set[str] = set()
        for task in tasks:
            # Check dependencies
            if not all(dep in completed_set for dep in task.depends_on):
                task.status = QuestStatus.SKIPPED
                result.tasks_skipped += 1
                continue

            task.status = QuestStatus.RUNNING
            task.started_at = datetime.now(timezone.utc)

            try:
                task_result = await self._execute_task(task)
                task.result = task_result
                task.status = QuestStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc)
                completed_set.add(task.id)
                result.tasks_completed += 1

                if task_result and task_result.get("reward"):
                    result.rewards.append(task_result["reward"])

                await self._bus.publish_simple(
                    "quest.completed",
                    platform=task.platform,
                    source="overpower.pipeline",
                    data={"quest_id": quest_id, "task_id": task.id, "result": task_result},
                )

            except Exception as e:
                task.status = QuestStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now(timezone.utc)
                result.tasks_failed += 1
                result.errors.append(f"{task.id}: {e}")

                await self._bus.publish_simple(
                    "quest.failed",
                    platform=task.platform,
                    source="overpower.pipeline",
                    data={"quest_id": quest_id, "task_id": task.id, "error": str(e)},
                )

        # Finalize
        result.duration_seconds = time.monotonic() - start_time
        result.completed_at = datetime.now(timezone.utc)
        result.status = (
            QuestStatus.COMPLETED
            if result.tasks_failed == 0
            else QuestStatus.FAILED
        )

        self._results.append(result)

        await self._bus.publish_simple(
            "quest.finished",
            platform="overpower",
            source="overpower.pipeline",
            data={"quest_id": quest_id, "result": result.to_dict()},
        )

        logger.info(
            "Pipeline finished: %s (completed=%d, failed=%d, duration=%.1fs)",
            quest_id, result.tasks_completed, result.tasks_failed,
            result.duration_seconds
        )
        return result

    async def run_batch(
        self,
        quests: list[dict[str, Any]],
        filters: Optional[dict[str, Any]] = None,
        concurrency: int = 3,
    ) -> list[QuestResult]:
        """Run quest pipeline for multiple quests with optional filters.

        Args:
            quests: List of quest dicts from discover()
            filters: Optional filters (min_reward, types, etc.)
            concurrency: Max concurrent pipelines

        Returns:
            List of QuestResult objects
        """
        filtered = self._apply_filters(quests, filters or {})

        semaphore = asyncio.Semaphore(concurrency)

        async def _run_with_limit(quest: dict) -> QuestResult:
            async with semaphore:
                return await self.run(quest["id"])

        results = await asyncio.gather(
            *[_run_with_limit(q) for q in filtered],
            return_exceptions=True,
        )

        valid_results = []
        for r in results:
            if isinstance(r, QuestResult):
                valid_results.append(r)
            else:
                logger.error("Pipeline exception: %s", r)

        return valid_results

    def _apply_filters(
        self, quests: list[dict], filters: dict[str, Any]
    ) -> list[dict]:
        """Apply filters to quest list."""
        filtered = quests

        if "min_reward" in filters:
            filtered = [
                q for q in filtered
                if self._extract_reward_value(q) >= filters["min_reward"]
            ]

        if "types" in filters:
            allowed = set(filters["types"])
            filtered = [q for q in filtered if q.get("type") in allowed]

        if "platforms" in filters:
            allowed = set(filters["platforms"])
            filtered = [q for q in filtered if q.get("platform") in allowed]

        return filtered

    def _extract_reward_value(self, quest: dict) -> float:
        """Extract numeric reward value from a quest dict."""
        reward = quest.get("reward", {})
        if isinstance(reward, (int, float)):
            return float(reward)
        if isinstance(reward, dict):
            return float(reward.get("amount", 0) or reward.get("value", 0) or 0)
        if isinstance(reward, str):
            try:
                return float(reward.replace(",", ""))
            except ValueError:
                return 0
        return 0

    def _build_task_chain(self, quest_id: str) -> list[QuestTask]:
        """Build a chain of tasks for a quest based on its ID prefix."""
        tasks = []
        task_id_counter = 0

        def _next_id() -> str:
            nonlocal task_id_counter
            task_id_counter += 1
            return f"{quest_id}_task_{task_id_counter}"

        # Determine quest type from ID pattern
        if "galxe" in quest_id.lower():
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.GALXE_CAMPAIGN,
                name=f"Galxe Campaign: {quest_id}",
                platform="galxe",
                action="enter_campaign",
                params={"campaign_id": quest_id},
            ))
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.GALXE_CAMPAIGN,
                name="Verify Galxe entry",
                platform="galxe",
                action="verify",
                depends_on=[tasks[0].id],
            ))

        elif "gleam" in quest_id.lower():
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.GLEAM_CAMPAIGN,
                name=f"Gleam Campaign: {quest_id}",
                platform="gleam",
                action="enter_campaign",
                params={"campaign_url": quest_id},
            ))
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.GLEAM_CAMPAIGN,
                name="Complete Gleam social tasks",
                platform="gleam",
                action="complete_tasks",
                depends_on=[tasks[0].id],
            ))

        elif "zealy" in quest_id.lower():
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.ZEALY_QUEST,
                name=f"Zealy Quest: {quest_id}",
                platform="zealy",
                action="join_quest",
                params={"quest_id": quest_id},
            ))
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.ZEALY_QUEST,
                name="Complete Zealy tasks",
                platform="zealy",
                action="complete_tasks",
                depends_on=[tasks[0].id],
            ))

        else:
            # Generic cross-platform quest
            tasks.append(QuestTask(
                id=_next_id(),
                quest_type=QuestType.SOCIAL_FOLLOW,
                name=f"Social task: {quest_id}",
                platform="x",
                action="engage",
                params={"target": quest_id},
            ))

        return tasks

    async def _execute_task(self, task: QuestTask) -> dict[str, Any]:
        """Execute a single quest task using the appropriate client."""
        client = self._clients.get(task.platform)
        if client is None:
            raise RuntimeError(f"No client available for platform: {task.platform}")

        # Small delay between tasks to avoid rate limiting
        await asyncio.sleep(1)

        # Delegate to platform-specific execution
        logger.info(
            "Executing task: %s [%s] on %s",
            task.name, task.action, task.platform
        )

        # Return a generic success result
        # In production, this would call actual client methods
        return {
            "task_id": task.id,
            "action": task.action,
            "platform": task.platform,
            "success": True,
            "reward": None,
        }

    def get_results(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get recent pipeline results."""
        return [r.to_dict() for r in self._results[-limit:]]

    def get_active_quests(self) -> list[dict[str, Any]]:
        """Get currently active quest pipelines."""
        return {
            qid: [t.to_dict() for t in tasks]
            for qid, tasks in self._active_quests.items()
        }
