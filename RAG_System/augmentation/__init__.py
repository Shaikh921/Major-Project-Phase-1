"""
Augmentation module for CloudOps Intel RAG System.
"""

from .context_builder import ContextBuilder, AugmentedPrompt
from .prompt_templates import SYSTEM_SRE_PROMPT, build_user_prompt

__all__ = ["ContextBuilder", "AugmentedPrompt", "SYSTEM_SRE_PROMPT", "build_user_prompt"]
