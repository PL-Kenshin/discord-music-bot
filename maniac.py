import discord
from discord import app_commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)


    queues = {}
    voice_clients = {}
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    async def play_next(guild_id):
        if queues[guild_id]:
            next_song = queues[guild_id].pop(0)
            player = discord.FFmpegOpusAudio(next_song['url'], **ffmpeg_options)
            voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop))
        else:
            await voice_clients[guild_id].disconnect()
            del voice_clients[guild_id]


    @client.event
    async def on_ready():
        print(f'{client.user} is now jamming')

    @tree.command(name="play", description="Dodaj utwór do kolejki lub odtwórz")
    @app_commands.describe(url="Link do utworu (np. YouTube)")
    async def play(interaction: discord.Interaction, url: str):
        guild_id = interaction.guild.id
        user = interaction.user

        if not user.voice or not user.voice.channel:
            await interaction.response.send_message("Musisz być na kanale głosowym!", ephemeral=True)
            return

        await interaction.response.defer()

        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            voice_client = await user.voice.channel.connect()
            voice_clients[guild_id] = voice_client

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        song_url = data['url']
        title = data.get('title', url)

        if guild_id not in queues:
            queues[guild_id] = []

        queues[guild_id].append({'url': song_url, 'title': title})

        if not voice_clients[guild_id].is_playing():
            await play_next(guild_id)
            await interaction.followup.send(f"Odtwarzam: {title}")
        else:
            await interaction.followup.send(f"Dodano do kolejki: {title}")

    @tree.command(name="queue", description="Wyświetl kolejkę")
    async def queue(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in queues and queues[guild_id]:
            queue_list = [f"{idx+1}. {song['title']}" for idx, song in enumerate(queues[guild_id])]
            await interaction.response.send_message("Kolejka:\n" + "\n".join(queue_list))
        else:
            await interaction.response.send_message("Kolejka jest pusta.")

    @tree.command(name="skip", description="Pomiń aktualny utwór")
    async def skip(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in voice_clients and voice_clients[guild_id].is_playing():
            voice_clients[guild_id].stop()
            await interaction.response.send_message("Pominięto utwór.")
        else:
            await interaction.response.send_message("Aktualnie nic nie jest odtwarzane.")

    @tree.command(name="pause", description="Pauzuje odtwarzanie")
    async def pause(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            voice_clients[guild_id].pause()
            await interaction.response.send_message("Pauza.")
        except Exception:
            await interaction.response.send_message("Nie można zapauzować.")

    @tree.command(name="resume", description="Wznawia odtwarzanie")
    async def resume(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            voice_clients[guild_id].resume()
            await interaction.response.send_message("Wznowiono odtwarzanie.")
        except Exception:
            await interaction.response.send_message("Nie można wznowić.")

    @tree.command(name="stop", description="Zatrzymuje i rozłącza bota")
    async def stop(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            voice_clients[guild_id].stop()
            await voice_clients[guild_id].disconnect()
            await interaction.response.send_message("Bot zatrzymany i rozłączony.")
        except Exception:
            await interaction.response.send_message("Nie można zatrzymać bota.")

    @tree.command(name="help", description="Wyświetl dostępne komendy")
    async def help_command(interaction: discord.Interaction):
        help_text = (
            "**Dostępne komendy:**\n"
            "`/play <url>` - Dodaj utwór do kolejki lub odtwórz\n"
            "`/queue` - Wyświetl kolejkę\n"
            "`/skip` - Pomija aktualny utwór\n"
            "`/pause` - Pauzuje odtwarzanie\n"
            "`/resume` - Wznawia odtwarzanie\n"
            "`/stop` - Zatrzymuje i rozłącza bota"
        )
        await interaction.response.send_message(help_text)

    client.run(TOKEN)