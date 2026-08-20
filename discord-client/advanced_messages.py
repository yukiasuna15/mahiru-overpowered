"""
Discord advanced messages module — forward, publish, ack, polls, attachments.
Uses discord.py-self.
"""

import discord
from typing import Optional, List, Union


async def forward_message(
    message: discord.Message,
    channel: Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel],
) -> discord.Message:
    """Forward a message to another channel."""
    return await message.forward(channel)


async def publish_message(message: discord.Message) -> None:
    """Publish a message in an announcement channel."""
    await message.publish()


async def mark_read(message: discord.Message) -> None:
    """Mark a message as read (ack)."""
    await message.ack()


async def mark_unread(message: discord.Message) -> None:
    """Mark a message as unread (unack)."""
    await message.unack()


async def bulk_ack(client: discord.Client, channel_ids: List[int]) -> None:
    """Bulk mark multiple channels as read."""
    await client.bulk_ack(channel_ids)


async def delete_recent_mention(client: discord.Client, message_id: int) -> None:
    """Remove a message from recent mentions."""
    await client.delete_recent_mention(message_id)


async def get_recent_mentions(
    client: discord.Client,
    limit: int = 25,
    roles: bool = True,
    everyone: bool = True,
) -> List[dict]:
    """Get recent mentions of the current user."""
    mentions = await client.recent_mentions(limit=limit, roles=roles, everyone=everyone)
    return [
        {
            "id": str(m.id),
            "content": m.content[:100] if m.content else "",
            "author": m.author.name if m.author else None,
            "channel_id": str(m.channel.id) if m.channel else None,
            "guild_id": str(m.guild.id) if m.guild else None,
        }
        for m in mentions
    ]


# === Polls ===

async def vote_poll(message: discord.Message, answer_id: int) -> None:
    """Vote on a poll."""
    poll = message.poll
    if not poll:
        raise ValueError("Message is not a poll")
    answer = poll.get_answer(answer_id)
    await answer.add_vote()


async def remove_poll_vote(message: discord.Message, answer_id: int) -> None:
    """Remove vote from a poll."""
    poll = message.poll
    if not poll:
        raise ValueError("Message is not a poll")
    answer = poll.get_answer(answer_id)
    await answer.remove_vote()


async def end_poll(message: discord.Message) -> None:
    """End a poll early."""
    await message.end_poll()


async def get_poll_results(message: discord.Message) -> Optional[dict]:
    """Get poll results."""
    poll = message.poll
    if not poll:
        return None
    return {
        "question": poll.question.text if poll.question else None,
        "answers": [
            {
                "id": a.id,
                "text": a.text if hasattr(a, "text") else str(a),
                "vote_count": a.vote_count,
                "is_correct": a.is_correct if hasattr(a, "is_correct") else None,
            }
            for a in poll.answers
        ],
        "total_votes": poll.total_votes,
        "is_finalized": poll.is_finalised(),
    }


# === Attachments ===

async def add_files_to_message(
    message: discord.Message,
    files: List[discord.File],
) -> None:
    """Add files to an existing message."""
    await message.add_files(*files)


async def remove_attachments(message: discord.Message) -> None:
    """Remove all attachments from a message."""
    await message.remove_attachments()


async def download_attachment(attachment: discord.Attachment, path: str) -> None:
    """Download an attachment to a file."""
    await attachment.save(path)


async def read_attachment(attachment: discord.Attachment) -> bytes:
    """Read attachment data into memory."""
    return await attachment.read()


# === Thread from message ===

async def create_thread(
    message: discord.Message,
    name: str,
    auto_archive_duration: int = 1440,
    slowmode_delay: int = 0,
) -> discord.Thread:
    """Create a thread from a message."""
    return await message.create_thread(
        name=name,
        auto_archive_duration=auto_archive_duration,
        slowmode_delay=slowmode_delay,
    )
