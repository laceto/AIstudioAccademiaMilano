import os
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    max_tokens=400,
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

SYSTEM = """You are a mindful pause coach embedded in a Telegram bot.
Users come to you mid-activation — stressed, reactive, running on autopilot.
Your role: interrupt the automatic response, open the space of possibilities, support a conscious choice.

Rules:
- SHORT responses only. Max 5 lines. Activated people cannot read long text.
- Warm, direct, non-preachy. A calm friend, not a therapist.
- Respond in the same language the user writes in.
- Use line breaks. No paragraphs."""

pause_chain = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", """The user is in autopilot mode. Their trigger:
"{trigger}"

Write a brief pause guide in 3 short lines:
1. A grounding action (breath, body, sensation — 1 line)
2. A permission to stop (1 line)
3. Bridge line: "Now let's look at your options →"

Max 4 lines total. Simple language. No bullet points."""),
]) | llm

options_chain = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", """Situation: "{trigger}"

Give exactly 3 response options — concrete, short, varied in approach:
• 1: direct/immediate action
• 2: pause/delay/create space
• 3: unexpected or creative action

Format exactly like this (no extra text before):
1️⃣ [max 8 words]
2️⃣ [max 8 words]
3️⃣ [max 8 words]

Last line: _Reply 1, 2, 3 — or describe your own._"""),
]) | llm

reflection_chain = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", """User chose: "{choice}"
Situation was: "{trigger}"

Ask ONE reflection question to help them own this choice.
One sentence only. Conversational. End with a question mark."""),
]) | llm

close_chain = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", """Session:
- Trigger: {trigger}
- Choice made: {choice}
- Reflection: {reflection}

Write exactly 2 lines:
1. Acknowledge they just broke autopilot and made a real choice
2. One forward-looking sentence

Then: "Session saved. 🌱"

Max 3 lines total."""),
]) | llm
