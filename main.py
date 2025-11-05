import os
import discord
from discord.ext import commands
from google import genai
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
api_key = os.getenv("GEN_AI_API_KEY")
client = genai.Client(api_key=api_key)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix='/', intents=intents)

prompt = "When was the last time the Cincinnati Reds were at the World Series?"
prompt += "Provide a short one sentence message of hope for Reds fans after your response."

response = client.models.generate_content(
  model="gemini-2.5-flash", 
  contents=prompt
)

if response != None:
  print(response.text)
else:
  print("Error.")

@bot.event
async def on_ready() -> None:
  print(f'We have logged in as {bot.user}.')

bot.run(token)