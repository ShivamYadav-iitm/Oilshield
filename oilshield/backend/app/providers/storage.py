"""Concrete ``ScenarioRepository`` implementations (Requirement 7).

Two interchangeable back-ends persist and restore saved scenarios behind the
:class:`app.providers.ScenarioRepository` protocol, so either can back the
Scenario_Simulator without any service-code change (design: "The Scenario
Repository interface hides SQLite; swapping to Postgres is a one-file change"):

- :class:`JsonFileScenarioRepository` -- absolute-simplest setup: one JSON file
  per saved scenario under a configurable directory.
- :class:`SqliteScenarioRepository` -- a single-file SQLite database (stdlib
  ``sqlite3``); ``save`` upserts by id.

Both guarantee the same contract:

- ``save(record)`` serializes the scenario, generates and returns an id.
- ``load(scenario_id)`` deserializes it back into a :class:`SavedScenario`,
  raising :class:`ScenarioLoadError` if the stored representation is missing,
  malformed, or version-incompatible -- never returning a partial or default
  scenario (Requirement 7.3).

Round-trip guarantee (Requirement 7.2 / Property 16): for any compatible
scenario ``s``, ``load(save(s))`` yields a :class:`SavedScenario` whose ``name``
and assumption values are identical to those saved.

Requirements: 7.1, 7.2, 7.3
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from app.core.errors import ScenarioLoadError
from app.models import SavedScenario

__all__ = [
    "CURRENT_SCENARIO_VERSION",
    "MIN_SUPPORTED_SCENARIO_VERSION",
    "JsonFileScenarioRepository",
    "SqliteScenarioRepository",
]

# The scenario serialization format version this build writes. Stored files /
# rows carrying a version outside the supported window are treated as
# incompatible on load (Requirement 7.3).
CURRENT_SCENARIO_VERSION: Final[int] = 1
MIN_SUPPORTED_SCENARIO_VERSION: Final[int] = 1

# Default on-disk locations, kept under app/data so the offline demo and tests
# use the same predictable paths.
_DATA_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_JSON_DIR: Final[Path] = _DATA_DIR / ".scenarios"
_DEFAULT_SQLITE_PATH: Final[Path] = _DATA_DIR / "scenarios.db"


def _new_id() -> str:
    """Generate a compact, collision-resistant scenario id."""
    return uuid.uuid4().hex


def _is_version_compatible(version: object) -> bool:
    """Return True when ``version`` is an int within the supported window."""
    return (
        isinstance(version, int)
        and not isinstance(version, bool)
        and MIN_SUPPORTED_SCENARIO_VERSION <= version <= CURRENT_SCENARIO_VERSION
    )


def _deserialize(payload: str, *, scenario_id: str) -> SavedScenario:
    """Parse a stored JSON payload into a validated :class:`SavedScenario`.

    Raises:
        ScenarioLoadError: If the payload is not valid JSON, does not match the
            :class:`SavedScenario` shape, or carries an incompatible version.
    """
    try:
        raw = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ScenarioLoadError(
            f"Saved scenario '{scenario_id}' is malformed and could not be parsed: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ScenarioLoadError(
            f"Saved scenario '{scenario_id}' is malformed: expected an object, "
            f"got {type(raw).__name__}."
        )

    if not _is_version_compatible(raw.get("version")):
        raise ScenarioLoadError(
            f"Saved scenario '{scenario_id}' has an incompatible version "
            f"{raw.get('version')!r}; this build supports versions "
            f"{MIN_SUPPORTED_SCENARIO_VERSION}..{CURRENT_SCENARIO_VERSION}."
        )

    try:
        return SavedScenario.model_validate(raw)
    except PydanticValidationError as exc:
        raise ScenarioLoadError(
            f"Saved scenario '{scenario_id}' failed to deserialize: {exc}"
        ) from exc


class JsonFileScenarioRepository:
    """Stores each saved scenario as one JSON file in a directory.

    The storage directory is configurable and created on first use, so the
    simplest possible setup (no database) works out of the box.
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self._dir = Path(storage_dir) if storage_dir is not None else _DEFAULT_JSON_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, scenario_id: str) -> Path:
        return self._dir / f"{scenario_id}.json"

    def save(self, record: SavedScenario) -> str:
        """Serialize ``record`` to a JSON file and return its generated id."""
        scenario_id = _new_id()
        payload = record.model_dump_json()
        # Write atomically-ish: write then leave in place. A temp file avoids a
        # torn file if the process dies mid-write.
        path = self._path_for(scenario_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
        return scenario_id

    def load(self, scenario_id: str) -> SavedScenario:
        """Read and deserialize the scenario stored under ``scenario_id``.

        Raises:
            ScenarioLoadError: If the file is missing, malformed, or
                version-incompatible.
        """
        path = self._path_for(scenario_id)
        try:
            payload = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ScenarioLoadError(
                f"No saved scenario found for id '{scenario_id}'."
            ) from exc
        except OSError as exc:
            raise ScenarioLoadError(
                f"Saved scenario '{scenario_id}' could not be read: {exc}"
            ) from exc
        return _deserialize(payload, scenario_id=scenario_id)


class SqliteScenarioRepository:
    """Stores saved scenarios as rows in a single-file SQLite database.

    Uses the standard-library ``sqlite3`` driver. ``save`` upserts by id; the
    JSON payload is validated on ``load`` so a corrupt row raises rather than
    returning a partial scenario.
    """

    _TABLE: Final[str] = "saved_scenarios"

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else _DEFAULT_SQLITE_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._TABLE} (
                    id       TEXT PRIMARY KEY,
                    version  INTEGER NOT NULL,
                    payload  TEXT NOT NULL
                )
                """
            )

    def save(self, record: SavedScenario) -> str:
        """Upsert ``record`` and return its generated id."""
        scenario_id = _new_id()
        payload = record.model_dump_json()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                f"""
                INSERT INTO {self._TABLE} (id, version, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    payload = excluded.payload
                """,
                (scenario_id, record.version, payload),
            )
        return scenario_id

    def load(self, scenario_id: str) -> SavedScenario:
        """Read and deserialize the scenario row for ``scenario_id``.

        Raises:
            ScenarioLoadError: If no row exists, or the stored payload is
                malformed or version-incompatible.
        """
        try:
            with closing(self._connect()) as conn:
                cursor = conn.execute(
                    f"SELECT payload FROM {self._TABLE} WHERE id = ?",
                    (scenario_id,),
                )
                row = cursor.fetchone()
        except sqlite3.Error as exc:
            raise ScenarioLoadError(
                f"Saved scenario '{scenario_id}' could not be read: {exc}"
            ) from exc

        if row is None:
            raise ScenarioLoadError(
                f"No saved scenario found for id '{scenario_id}'."
            )
        return _deserialize(row[0], scenario_id=scenario_id)
