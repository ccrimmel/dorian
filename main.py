import os
import threading
from urllib.parse import urlencode
import requests
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google import genai
import json
import asyncio
import uvicorn

load_dotenv()
app = FastAPI()

# DISCORD
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# SPOTIFY
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPE = "user-top-read user-read-recently-played user-read-currently-playing"

# GEMINI
GEMINI_API_KEY = os.getenv("GEN_AI_API_KEY")
GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)

# MISC
user_tokens = {}
DORIAN_GREEN = 0x1ED760
COULDNT_REFRESH = "Couldn't refresh your Spotify token.\nTry reconnecting with **/connect**."

# SPOTIFY TOKEN REFRESH
async def refresh_spotify_token(user_id):
	# look up stored tokens
	tokens = user_tokens.get(user_id)
	if not tokens:
		return None

	refresh_token = tokens["refresh_token"]

	# call token
	token_url = "https://accounts.spotify.com/api/token"
	data = {
		"grant_type": "refresh_token",
		"refresh_token": refresh_token,
		"client_id": SPOTIFY_CLIENT_ID,
		"client_secret": SPOTIFY_CLIENT_SECRET,
	}
	
	# request to exchange token
	response = await asyncio.to_thread(requests.post, token_url, data=data)

	# error
	if response.status_code != 200:
		print("Failed to refresh token:", response.text)
		return None

	new_tokens = response.json()

	tokens["access_token"] = new_tokens["access_token"]
	tokens["expires_in"] = new_tokens.get("expires_in", tokens["expires_in"])

	# store if new token
	if "refresh_token" in new_tokens:
		tokens["refresh_token"] = new_tokens["refresh_token"]

	return tokens

# SPOTIFY REQUEST + REFRESH
async def spotify_get(interaction, user_id, url):
	tokens = user_tokens.get(user_id)
	if tokens is None:
		await interaction.edit_original_response(embed=embed_connect())
		return None

	headers = {"Authorization": f"Bearer {tokens['access_token']}"}
	
	# run in thread
	def do_request(u, h):
		return requests.get(u, headers=h, timeout=10)
	
	# 1st request
	response = await asyncio.to_thread(do_request, url, headers)

	# refresh
	if response.status_code == 401:
		tokens = await refresh_spotify_token(user_id)

		if tokens is None:
			await interaction.edit_original_response(embed=embed_error(COULDNT_REFRESH))
			return None

		headers = {"Authorization": f"Bearer {tokens['access_token']}"}
		response = requests.get(url, headers=headers)

		# retry
		response = await asyncio.to_thread(do_request, url, headers)

		if response.status_code != 200:
			await interaction.edit_original_response(embed=embed_error(COULDNT_REFRESH))
			return None

	# for nowplaying
	elif response.status_code == 204:
		await interaction.edit_original_response(
			embed=embed_error(f"{interaction.user.display_name} isn't playing anything.")
		)
		return None

	# any other error
	elif response.status_code != 200:
		await interaction.edit_original_response(
			embed=embed_error(f"Spotify returned an error ({response.status_code}).")
		)
		return None

	return response

# EMBED TEMPLATES
def embed_connect():
	# not connected
	return discord.Embed(
		title="Connect your Spotify account!",
		description="Your account isn't connected to **Dorian** yet.\nRun **/connect**.",
		color=DORIAN_GREEN
	)

def embed_error(message: str):
	# error, write description
	return discord.Embed(
		title="Error!",
		description=message,
		color=DORIAN_GREEN
	)

# TIMESTAMPS, NOWPLAYING
def ms_to_timestamp(ms):
	# convert milliseconds to mm:ss
	seconds = ms // 1000
	minutes = seconds // 60
	seconds = seconds % 60
	return f"{minutes}:{seconds:02d}"

# ON READY
@bot.event
async def on_ready():
	# sync commands to test server if guild id is set
	if GUILD_ID:
		guild = discord.Object(id=int(GUILD_ID))
		await bot.tree.sync(guild=guild)
		print(f"Slash commands synced to test server ({GUILD_ID}).")
	else:
		# sync commands globally
		await bot.tree.sync()
		print("No GUILD_ID found, commands synced globally.")

	print(f"Logged in as {bot.user}.")

