"""
LLM text processing for rewording, translation, and formatting.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .client import get_client


class ProcessingMode(Enum):
    """Built-in text processing modes."""
    
    NORMAL = "normal"
    FORMAL = "formal"
    TRANSLATE = "translate"
    STRUCTURE = "structure"
    SUMMARIZE = "summarize"


@dataclass
class CustomMode:
    """User-defined custom processing mode."""
    
    name: str
    prompt: str
    
    def __str__(self) -> str:
        return self.name


# System prompts for each mode
MODE_PROMPTS = {
    ProcessingMode.FORMAL: (
        "You are a professional writing assistant. "
        "Rewrite the following text to be more professional, clear, and polished. "
        "Maintain the original meaning but improve clarity and tone. "
        "Only output the rewritten text, nothing else."
    ),
    ProcessingMode.TRANSLATE: (
        "You are a professional translator. "
        "Translate the following text to {target_language}. "
        "Maintain the original meaning, tone, and style as much as possible. "
        "Only output the translated text, nothing else."
    ),
    ProcessingMode.STRUCTURE: (
        "You are a professional editor. "
        "Restructure the following text into clear, concise bullet points. "
        "Organize the information logically and make it easy to scan. "
        "Use proper hierarchy if needed. Only output the structured text, nothing else."
    ),
    ProcessingMode.SUMMARIZE: (
        "You are a professional summarizer. "
        "Condense the following text to its key points. "
        "Be concise but preserve all important information. "
        "Only output the summary, nothing else."
    ),
}

# Common languages for translation
LANGUAGES = [
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Dutch",
    "Russian",
    "Chinese",
    "Japanese",
    "Korean",
    "Arabic",
]

DEFAULT_TARGET_LANGUAGE = "English"


def process_text(
    text: str,
    mode: ProcessingMode | CustomMode,
    target_language: str = DEFAULT_TARGET_LANGUAGE,
) -> str:
    """
    Process text through LLM based on the selected mode.
    
    Args:
        text: Input text to process
        mode: Processing mode (built-in or custom)
        target_language: Target language for translation mode
        
    Returns:
        Processed text
    """
    # Normal mode is pass-through (no LLM call)
    if mode == ProcessingMode.NORMAL:
        return text
    
    # Get the appropriate prompt
    if isinstance(mode, CustomMode):
        system_prompt = mode.prompt
    else:
        system_prompt = MODE_PROMPTS.get(mode, "")
        if mode == ProcessingMode.TRANSLATE:
            system_prompt = system_prompt.format(target_language=target_language)
    
    if not system_prompt:
        return text
    
    # Call the LLM
    client = get_client()
    
    response = client.client.chat.completions.create(
        model=client.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    
    result = response.choices[0].message.content
    return result.strip() if result else text


async def process_text_async(
    text: str,
    mode: ProcessingMode | CustomMode,
    target_language: str = DEFAULT_TARGET_LANGUAGE,
) -> str:
    """
    Async version of process_text for non-blocking UI.
    
    Args:
        text: Input text to process
        mode: Processing mode (built-in or custom)
        target_language: Target language for translation mode
        
    Returns:
        Processed text
    """
    # For now, just call the sync version
    # TODO: Use async OpenAI client when needed
    return process_text(text, mode, target_language)


def get_mode_display_name(mode: ProcessingMode | CustomMode) -> str:
    """Get human-readable name for a mode."""
    if isinstance(mode, CustomMode):
        return mode.name
    
    return {
        ProcessingMode.NORMAL: "Normal",
        ProcessingMode.FORMAL: "Formal",
        ProcessingMode.TRANSLATE: "Translate",
        ProcessingMode.STRUCTURE: "Structure",
        ProcessingMode.SUMMARIZE: "Summarize",
    }.get(mode, mode.value.title())


def get_all_modes(custom_modes: Optional[list[CustomMode]] = None) -> list[ProcessingMode | CustomMode]:
    """
    Get all available modes (built-in + custom).
    
    Args:
        custom_modes: List of user-defined custom modes
        
    Returns:
        List of all modes in cycle order
    """
    modes: list[ProcessingMode | CustomMode] = [
        ProcessingMode.NORMAL,
        ProcessingMode.FORMAL,
        ProcessingMode.TRANSLATE,
        ProcessingMode.STRUCTURE,
        ProcessingMode.SUMMARIZE,
    ]
    
    if custom_modes:
        modes.extend(custom_modes)
    
    return modes
