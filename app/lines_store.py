"""Хранилище конфигов линий: JSON-файл + атомарная запись.

Позже легко заменить на SQLite — интерфейс (get/list/save/delete)
останется тем же.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .schemas import Line, LinesConfig, LinesConfigCreate, LinesConfigPatch


class LinesStore:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.RLock()
        self._configs: dict[str, LinesConfig] = {}
        self._load()

    # --- внутреннее ---

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
        for cid, payload in raw.items():
            try:
                self._configs[cid] = LinesConfig.model_validate(payload)
            except Exception:
                continue

    def _flush_locked(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        data = {
            cid: cfg.model_dump(mode="json")
            for cid, cfg in self._configs.items()
        }
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    # --- публичный API ---

    def list(self) -> list[LinesConfig]:
        with self._lock:
            return sorted(
                self._configs.values(),
                key=lambda c: c.updated_at,
                reverse=True,
            )

    def get(self, config_id: str) -> Optional[LinesConfig]:
        with self._lock:
            return self._configs.get(config_id)

    def create(self, data: LinesConfigCreate) -> LinesConfig:
        now = datetime.utcnow()
        cfg = LinesConfig(
            id=uuid.uuid4().hex[:12],
            name=data.name,
            frame_width=data.frame_width,
            frame_height=data.frame_height,
            lines=list(data.lines),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._configs[cfg.id] = cfg
            self._flush_locked()
        return cfg

    def replace(self, config_id: str, data: LinesConfigCreate) -> Optional[LinesConfig]:
        """PUT — полная замена, id и created_at сохраняются."""
        with self._lock:
            existing = self._configs.get(config_id)
            if existing is None:
                return None
            updated = LinesConfig(
                id=existing.id,
                name=data.name,
                frame_width=data.frame_width,
                frame_height=data.frame_height,
                lines=list(data.lines),
                created_at=existing.created_at,
                updated_at=datetime.utcnow(),
            )
            self._configs[config_id] = updated
            self._flush_locked()
            return updated

    def patch(self, config_id: str, data: LinesConfigPatch) -> Optional[LinesConfig]:
        """PATCH — частичное обновление."""
        with self._lock:
            existing = self._configs.get(config_id)
            if existing is None:
                return None

            patch_dict = data.model_dump(exclude_unset=True)
            # lines: list[Line] → list[Line] (Pydantic уже провалидировал)
            if "lines" in patch_dict and patch_dict["lines"] is not None:
                patch_dict["lines"] = [Line(**ln) for ln in patch_dict["lines"]]

            updated = existing.model_copy(
                update={**patch_dict, "updated_at": datetime.utcnow()},
            )
            self._configs[config_id] = updated
            self._flush_locked()
            return updated

    def delete(self, config_id: str) -> bool:
        with self._lock:
            if config_id not in self._configs:
                return False
            del self._configs[config_id]
            self._flush_locked()
            return True

    def ensure_default(self, default_lines: list[dict]) -> LinesConfig:
        """Если хранилище пусто — создаёт дефолтный конфиг.

        Возвращает существующий или только что созданный.
        """
        with self._lock:
            if self._configs:
                # отдаём самый свежий
                return max(
                    self._configs.values(),
                    key=lambda c: c.updated_at,
                )
        return self.create(LinesConfigCreate(
            name="Default",
            lines=[Line(**ln) for ln in default_lines],
        ))
