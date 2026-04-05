"""Quick test: run the new prompt against 5 sample words."""
from __future__ import annotations

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

SYSTEM_PROMPT = """\
You are a vocabulary assistant for a B1-B2 English learner. Your task is to explain English words clearly and simply, using only common everyday English in your explanations.

Output has 4 lines. Follow the format exactly, no extra lines or labels.

LINE 1 — Definition:
Use the word itself inside a natural sentence pattern that shows how it works in speech.
NOT "X means Y". Instead, a real phrase: "When you **elaborate** on something, you give more details about it", "If you are **reluctant** to do something, you don't really want to do it".
This shows the learner the part of speech, grammar, and how the word fits in real sentences.
Bold the target word using **bold**.
Must match the SPECIFIC meaning used in the given context, not a general one.

LINE 2 — Context explanation:
Explain what is happening in the given context in simple words.
Rephrase the situation: what is happening, why, what it feels like.
Imagine explaining the sentence to a friend who doesn't know this word.
NEVER evaluate how well the word fits. No "this word fits perfectly", "this perfectly captures", "this is a great example of".

LINE 3 — 🇷🇺 <short Russian translation, 1-3 words>
Short, natural — not a dictionary entry.

LINE 4 — 📋 <2-3 English synonyms or short phrases>
Only for the specific meaning used in context.\
"""

USER_TEMPLATE = 'Word: "{lemma}" ({pos})\nContext: "{context}"'

SAMPLES: list[dict[str, str]] = [
    {"lemma": "elaborate", "pos": "VERB", "context": "She refused to elaborate on her plans."},
    {"lemma": "reluctant", "pos": "ADJ", "context": "He was reluctant to share his opinion with the group."},
    {"lemma": "stumble", "pos": "VERB", "context": "I stumbled upon an interesting article about space."},
    {"lemma": "subtle", "pos": "ADJ", "context": "There was a subtle difference between the two paintings."},
    {"lemma": "compromise", "pos": "NOUN", "context": "They reached a compromise after hours of discussion."},
]


async def generate(lemma: str, pos: str, context: str) -> str:
    user_prompt = USER_TEMPLATE.format(lemma=lemma, pos=pos, context=context)
    options = ClaudeAgentOptions(
        model="claude-haiku-4-5-20251001",
        system_prompt=SYSTEM_PROMPT,
        max_turns=1,
    )
    parts: list[str] = []
    async for message in query(prompt=user_prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
    return " ".join(parts).strip()


async def main() -> None:
    for sample in SAMPLES:
        print(f"\n{'='*60}")
        print(f"📖  {sample['lemma']}  —  \"{sample['context']}\"")
        print(f"{'='*60}")
        result = await generate(sample["lemma"], sample["pos"], sample["context"])
        print(result)
        print()


if __name__ == "__main__":
    asyncio.run(main())
