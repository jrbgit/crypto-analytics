#!/usr/bin/env python3

import requests
import feedparser

# Test AllOrigins with multiple Medium feeds
test_feeds = [
    'https://medium.com/feed/@chainlink',
    'https://medium.com/feed/coinbase',
    'https://medium.com/feed/@ethereum',
    'https://medium.com/feed/the-capital'
]

for feed_url in test_feeds:
    api_url = f'https://api.allorigins.win/raw?url={feed_url}'
    
    print(f'\n=== Testing: {feed_url} ===')
    response = requests.get(api_url, timeout=30)
    print(f'Status: {response.status_code}')
    print(f'Content length: {len(response.content)}')
    
    if response.status_code == 200:
        content = response.content.decode('utf-8', errors='ignore')
        
        # Parse with feedparser
        feed = feedparser.parse(response.content)
        feed_title = getattr(getattr(feed, 'feed', None), 'title', 'None')
        print(f'Feed title: {feed_title}')
        print(f'Number of entries: {len(feed.entries)}')
        
        if feed.entries:
            entry = feed.entries[0]
            print(f'First entry title: {getattr(entry, "title", "None")}')
            print(f'First entry link: {getattr(entry, "link", "None")}')
            print(f'First entry author: {getattr(entry, "author", "None")}')
            if hasattr(entry, 'published_parsed'):
                print(f'Published: {entry.published_parsed}')
            if hasattr(entry, 'summary'):
                print(f'Summary length: {len(entry.summary)}')
            print('SUCCESS - Found articles!')
            break  # Stop testing once we find a working feed
        else:
            print('No entries found!')
            # Debug feedparser errors
            if hasattr(feed, 'bozo') and feed.bozo:
                print(f'Feed parsing error: {feed.bozo_exception}')
    else:
        print(f'Failed to fetch content: {response.status_code}')
