"""
Waguri X/Twitter Client
Full X/Twitter automation via twikit with cookie-based auth.

Modules:
    auth      - Authentication, cookies, user info
    tweets    - Create, delete, like, retweet, bookmark, poll, schedule
    search    - Search tweets, users, communities, lists, trends
    users     - Follow, block, mute, get followers/following
    dm        - Direct messages (1:1 and group)
    lists     - List management and members
    media     - Upload images/videos, metadata
    timeline  - Home timeline, notifications

Usage:
    import asyncio
    from tweets import create_tweet, like
    from search import search_tweets
    from users import follow

    asyncio.run(create_tweet("Hello from Waguri!"))
    asyncio.run(like("1234567890"))
"""
