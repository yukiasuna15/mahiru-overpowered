"""Event handlers for real-time Telegram updates."""

from telethon import TelegramClient, events
from telethon.tl import types


def setup_handlers(client: TelegramClient) -> dict:
    """Set up all event handlers on a client.
    
    Args:
        client: Authenticated Telethon client with event loop running
    
    Returns:
        dict with handler count info
    """
    handlers = []

    @client.on(events.NewMessage)
    async def on_message(event):
        """Handle new messages.
        
        Fires for every new message in any chat.
        event.message contains the full Message object.
        event.chat_id gives the chat ID.
        event.text gives the message text.
        """
        pass  # User overrides this by registering their own handler

    @client.on(events.MessageEdited)
    async def on_message_edited(event):
        """Handle edited messages.
        
        Fires when any message is edited.
        """
        pass

    @client.on(events.ChatAction)
    async def on_chat_action(event):
        """Handle chat actions (joins, leaves, pins, etc.).
        
        event.user_id - user who performed action
        event.chat_id - chat where action happened
        event.user_added / event.user_left / event.user_kicked
        event.unpin / event.pin
        """
        pass

    @client.on(events.Raw)
    async def on_raw(event):
        """Handle raw Telegram updates.
        
        event.update contains the raw Update object.
        Use for catching updates not covered by other handlers.
        """
        pass

    @client.on(events.MessageRead)
    async def on_read(event):
        """Handle read receipt updates.
        
        Fires when messages are read in a chat.
        """
        pass

    @client.on(events.UserUpdate)
    async def on_user_update(event):
        """Handle user status updates (online/offline/typing).
        
        event.status - new user status
        event.user_id - user whose status changed
        """
        pass

    @client.on(events.Album)
    async def on_album(event):
        """Handle media albums (grouped media messages).
        
        event.messages - list of messages in the album
        event.text - common caption
        """
        pass

    @client.on(events.InlineQuery)
    async def on_inline_query(event):
        """Handle inline queries (if running as bot).
        
        event.query - query text
        event.builder - result builder helper
        """
        pass

    @client.on(events.CallbackQuery)
    async def on_callback_query(event):
        """Handle callback queries from inline keyboards.
        
        event.data - callback data bytes
        event.message_id - message with the keyboard
        """
        pass

    @client.on(events.StopPropagation)
    async def stop_propagation(event):
        """Stop propagation to other handlers."""
        pass

    return {
        "handlers_set": 9,
        "client_ready": True,
    }


async def on_message(client: TelegramClient, chats=None, func=None):
    """Decorator-style helper: register a message handler.
    
    Args:
        client: Telethon client
        chats: List of chat IDs to filter (None = all)
        func: Callable filter function(message) -> bool
    
    Returns:
        Decorator function
    """
    def decorator(handler):
        @client.on(events.NewMessage(chats=chats, func=func))
        async def wrapper(event):
            await handler(event)
        return wrapper
    return decorator


async def on_chat_action(client: TelegramClient, chats=None, func=None):
    """Register a chat action handler.
    
    Args:
        client: Telethon client
        chats: Chat ID filter
        func: Callable filter
    
    Returns:
        Decorator function
    """
    def decorator(handler):
        @client.on(events.ChatAction(chats=chats, func=func))
        async def wrapper(event):
            await handler(event)
        return wrapper
    return decorator


async def on_raw(client: TelegramClient, update_type=None):
    """Register a raw update handler.
    
    Args:
        client: Telethon client
        update_type: Filter by update type class
    
    Returns:
        Decorator function
    """
    def decorator(handler):
        @client.on(events.Raw(types=update_type))
        async def wrapper(event):
            await handler(event)
        return wrapper
    return decorator
