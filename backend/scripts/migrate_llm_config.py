"""Create llm_configs table, add llm_config_id to prompts, seed data, and migrate historical prompts.

Usage:
    cd backend
    python scripts/migrate_llm_config.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, SessionLocal
from app.config import LLM_PROVIDERS
from app.models.models import LLMConfig, Prompt


def create_llm_configs_table():
    """Create llm_configs table if it doesn't already exist."""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'llm_configs'"
        ))
        exists = result.scalar() > 0

        if exists:
            print("[migrate] llm_configs table already exists. Skipping.")
            return

        conn.execute(text(
            "CREATE TABLE llm_configs ("
            "  id INTEGER NOT NULL AUTO_INCREMENT,"
            "  user_id INTEGER NULL,"
            "  name VARCHAR(128) NOT NULL,"
            "  base_url VARCHAR(512) NOT NULL,"
            "  api_key VARCHAR(512) NOT NULL,"
            "  models JSON NOT NULL,"
            "  default_model VARCHAR(128) NOT NULL,"
            "  created_at DATETIME NULL,"
            "  updated_at DATETIME NULL,"
            "  PRIMARY KEY (id),"
            "  INDEX ix_llm_configs_user_id (user_id),"
            "  CONSTRAINT fk_llm_configs_user_id"
            "    FOREIGN KEY (user_id) REFERENCES users(id)"
            ")"
        ))
        conn.commit()
        print("[migrate] llm_configs table created successfully.")


def add_llm_config_id_to_prompts():
    """Add llm_config_id column to prompts table if it doesn't already exist."""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'prompts' "
            "AND COLUMN_NAME = 'llm_config_id'"
        ))
        exists = result.scalar() > 0

        if exists:
            print("[migrate] llm_config_id column already exists in prompts table. Skipping.")
            return

        conn.execute(text(
            "ALTER TABLE prompts ADD COLUMN llm_config_id INTEGER NULL,"
            " ADD INDEX ix_prompts_llm_config_id (llm_config_id),"
            " ADD CONSTRAINT fk_prompts_llm_config_id"
            " FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id)"
        ))
        conn.commit()
        print("[migrate] llm_config_id column added to prompts table successfully.")


def seed_llm_configs():
    """Seed llm_configs with dashscope and swust presets from config.py (user_id=NULL, global)."""
    db = SessionLocal()
    try:
        # Check if seed data already exists
        existing_count = db.query(LLMConfig).filter(LLMConfig.user_id == None).count()
        if existing_count > 0:
            print(f"[migrate] {existing_count} global llm_configs already exist. Skipping seed.")
            return

        for provider_name, preset in LLM_PROVIDERS.items():
            config = LLMConfig(
                user_id=None,  # Global shared config
                name=provider_name,
                base_url=preset["base_url"],
                api_key=preset["api_key"],
                models=preset["models"],
                default_model=preset["default_model"],
            )
            db.add(config)
        db.commit()
        print(f"[migrate] Seeded {len(LLM_PROVIDERS)} global llm_configs: {list(LLM_PROVIDERS.keys())}")
    except Exception as e:
        print(f"[migrate] Error seeding llm_configs: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_prompt_llm_config_ids():
    """Migrate historical prompts: match model string against dashscope/swust models lists.

    - If model matches one of dashscope's models, associate with dashscope config
    - If model matches one of swust's models, associate with swust config
    - If model doesn't match either, associate with dashscope (default)
    - If prompt has no model, leave llm_config_id as NULL
    """
    db = SessionLocal()
    try:
        # Get the global config IDs
        configs = db.query(LLMConfig).filter(LLMConfig.user_id == None).all()
        config_map = {}
        for config in configs:
            config_map[config.name] = {
                "id": config.id,
                "models": config.models if isinstance(config.models, list) else [],
            }

        # Default fallback: dashscope
        default_config_id = config_map.get("dashscope", {}).get("id")
        if default_config_id is None and configs:
            default_config_id = configs[0].id

        if not config_map:
            print("[migrate] No global llm_configs found. Cannot migrate prompts.")
            return

        # Find prompts that have a model but no llm_config_id yet
        prompts_to_migrate = (
            db.query(Prompt)
            .filter(Prompt.llm_config_id == None, Prompt.model != None)
            .all()
        )

        if not prompts_to_migrate:
            print("[migrate] No prompts to migrate (all have llm_config_id or no model). Skipping.")
            return

        migrated_count = 0
        for prompt in prompts_to_migrate:
            model_name = prompt.model
            matched_config_id = None

            # Try to match model against each config's models list
            for config_name, config_info in config_map.items():
                if model_name in config_info["models"]:
                    matched_config_id = config_info["id"]
                    break

            # If no match found, fall back to default (dashscope)
            if matched_config_id is None:
                matched_config_id = default_config_id

            prompt.llm_config_id = matched_config_id
            migrated_count += 1

        db.commit()
        print(f"[migrate] Migrated {migrated_count} prompts to llm_config_id associations.")
    except Exception as e:
        print(f"[migrate] Error migrating prompts: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    print("[migrate] Starting LLM config migration...")
    create_llm_configs_table()
    add_llm_config_id_to_prompts()
    seed_llm_configs()
    migrate_prompt_llm_config_ids()
    print("[migrate] Migration complete.")


if __name__ == "__main__":
    main()