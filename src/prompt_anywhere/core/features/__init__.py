"""Feature implementations"""
from prompt_anywhere.core.features.base_feature import BaseFeature
from prompt_anywhere.core.features.google_search_feature import GoogleSearchFeature
from prompt_anywhere.core.features.file_search_feature import FileSearchFeature
from prompt_anywhere.core.features.browser_feature import BrowserFeature
from prompt_anywhere.core.features.terminal_feature import TerminalFeature
from prompt_anywhere.core.features.maximize_chat_feature import MaximizeChatFeature
from prompt_anywhere.core.features.screenshot_feature import ScreenshotFeature
from prompt_anywhere.core.features.history_feature import HistoryFeature
from prompt_anywhere.core.features.customize_feature import CustomizeFeature

__all__ = [
    "BaseFeature",
    "GoogleSearchFeature",
    "FileSearchFeature",
    "BrowserFeature",
    "TerminalFeature",
    "MaximizeChatFeature",
    "ScreenshotFeature",
    "HistoryFeature",
    "CustomizeFeature",
]
