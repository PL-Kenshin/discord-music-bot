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

    last_text_channel = {}
    queues = {}
    voice_clients = {}
    yt_dl_options = {"format": "bestaudio/best", "noplaylist": True}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    AUTHOR_ID = 430079534201569280

    async def get_author_avatar(client):
        user = await client.fetch_user(AUTHOR_ID)
        return user.display_avatar.url

    async def play_next(guild_id):
        if queues[guild_id]:
            next_song = queues[guild_id].pop(0)
            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(next_song['webpage_url'], download=False))
                song_url = data.get('url')
                title = data.get('title', next_song.get('title', 'Nieznany tytuł'))
                thumbnail = data.get('thumbnail')
                if not song_url:
                    print(f"Nie udało się pobrać streamu dla: {title}")
                    await play_next(guild_id)
                    return
                player = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)
                voice_clients[guild_id].play(
                    player,
                    after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop)
                )
                print(f"Odtwarzam: {title}")
                if guild_id in last_text_channel:
                    avatar_url = await get_author_avatar(client)
                    embed = discord.Embed(
                        description=f"Odtwarzam teraz: **{title}**",
                        color=discord.Color.green()
                    )
                    if thumbnail:
                        embed.set_thumbnail(url=thumbnail)
                    embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
                    await last_text_channel[guild_id].send(embed=embed)
            except Exception as e:
                print(f"Błąd podczas odtwarzania: {e}")
                await play_next(guild_id)
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
        avatar_url = await get_author_avatar(client)

        if not user.voice or not user.voice.channel:
            embed = discord.Embed(
                description="Musisz być na kanale głosowym!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
            voice_client = await user.voice.channel.connect()
            voice_clients[guild_id] = voice_client
            
        last_text_channel[guild_id] = interaction.channel
        loop = asyncio.get_event_loop()
        try:
            # Najpierw spróbuj pobrać tylko "flat" dane (bez streamów)
            flat_options = yt_dl_options.copy()
            flat_options["extract_flat"] = True
            ytdl_flat = yt_dlp.YoutubeDL(flat_options)
            data = await loop.run_in_executor(None, lambda: ytdl_flat.extract_info(url, download=False))
            if guild_id not in queues:
                queues[guild_id] = []

            # Jeśli playlista (flat)
            if 'entries' in data and data['entries']:
                added_titles = []
                for entry in data['entries']:
                    if entry is None:
                        continue
                    queues[guild_id].append({'webpage_url': entry.get('url') or entry.get('webpage_url'), 'title': entry.get('title', 'Nieznany tytuł')})
                    added_titles.append(entry.get('title', 'Nieznany tytuł'))
                msg = f"Dodano do kolejki {len(added_titles)} utworów z playlisty."
                if not voice_clients[guild_id].is_playing():
                    await play_next(guild_id)
                    msg += f"\nOdtwarzam: {added_titles[0]}"
                embed = discord.Embed(description=msg, color=discord.Color.green())
                embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
                await interaction.followup.send(embed=embed)
                return

            # Jeśli pojedynczy utwór (nie playlista)
            # Pobierz pełne dane o utworze
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            queues[guild_id].append({'webpage_url': data.get('webpage_url', url), 'title': data.get('title', url)})

            if not voice_clients[guild_id].is_playing():
                await play_next(guild_id)
                embed = discord.Embed(description=f"Odtwarzam: {data.get('title', url)}", color=discord.Color.green())
                embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(description=f"Dodano do kolejki: {data.get('title', url)}", color=discord.Color.green())
                embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
                await interaction.followup.send(embed=embed)

        except Exception:
            embed = discord.Embed(
                description="Nie udało się pobrać informacji o utworze. Sprawdź, czy link jest poprawny.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    @tree.command(name="queue", description="Wyświetl kolejkę")
    async def queue(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        avatar_url = await get_author_avatar(client)
        if guild_id in queues and queues[guild_id]:
            queue_list = [f"{idx+1}. {song['title']}" for idx, song in enumerate(queues[guild_id])]
            embed = discord.Embed(
                title="Kolejka",
                description="\n".join(queue_list),
                color=discord.Color.blue()
            )
            embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                description="Kolejka jest pusta.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
            await interaction.response.send_message(embed=embed)

    @tree.command(name="skip", description="Pomiń aktualny utwór")
    async def skip(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        avatar_url = await get_author_avatar(client)
        if guild_id in voice_clients and voice_clients[guild_id].is_playing():
            voice_clients[guild_id].stop()
            embed = discord.Embed(
                description="Pominięto utwór.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                description="Aktualnie nic nie jest odtwarzane.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Autor: Kenshin4991", icon_url=avatar_url)
            await interaction.response.send_message(embed=embed)

    @tree.command(name="pause", description="Pauzuje odtwarzanie")
    async def pause(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            voice_clients[guild_id].pause()
            embed = discord.Embed(
                description="Pauza.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed)
        except Exception:
            embed = discord.Embed(
                description="Nie można zapauzować.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed)

    @tree.command(name="resume", description="Wznawia odtwarzanie")
    async def resume(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            voice_clients[guild_id].resume()
            embed = discord.Embed(
                description="Wznowiono odtwarzanie.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed)
        except Exception:
            embed = discord.Embed(
                description="Nie można wznowić.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed)

    @tree.command(name="stop", description="Zatrzymuje i rozłącza bota")
    async def stop(interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            voice_clients[guild_id].stop()
            await voice_clients[guild_id].disconnect()
            embed = discord.Embed(
                description="Bot zatrzymany i rozłączony.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed)
        except Exception:
            embed = discord.Embed(
                description="Nie można zatrzymać bota.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Autor: Kenshin4991")
            await interaction.response.send_message(embed=embed)

    @tree.command(name="help", description="Wyświetl dostępne komendy")
    async def help_command(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pomoc - Komendy muzycznego bota",
            description=(
                "**Dostępne komendy:**\n"
                "`/play <url>` - Dodaj utwór do kolejki lub odtwórz\n"
                "`/queue` - Wyświetl kolejkę\n"
                "`/skip` - Pomija aktualny utwór\n"
                "`/pause` - Pauzuje odtwarzanie\n"
                "`/resume` - Wznawia odtwarzanie\n"
                "`/stop` - Zatrzymuje i rozłącza bota"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Autor: Kenshin4991")
        await interaction.response.send_message(embed=embed)

    client.run(TOKEN)