# -*- coding: utf-8 -*-
"""预设主题常量。

每套主题由 id 与中文名称组成；前端据此加载对应的主题 CSS 文件。
"""
from typing import TypedDict


class ThemeItem(TypedDict):
    """主题条目结构。"""

    id: str
    name: str


# 6 套预设主题（id 与 frontend/themes 下的样式文件一一对应）
PRESET_THEMES: list[ThemeItem] = [
    {"id": "light", "name": "明亮"},
    {"id": "dark", "name": "暗夜"},
    {"id": "ocean", "name": "海洋"},
    {"id": "forest", "name": "森林"},
    {"id": "sunset", "name": "日落"},
    {"id": "sakura", "name": "樱花"},
]

# 全部主题 id 集合（用于设置校验 / 回退）
THEME_IDS: list[str] = [item["id"] for item in PRESET_THEMES]
