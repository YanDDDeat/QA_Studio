"""系统配置持久化 — 读写 JSON 文件。"""

import json
import os
import logging

logger = logging.getLogger("qa_studio.system_config")

# 配置文件路径：backend/data/system_config.json
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "system_config.json")


def _ensure_dir():
    os.makedirs(_CONFIG_DIR, exist_ok=True)


def load_config() -> dict:
    """读取系统配置，文件不存在返回空 dict。"""
    if not os.path.exists(_CONFIG_FILE):
        return {}
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("读取系统配置失败: %s", e)
        return {}


def save_config(config: dict):
    """写入系统配置。"""
    _ensure_dir()
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_value(key: str, default=None):
    """获取单个配置项。"""
    return load_config().get(key, default)


def set_value(key: str, value):
    """设置单个配置项。"""
    config = load_config()
    config[key] = value
    save_config(config)
