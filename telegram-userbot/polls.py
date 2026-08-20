"""Polls — create, vote, and get results."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def send_poll(
    client: TelegramClient,
    entity: str | int,
    question: str,
    options: list[str],
    multiple_choice: bool = False,
    quiz: bool = False,
    correct_option: int = None,
) -> dict:
    """Send a poll to a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        question: Poll question
        options: List of option texts (2-10 options)
        multiple_choice: Allow multiple answers
        quiz: Quiz mode (single correct answer)
        correct_option: Index of correct option (for quiz mode, 0-based)
    
    Returns:
        dict with poll info
    """
    answers = [types.PollAnswer(text=o, option=o.encode()) for o in options]
    media = types.InputMediaPoll(
        poll=types.Poll(
            id=0,
            question=question,
            answers=answers,
            multiple_choice=multiple_choice,
            quiz=quiz,
        ),
        correct_answers=[options[correct_option].encode()] if quiz and correct_option is not None else None,
    )
    result = await client.send_message(entity, file=media)
    return {
        "sent": True,
        "id": result.id,
        "question": question,
        "options": options,
    }


async def vote_poll(client: TelegramClient, entity: str | int, message_id: int, options: list[int]) -> dict:
    """Vote in a poll.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID containing the poll
        options: List of option indices to vote for (0-based)
    
    Returns:
        dict with vote status
    """
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not isinstance(msg.media, types.MessageMediaPoll):
        return {"error": "Message is not a poll"}
    
    poll_answers = msg.media.poll.answers
    selected = [poll_answers[i].option for i in options if i < len(poll_answers)]
    
    await client(functions.messages.SendVoteRequest(
        peer=entity,
        msg_id=message_id,
        options=selected,
    ))
    return {"voted": True, "message_id": message_id, "options": options}


async def get_poll_results(client: TelegramClient, entity: str | int, message_id: int) -> dict:
    """Get poll results.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID containing the poll
    
    Returns:
        dict with poll results
    """
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not isinstance(msg.media, types.MessageMediaPoll):
        return {"error": "Message is not a poll"}
    
    poll = msg.media.poll
    results = msg.media.results
    
    options = []
    result_map = {}
    if results.results:
        for r in results.results:
            result_map[r.option.decode()] = r.voters
    
    for ans in poll.answers:
        option_key = ans.option.decode()
        options.append({
            "text": ans.text,
            "voters": result_map.get(option_key, 0),
            "chosen": ans.option in (results.chosen or []),
        })
    
    return {
        "question": poll.question,
        "total_voters": results.total_voters if results.total_voters else 0,
        "options": options,
        "is_quiz": poll.quiz,
        "is_closed": poll.closed if hasattr(poll, "closed") else False,
    }