# SPOTIFY OAUTH
@app.get("/callback/spotify")
async def spotify_callback(request: Request):
	# read parameters
	code = request.query_params.get("code")
	error = request.query_params.get("error")
	user_id = request.query_params.get("state")

	print("User ID:", user_id)
	print("Authorization Code:", code)
	print("Error:", error)

	if error:
		return f"Spotify authorization failed: {error}"
		
	token_url = "https://accounts.spotify.com/api/token"

	data = {
		"grant_type": "authorization_code",
		"code": code,
		"redirect_uri": SPOTIFY_REDIRECT_URI,
		"client_id": SPOTIFY_CLIENT_ID,
		"client_secret": SPOTIFY_CLIENT_SECRET,
	}

	response = await asyncio.to_thread(requests.post, token_url, data=data)

	# error
	if response.status_code != 200:
		return f"Failed to exchange code: {response.text}"

	token_info = response.json()

	# parse token info
	access_token = token_info["access_token"]
	refresh_token = token_info["refresh_token"]
	expires_in = token_info["expires_in"]

	# store tokens w/ user id
	if user_id:
		user_tokens[user_id] = {
			"access_token": access_token,
			"refresh_token": refresh_token,
			"expires_in": expires_in,
		}
		return "Spotify connected! You can close this tab."

# /CONNECT: START SPOTIFY LOGIN
@bot.tree.command(name="connect", description="Connect your Spotify account.")
async def connect(interaction: discord.Interaction):
	await interaction.response.defer(ephemeral=True)

	user_id = str(interaction.user.id)
	tokens = await refresh_spotify_token(user_id)

	parameters = {
		"response_type": "code",
		"client_id": SPOTIFY_CLIENT_ID,
		"scope": SPOTIFY_SCOPE,
		"redirect_uri": SPOTIFY_REDIRECT_URI,
		"state": str(interaction.user.id)
	}

	# build url
	auth_url = "https://accounts.spotify.com/authorize?" + urlencode(parameters)

	# create embed
	if tokens is not None:
		embed = discord.Embed(
			title="Connect your Spotify account!",
			description=(
				"Your account is already connected to **Dorian**.\n"
				f"If something isn't working you can reconnect [here]({auth_url})."
			),
			color=DORIAN_GREEN
		)
	else:
		embed = discord.Embed(
			title="Connect your Spotify account!",
			description=f"Your account isn't connected to **Dorian** yet.\n\n[Log in]({auth_url})",
			color=DORIAN_GREEN
		)

	return await interaction.edit_original_response(embed=embed)

# /NOWPLAYING: SHOW CURRENT SPOTIFY TRACK
@bot.tree.command(name="nowplaying", description="Show your current Spotify track.")
async def nowplaying(interaction: discord.Interaction):
	await interaction.response.defer()

	# identify user
	user_id = str(interaction.user.id)
	tokens = await refresh_spotify_token(user_id)

	# account not connected
	if tokens is None:
		return await interaction.edit_original_response(embed=embed_connect())

	# call currently playing
	url = "https://api.spotify.com/v1/me/player/currently-playing"
	response = await spotify_get(interaction, user_id, url)

	if response is None:
		return

	data = response.json()

	# if paused
	if not data.get("is_playing", False):
		embed = discord.Embed(
			title="No song playing!",
			description=f"{interaction.user.display_name}'s music is paused right now.",
			color=DORIAN_GREEN
		)
		return await interaction.edit_original_response(embed=embed)

	# metadata
	song_name = data["item"]["name"]
	artist_name = data["item"]["artists"][0]["name"]
	album_name = data["item"]["album"]["name"]
	album_cover = data["item"]["album"]["images"][0]["url"]
	song_url = data["item"]["external_urls"]["spotify"]
	song_length = data["item"]["duration_ms"]
	progress = data["progress_ms"]

	# convert ms to mm:ss
	current_time = ms_to_timestamp(progress)
	total_time = ms_to_timestamp(song_length)

	# PROGRESS BAR
	bar_length = 25
	# percent of the song that has played
	percent = progress / song_length
	# how many characters should be filled
	filled = int(percent * bar_length)

	bar = "/" * filled + "-" * (bar_length - filled)
	formatted = f"{current_time} {bar} {total_time}"

	# create embed
	embed = discord.Embed(
		title=f"{interaction.user.display_name} is playing:",
		description=f"**[{song_name}]({song_url})**\nby **{artist_name}**\nfrom *{album_name}*",
		color=DORIAN_GREEN
	)

	embed.set_thumbnail(url=album_cover)
	embed.set_footer(text=formatted)

	return await interaction.edit_original_response(embed=embed)

