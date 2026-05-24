"""
Slash commands:
  /ask <question>     — Claude answers in AI Studio persona
  /weather            — current weather in Milan
  /latest             — most recent AI Studio deliverable
  /help               — list all commands
"""

import os
import requests
import discord
from discord import app_commands
from discord.ext import commands
from ai_chat import reply

WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
WEATHER_ICONS = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
    "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Fog": "🌫️", "Haze": "🌫️",
}

DELIVERABLES = [
    {"id": "012", "name": "Discord Bot",                     "date": "2026-05-24", "price": "€19.90"},
    {"id": "011", "name": "Milan Weather Dashboard",          "date": "2026-05-24", "price": "€9.90"},
    {"id": "010", "name": "Profile Setup & Publishing",       "date": "2026-05-23", "price": "€14.90"},
    {"id": "009", "name": "LinkedIn Post Generator",          "date": "2026-05-23", "price": "€4.90"},
    {"id": "008", "name": "Algo Trading Bot (Alpaca)",        "date": "2026-05-23", "price": "€24.90"},
    {"id": "007", "name": "WhatsApp → Calendar Sync",         "date": "2026-05-23", "price": "€14.90"},
    {"id": "006", "name": "RAG Knowledge Base",               "date": "2026-05-23", "price": "€29.90"},
    {"id": "005", "name": "Streamlit Chatbot (OpenAI)",       "date": "2026-05-23", "price": "€19.90"},
]


def _get_weather() -> str:
    api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
    if not api_key:
        return "⚠️ OPENWEATHERMAP_API_KEY not set."
    try:
        r = requests.get(
            WEATHER_API_URL,
            params={"q": "Milan,IT", "units": "metric", "appid": api_key},
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()
        main = d["main"]
        wind = d["wind"]
        desc = d["weather"][0]
        icon = WEATHER_ICONS.get(desc["main"], "🌡️")
        return (
            f"{icon} **Milan** — {desc['description'].capitalize()}\n"
            f"🌡️ {main['temp']:.1f}°C (feels {main['feels_like']:.1f}°C)\n"
            f"💧 Humidity: {main['humidity']}%   💨 Wind: {wind['speed']} m/s\n"
            f"↕️ {main['temp_min']:.1f}°C / {main['temp_max']:.1f}°C"
        )
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "⚠️ Invalid OpenWeatherMap API key."
        return f"⚠️ Weather API error: {e}"
    except Exception as e:
        return f"⚠️ {e}"


def setup_commands(bot: commands.Bot):

    @bot.tree.command(name="ask", description="Ask AI Studio anything")
    @app_commands.describe(question="Your question")
    async def ask(interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        answer = await reply(question)
        await interaction.followup.send(answer)

    @bot.tree.command(name="weather", description="Current weather in Milan")
    async def weather(interaction: discord.Interaction):
        await interaction.response.defer()
        result = _get_weather()
        await interaction.followup.send(result)

    @bot.tree.command(name="latest", description="Latest AI Studio deliverable")
    async def latest(interaction: discord.Interaction):
        d = DELIVERABLES[0]
        embed = discord.Embed(
            title=f"🚀 Latest: #{d['id']} — {d['name']}",
            description=f"Shipped {d['date']}  ·  {d['price']}",
            color=0x5865F2,
        )
        embed.set_footer(text="AI Studio Accademia Milano · github.com/laceto/AIstudioAccademiaMilano")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="deliverables", description="All AI Studio deliverables")
    async def deliverables(interaction: discord.Interaction):
        embed = discord.Embed(
            title="📦 AI Studio Deliverables",
            color=0x5865F2,
        )
        for d in DELIVERABLES:
            embed.add_field(
                name=f"#{d['id']} — {d['name']}",
                value=f"{d['date']}  ·  {d['price']}",
                inline=False,
            )
        embed.set_footer(text="Want something built? DM this bot or contact Luigi.")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="help", description="Show all available commands")
    async def help_cmd(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 AI Studio Bot — Commands",
            color=0x5865F2,
        )
        embed.add_field(name="/ask <question>",    value="Ask AI Studio anything (Claude-powered)", inline=False)
        embed.add_field(name="/weather",           value="Current weather in Milan", inline=False)
        embed.add_field(name="/latest",            value="Latest deliverable shipped", inline=False)
        embed.add_field(name="/deliverables",      value="Full list of deliverables", inline=False)
        embed.add_field(name="@mention or DM",     value="Chat directly with the AI Studio assistant", inline=False)
        embed.set_footer(text="AI Studio Accademia Milano")
        await interaction.response.send_message(embed=embed)
