import os
import discord
from discord.ext import commands
from google import genai
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
guild_id = os.getenv("GUILD_ID")
api_key = os.getenv("GEN_AI_API_KEY")
client = genai.Client(api_key=api_key)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        await bot.tree.sync(guild=guild)
        print(f"Slash commands synced to test server ({guild_id}).")
    else:
        await bot.tree.sync()
        print("No GUILD_ID found, commands synced globally.")
    print(f"Logged in as {bot.user}.")

@bot.tree.command(name="alarm", description="Check if Dorian is awake.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("I'm up! Time to seize the day! ☀️")

@bot.tree.command(name="reds", description="Test Gemini connection.")
async def reds(interaction: discord.Interaction):
  await interaction.response.defer()

  prompt = "When was the last time the Cincinnati Reds were at the World Series? Provide a short one sentence message of hope for Reds fans hoping they'll make it this season after your response."

  response = client.models.generate_content(
    model="gemini-2.5-flash", 
    contents=prompt
  )

  if response:
    await interaction.edit_original_response(content=response.text)
  else:
    await interaction.edit_original_response(content="Something went wrong.")

bot.run(token)