# /TOPTRACKS: SHOW TOP 10 TRACKS FOR SHORT/MED/LONG
@bot.tree.command(name="toptracks", description="Show your top tracks.")
@app_commands.describe(
	time_range="How far back should I look?"
)
@app_commands.choices(
	time_range=[
		app_commands.Choice(name="Short term (4 weeks)", value="short_term"),
		app_commands.Choice(name="Medium term (6 months)", value="medium_term"),
		app_commands.Choice(name="Long term (All time)", value="long_term"),
	]
)
async def toptracks(interaction: discord.Interaction, time_range: app_commands.Choice[str]):
	await interaction.response.defer()

	# identify user
	user_id = str(interaction.user.id)
	tokens = await refresh_spotify_token(user_id)

	# account not connected
	if tokens is None:
		return await interaction.edit_original_response(embed=embed_connect())

	# build url and call tracks
	url = f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range.value}&limit=10"
	response = await spotify_get(interaction, user_id, url)

	if response is None:
		return
	
	data = response.json()

	# build description string
	description = ""

	for i, track in enumerate(data.get("items", []), start=1):
		name = track["name"]
		artist = track["artists"][0]["name"]
		url = track["external_urls"]["spotify"]
		description += f"{i}. **[{name}]({url})** - {artist}\n"

	embed = discord.Embed(
		title=f"{interaction.user.display_name}'s top tracks: {time_range.name}",
		description=description,
		color=DORIAN_GREEN
	)

	return await interaction.edit_original_response(embed=embed)

# /TOPARTISTS: SHOW TOP 10 ARTISTS FOR SHORT/MED/LONG
@bot.tree.command(name="topartists", description="Show your top artists.")
@app_commands.describe(
	time_range="How far back should I look?"
)
@app_commands.choices(
	time_range=[
		app_commands.Choice(name="Short term (4 weeks)", value="short_term"),
		app_commands.Choice(name="Medium term (6 months)", value="medium_term"),
		app_commands.Choice(name="Long term (All time)", value="long_term"),
	]
)
async def topartists(interaction: discord.Interaction, time_range: app_commands.Choice[str]):
	await interaction.response.defer()

	# identify user
	user_id = str(interaction.user.id)
	tokens = await refresh_spotify_token(user_id)

	# account not connected
	if tokens is None:
		return await interaction.edit_original_response(embed=embed_connect())

	# build url and call artists
	url = f"https://api.spotify.com/v1/me/top/artists?time_range={time_range.value}&limit=10"
	response = await spotify_get(interaction, user_id, url)

	if response is None:
		return
	
	data = response.json()

	# build description string
	description = ""

	for i, artist in enumerate(data.get("items", []), start=1):
		name = artist["name"]
		url = artist["external_urls"]["spotify"]
		description += f"{i}. **[{name}]({url})**\n"

	embed = discord.Embed(
		title=f"{interaction.user.display_name}'s top artists: {time_range.name}",
		description=description,
		color=DORIAN_GREEN
	)

	return await interaction.edit_original_response(embed=embed)

# /ANALYZE: GEMINI ANALYZES TOP TRACKS/ARTISTS
@bot.tree.command(name="analyze", description="Get an analysis of your top music.")
@app_commands.describe(
	time_range="How far back should I look?"
)
@app_commands.choices(
	time_range=[
		app_commands.Choice(name="Short term (4 weeks)", value="short_term"),
		app_commands.Choice(name="Medium term (6 months)", value="medium_term"),
		app_commands.Choice(name="Long term (All time)", value="long_term"),
	]
)
async def analyze(interaction: discord.Interaction, time_range: app_commands.Choice[str]):
	await interaction.response.defer()

	# base prompt
	prompt = (
		"You are Dorian, a bright and friendly music bot. "
		"Your tone is kind, with a light touch of humor, but never dramatic, poetic, or exaggerated. "
		"Give a short analysis (1 paragraph, 3-4 sentences. Only output the paragraph.) "
		"of the user's music taste based on their top tracks and artists. "
		"Be extremely analytical, like a scientist, but keep your language simple, concise, "
		"and easy for an average reader (~6th-grade reading level). "
		"Focus on patterns, contradictions, stereotypes, and reasonable assumptions you can make about the user.\n"
		"Top Tracks:\n"
	)

	# identify user
	user_id = str(interaction.user.id)
	tokens = await refresh_spotify_token(user_id)

	# account not connected
	if tokens is None:
		return await interaction.edit_original_response(embed=embed_connect())

	# TOP 20 TRACKS
	tracks_url = f"https://api.spotify.com/v1/me/top/tracks?time_range={time_range.value}&limit=20"
	response = await spotify_get(interaction, user_id, tracks_url)

	if response is None:
		return

	data = response.json()

	for i, track in enumerate(data.get("items", []), start=1):
		name = track["name"]
		artist = track["artists"][0]["name"]
		prompt += f"{i}. {name} — {artist}\n"

	prompt += "\nTop artists:\n"

	# TOP 20 ARTISTS
	artists_url = f"https://api.spotify.com/v1/me/top/artists?time_range={time_range.value}&limit=20"
	response = await spotify_get(interaction, user_id, artists_url)

	if response is None:
		return

	data = response.json()

	for i, artist in enumerate(data.get("items", []), start=1):
		name = artist["name"]
		prompt += f"{i}. {name}\n"

	# send prompt
	gemini_response = GEMINI_CLIENT.models.generate_content(
		model="gemini-2.5-flash",
		contents=prompt
	)

	if gemini_response:
		embed = discord.Embed(
			title=f"{interaction.user.display_name}'s music analysis: {time_range.name}",
			description=gemini_response.text,
			color=DORIAN_GREEN
		)
		return await interaction.edit_original_response(embed=embed)
	
	return await interaction.edit_original_response(
		embed=embed_error("Something went wrong.")
	)

