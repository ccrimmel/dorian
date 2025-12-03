# Dorian

Dorian is a Discord bot that connects to the Spotify Web API to provide statisics, analysis, recommendations, and (eventually) social features.

## Current Features
* */connect* - OAuth Spotify login  
* */nowplaying* - Show your current track with timestamps + album art 
* */toptracks* - View your top 10 tracks (short/medium/long-term)
* */topartists* - View your top 10 tracks (short/medium/long-term)
* */analyze* - Taste analysis based on your top tracks/artists, Gemini powered
* */recommend* - Three song recommendations based on your top artists, Gemini powered  

## In Progress
I’m working on caching daily Spotify data so it's not hitting the API every time. This will also make starting the social stuff possible.

## Roadmap (rough order)
### 1. Core
* Store user data in local JSON, refreshes daily (tracks, artists, genres, last updated date, etc)
* Rewrite commands to pull from that instead of calling Spotify each time
* */settings* - Show what's stored, change visibility for social/server commands
* */disconnect* - Delete stored data

### 2. Personal
* */topgenres* - View your top 10 genres (short/medium/long-term)
* */profile* - Mini stat card using stored data
* */analyze* - Update: Taste analysis based on playlist
* */export* - Create playlist with *x* top songs from range

### 3. Social
* */compatibility @user* - Shared artists/tracks + similarity %  
* */matchme* - Find 3 most similar users in server (returns their profile?)
* */mix @userA @userB* - Create playlist based on overlap

### 4. Server
* */server topartists* - Server wide top artists (weighted by visibility settings)
* */server toptracks*
* */server topgenres*
* */server stats* - # of connected users, unique artists, superlatives, etc.
* */server recap* - Weekly mini wrapped (manual first, auto later?)

### **5. Misc Ideas**
* */lyrics* - Show current song lyrics 
* */newmusicfriday* - New releases for user 
* */server newmusicfriday* - New releases for server 
* */streak* - Daily listening streak + most active hour
* */whosthat* - Guessing game using anonymous profiles (leaderboard?)

## Credits
Logo image by [Vectorportal.com](https://www.vectorportal.com), [CC BY](https://creativecommons.org/licenses/by/4.0/)