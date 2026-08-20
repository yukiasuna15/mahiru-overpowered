"""
Discord voice module — connect, play audio, pause, resume, stop, disconnect.
Uses discord.py-self.
Requires: ffmpeg installed on system for audio playback.
"""

import discord
from typing import Optional, Union


async def connect_voice(
    channel: Union[discord.VoiceChannel, discord.StageChannel],
) -> discord.VoiceClient:
    """Connect to a voice channel."""
    return await channel.connect()


async def disconnect_voice(voice_client: discord.VoiceClient) -> None:
    """Disconnect from voice."""
    await voice_client.disconnect()


async def play_audio(
    voice_client: discord.VoiceClient,
    source: str,
    volume: float = 0.5,
) -> None:
    """Play audio from file path or URL. Requires ffmpeg."""
    audio = discord.FFmpegPCMAudio(source)
    transformed = discord.PCMVolumeTransformer(audio, volume=volume)
    voice_client.play(transformed)


async def pause_audio(voice_client: discord.VoiceClient) -> None:
    """Pause audio playback."""
    voice_client.pause()


async def resume_audio(voice_client: discord.VoiceClient) -> None:
    """Resume audio playback."""
    voice_client.resume()


async def stop_audio(voice_client: discord.VoiceClient) -> None:
    """Stop audio playback."""
    voice_client.stop()


async def set_volume(voice_client: discord.VoiceClient, volume: float) -> None:
    """Set volume (0.0 to 1.0). Only works with PCMVolumeTransformer source."""
    if voice_client.source and isinstance(voice_client.source, discord.PCMVolumeTransformer):
        voice_client.source.volume = volume


async def move_to(voice_client: discord.VoiceClient, channel: discord.VoiceChannel) -> None:
    """Move to another voice channel."""
    await voice_client.move_to(channel)


async def is_playing(voice_client: discord.VoiceClient) -> bool:
    """Check if audio is playing."""
    return voice_client.is_playing()


async def is_paused(voice_client: discord.VoiceClient) -> bool:
    """Check if audio is paused."""
    return voice_client.is_paused()


async def is_connected(voice_client: discord.VoiceClient) -> bool:
    """Check if connected to voice."""
    return voice_client.is_connected()


async def get_voice_channels(guild: discord.Guild) -> list:
    """List all voice channels in a guild."""
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "bitrate": c.bitrate,
            "user_limit": c.user_limit,
            "members": [m.name for m in c.members],
        }
        for c in guild.voice_channels
    ]


async def get_stage_channels(guild: discord.Guild) -> list:
    """List all stage channels in a guild."""
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "members": [m.name for m in c.members],
        }
        for c in guild.stage_channels
    ]