# /RECOMMEND: GEMINI RECOMMENDS SONGS BASED ON TOP ARTISTS
@bot.tree.command(name="recommend", description="Get recommendations based on your top music.")
@app_commands.describe(
	time_range="How far back should I look?"
)
@app_commands.choices(
	time_range=[
		app_commands.Choice(name="Short term (4 weeks)", value="short_term"),
		app_commands.Choice(name="Medium term (6 months)", value="medium_term"),
		app_commands.Choice(name="Long term (All time)", value="long_term"),
	]
)
async def recommend(interaction: discord.Interaction, time_range: app_commands.Choice[str]):
	await interaction.response.defer()

	# base prompt
	prompt = (
		"You are Dorian, a bright and friendly music bot. "
		"Give 3 song recommendations based on the user's top artists. "
		"Deep cuts encouraged! Look for artists outside of the list given."
		"Output ONLY valid JSON: a list of objects with keys 'title', 'artist', and 'reason'.\n "
		"- 'title': the title of a real song\n"
		"- 'artist': the artist who performs it\n"
		"- 'reason': One short, simple, and concise sentence about why you chose said song\n"
		"Do not write any backticks, commentary, markdown, or extra text. Only ouput the JSON list.\n" 
		"Top Artists:\n"
	)

	# identify user
	user_id = str(interaction.user.id)
	tokens = await refresh_spotify_token(user_id)
	
	# account not connected
	if tokens is None:
		return await interaction.edit_original_response(embed=embed_connect())
	
	# TOP 20 ARTISTS
	artists_url = f"https://api.spotify.com/v1/me/top/artists?time_range={time_range.value}&limit=20"
	response = await spotify_get(interaction, user_id, artists_url)

	if response is None:
		return
	
	data = response.json()
	
	for i, artist in enumerate(data.get("items", []), start=1):
		prompt += f"{i}. {artist['name']}\n"
		
	gemini_response = GEMINI_CLIENT.models.generate_content(
		model="gemini-2.5-flash",
		contents=prompt
	)
	
	# parse json
	try:
		recs = json.loads(gemini_response.text)
	except Exception:
		return await interaction.edit_original_response(
			embed=embed_error("I couldn't think of any recommendations. Try again?")
		)
		
	# search spotify
	final_recs = []
	
	for rec in recs:
		title = rec.get("title")
		artist = rec.get("artist")
		reason = rec.get("reason")
		
		# search query
		query = f"{title} {artist}"
		search_url = f"https://api.spotify.com/v1/search?q={query}&type=track&limit=1"
		search_response = await spotify_get(interaction, user_id, search_url)
		results = search_response.json()
		items = results.get("tracks", {}).get("items", [])
		track = items[0]
		
		# get real Spotify metadata
		real_title = track["name"]
		real_artist = track["artists"][0]["name"]
		real_url = track["external_urls"]["spotify"]
		album_cover = track["album"]["images"][0]["url"]
		
		final_recs.append({
			"title": real_title,
			"artist": real_artist,
			"url": real_url,
			"reason": reason,
			"cover": album_cover
		})
	
	# no valid recs
	if not final_recs:
		return await interaction.edit_original_response(
		embed=embed_error("I couldn't think of any recommendations. Try again?")
	)
		
	# build embed
	description = ""
	for i, item in enumerate(final_recs, start=1):
		description += (
			f"{i}. **[{item['title']}]({item['url']})** - {item['artist']}\n"
			f"{item['reason']}\n"
		)
			
	embed = discord.Embed(
		title=f"Recommendations for {interaction.user.display_name}:",
		description=description,
		color=DORIAN_GREEN
    )
	
	# first rec cover as thumbnail
	embed.set_thumbnail(url=final_recs[0]["cover"])
	
	return await interaction.edit_original_response(embed=embed)

# FASTAPI STARTER
# runs the FastAPI in background
def start_web_server():
	uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
	# start server in separate thread
	web_thread = threading.Thread(target=start_web_server, daemon=True)
	web_thread.start()

	# start bot
	bot.run(DISCORD_TOKEN)