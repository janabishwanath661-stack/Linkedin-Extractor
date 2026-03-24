"""
storage/db_handler.py — SQLite storage and JSON/CSV export for extracted profiles.
"""

import csv
import json
import sqlite3
from pathlib import Path

from loguru import logger

from config import DB_PATH
from validation.schema import LinkedInProfile


class DBHandler:
    """Manages SQLite persistence and export for LinkedIn profiles."""

    def __init__(self) -> None:
        db_dir = Path(DB_PATH).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._create_table()
        logger.info("Database ready at {}", DB_PATH)

    def _create_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name       TEXT NOT NULL,
                profile_url     TEXT,
                raw_json        TEXT,
                extracted_at    TEXT,
                confidence_score REAL
            )
            """
        )
        self.conn.commit()

    def save_profile(self, profile: LinkedInProfile, profile_url: str) -> None:
        """Insert or replace a profile record."""
        self.conn.execute(
            """
            INSERT INTO profiles (full_name, profile_url, raw_json, extracted_at, confidence_score)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                profile.full_name,
                profile_url,
                profile.model_dump_json(indent=2),
                profile.extracted_at.isoformat(),
                profile.confidence_score,
            ),
        )
        self.conn.commit()
        logger.info("Profile for '{}' saved to database", profile.full_name)

    def export_json(self, full_name: str, output_path: str) -> None:
        """Export a profile by name to a pretty-printed JSON file."""
        row = self.conn.execute(
            "SELECT raw_json FROM profiles WHERE full_name = ? ORDER BY id DESC LIMIT 1",
            (full_name,),
        ).fetchone()

        if row is None:
            logger.warning("No profile found for '{}' in database", full_name)
            return

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(row["raw_json"])
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("JSON exported to {}", output_path)

    def export_csv(self, output_path: str) -> None:
        """Export all profiles to a flat CSV file."""
        rows = self.conn.execute(
            "SELECT full_name, profile_url, raw_json, extracted_at, confidence_score FROM profiles"
        ).fetchall()

        if not rows:
            logger.warning("No profiles in database to export")
            return

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "full_name", "headline", "location", "about", "current_company",
            "connections", "experience", "education", "skills",
            "certifications", "languages", "email", "website", "phone",
            "profile_url", "extracted_at", "confidence_score",
        ]

        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                data = json.loads(row["raw_json"])
                flat = {
                    "full_name": data.get("full_name", ""),
                    "headline": data.get("headline", ""),
                    "location": data.get("location", ""),
                    "about": data.get("about", ""),
                    "current_company": data.get("current_company", ""),
                    "connections": data.get("connections", ""),
                    "experience": " | ".join(
                        f"{e.get('title', '')} @ {e.get('company', '')}"
                        for e in data.get("experience", [])
                    ),
                    "education": " | ".join(
                        f"{e.get('degree', '')} — {e.get('institution', '')}"
                        for e in data.get("education", [])
                    ),
                    "skills": " | ".join(data.get("skills", [])),
                    "certifications": " | ".join(
                        c.get("name", "") for c in data.get("certifications", [])
                    ),
                    "languages": " | ".join(data.get("languages", [])),
                    "email": data.get("email", ""),
                    "website": data.get("website", ""),
                    "phone": data.get("phone", ""),
                    "profile_url": row["profile_url"],
                    "extracted_at": row["extracted_at"],
                    "confidence_score": row["confidence_score"],
                }
                writer.writerow(flat)

        logger.info("CSV exported to {}", output_path)

    def close(self) -> None:
        self.conn.close()
