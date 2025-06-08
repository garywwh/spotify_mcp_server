"""
Spotify Helper Module

This module provides helper functions and utilities for the Spotify MCP Server.
It includes data parsing, query building, authentication helpers, and decorators.
"""

import functools
from collections import defaultdict
from typing import Callable, TypeVar, Optional, Dict, List, Union
from urllib.parse import quote, urlparse, urlunparse

from requests import RequestException

T = TypeVar('T')


# =============================================================================
# Authentication and URI Utilities
# =============================================================================

def normalize_redirect_uri(url: str) -> str:
    """
    Normalize redirect URI to meet Spotify's requirements.
    
    Converts localhost to 127.0.0.1 as required by Spotify OAuth.
    
    Args:
        url: The redirect URI to normalize
        
    Returns:
        Normalized URI string
    """
    if not url:
        return url
        
    parsed = urlparse(url)
    
    # Convert localhost to 127.0.0.1
    if parsed.netloc == 'localhost' or parsed.netloc.startswith('localhost:'):
        port = ''
        if ':' in parsed.netloc:
            port = ':' + parsed.netloc.split(':')[1]
        parsed = parsed._replace(netloc=f'127.0.0.1{port}')
    
    return urlunparse(parsed)


# =============================================================================
# Spotify Data Parsers
# =============================================================================

def parse_track(track_item: dict, detailed: bool = False) -> Optional[dict]:
    """
    Parse a Spotify track item into a simplified format.
    
    Args:
        track_item: Raw track data from Spotify API
        detailed: Whether to include detailed information
        
    Returns:
        Parsed track dictionary or None if invalid
    """
    if not track_item:
        return None
        
    narrowed_item = {
        'name': track_item['name'],
        'id': track_item['id'],
    }

    # Add playback status if available
    if 'is_playing' in track_item:
        narrowed_item['is_playing'] = track_item['is_playing']

    # Add detailed information if requested
    if detailed:
        narrowed_item['album'] = parse_album(track_item.get('album'))
        for key in ['track_number', 'duration_ms', 'popularity', 'explicit']:
            if key in track_item:
                narrowed_item[key] = track_item[key]

    # Handle playability
    if not track_item.get('is_playable', True):
        narrowed_item['is_playable'] = False

    # Parse artists
    artists = [artist['name'] for artist in track_item.get('artists', [])]
    if detailed:
        artists = [parse_artist(artist) for artist in track_item.get('artists', [])]

    # Add artist(s) to the result
    if len(artists) == 1:
        narrowed_item['artist'] = artists[0]
    elif len(artists) > 1:
        narrowed_item['artists'] = artists

    return narrowed_item


def parse_artist(artist_item: dict, detailed: bool = False) -> Optional[dict]:
    """
    Parse a Spotify artist item into a simplified format.
    
    Args:
        artist_item: Raw artist data from Spotify API
        detailed: Whether to include detailed information
        
    Returns:
        Parsed artist dictionary or None if invalid
    """
    if not artist_item:
        return None
        
    narrowed_item = {
        'name': artist_item['name'],
        'id': artist_item['id'],
    }
    
    if detailed:
        for key in ['genres', 'popularity', 'followers']:
            if key in artist_item:
                if key == 'followers' and isinstance(artist_item[key], dict):
                    narrowed_item[key] = artist_item[key].get('total', 0)
                else:
                    narrowed_item[key] = artist_item[key]

    return narrowed_item


def parse_playlist(playlist_item: dict, username: str, detailed: bool = False) -> Optional[dict]:
    """
    Parse a Spotify playlist item into a simplified format.
    
    Args:
        playlist_item: Raw playlist data from Spotify API
        username: Current user's username for ownership check
        detailed: Whether to include detailed information (tracks)
        
    Returns:
        Parsed playlist dictionary or None if invalid
    """
    if not playlist_item:
        return None
        
    narrowed_item = {
        'name': playlist_item['name'],
        'id': playlist_item['id'],
        'owner': playlist_item['owner']['display_name'],
        'user_is_owner': playlist_item['owner']['display_name'] == username,
        'total_tracks': playlist_item['tracks']['total'],
    }
    
    if detailed:
        narrowed_item['description'] = playlist_item.get('description')
        narrowed_item['public'] = playlist_item.get('public')
        narrowed_item['collaborative'] = playlist_item.get('collaborative')
        
        # Parse tracks if available
        tracks = []
        for track_item in playlist_item.get('tracks', {}).get('items', []):
            if track_item and track_item.get('track'):
                parsed_track = parse_track(track_item['track'])
                if parsed_track:
                    tracks.append(parsed_track)
        narrowed_item['tracks'] = tracks

    return narrowed_item


def parse_album(album_item: dict, detailed: bool = False) -> Optional[dict]:
    """
    Parse a Spotify album item into a simplified format.
    
    Args:
        album_item: Raw album data from Spotify API
        detailed: Whether to include detailed information
        
    Returns:
        Parsed album dictionary or None if invalid
    """
    if not album_item:
        return None
        
    narrowed_item = {
        'name': album_item['name'],
        'id': album_item['id'],
    }

    # Parse artists
    artists = [artist['name'] for artist in album_item.get('artists', [])]
    
    if detailed:
        # Parse tracks if available
        tracks = []
        for track_item in album_item.get('tracks', {}).get('items', []):
            if track_item:
                parsed_track = parse_track(track_item)
                if parsed_track:
                    tracks.append(parsed_track)
        narrowed_item["tracks"] = tracks
        
        # Parse detailed artist information
        artists = [parse_artist(artist) for artist in album_item.get('artists', [])]
        
        # Add additional album metadata
        for key in ['total_tracks', 'release_date', 'genres', 'popularity', 'album_type']:
            if key in album_item:
                narrowed_item[key] = album_item[key]

    # Add artist(s) to the result
    if len(artists) == 1:
        narrowed_item['artist'] = artists[0]
    elif len(artists) > 1:
        narrowed_item['artists'] = artists

    return narrowed_item


# =============================================================================
# Search and Query Utilities
# =============================================================================

def parse_search_results(results: Dict, qtype: str, username: Optional[str] = None) -> Dict:
    """
    Parse Spotify search results into a structured format.
    
    Args:
        results: Raw search results from Spotify API
        qtype: Comma-separated query types (track, artist, playlist, album)
        username: Current user's username for playlist ownership
        
    Returns:
        Dictionary with parsed results by type
        
    Raises:
        ValueError: If unknown qtype is provided
    """
    parsed_results = defaultdict(list)
    
    for query_type in qtype.split(","):
        query_type = query_type.strip()
        
        match query_type:
            case "track":
                for item in results.get('tracks', {}).get('items', []):
                    if item:
                        parsed_track = parse_track(item)
                        if parsed_track:
                            parsed_results['tracks'].append(parsed_track)
                            
            case "artist":
                for item in results.get('artists', {}).get('items', []):
                    if item:
                        parsed_artist = parse_artist(item)
                        if parsed_artist:
                            parsed_results['artists'].append(parsed_artist)
                            
            case "playlist":
                for item in results.get('playlists', {}).get('items', []):
                    if item:
                        parsed_playlist = parse_playlist(item, username or "")
                        if parsed_playlist:
                            parsed_results['playlists'].append(parsed_playlist)
                            
            case "album":
                for item in results.get('albums', {}).get('items', []):
                    if item:
                        parsed_album = parse_album(item)
                        if parsed_album:
                            parsed_results['albums'].append(parsed_album)
                            
            case _:
                raise ValueError(f"Unknown query type: {query_type}")

    return dict(parsed_results)


def parse_tracks(items: List[Dict]) -> List[Dict]:
    """
    Parse a list of track items and return a list of parsed tracks.

    Args:
        items: List of track items from Spotify API
        
    Returns:
        List of parsed tracks
    """ 
    tracks = []
    for item in items:
        if not item:
            continue
        
        # Handle both direct track items and wrapped track items
        track_data = item.get('track', item)
        parsed_track = parse_track(track_data)
        if parsed_track:
            tracks.append(parsed_track)
            
    return tracks


def build_search_query(
    base_query: str,
    artist: Optional[str] = None,
    track: Optional[str] = None,
    album: Optional[str] = None,
    year: Optional[Union[str, int]] = None,
    year_range: Optional[tuple[int, int]] = None,
    genre: Optional[str] = None,
    is_hipster: bool = False,
    is_new: bool = False
) -> str:
    """
    Build a Spotify search query string with optional filters.

    Args:
        base_query: Base search term
        artist: Artist name filter
        track: Track name filter
        album: Album name filter
        year: Specific year filter
        year_range: Tuple of (start_year, end_year) for year range filter
        genre: Genre filter
        is_hipster: Filter for lowest 10% popularity albums
        is_new: Filter for albums released in past two weeks

    Returns:
        URL-encoded query string with applied filters
    """
    filters = []

    if artist:
        filters.append(f"artist:{artist}")
    if track:
        filters.append(f"track:{track}")
    if album:
        filters.append(f"album:{album}")
    if year:
        filters.append(f"year:{year}")
    if year_range and len(year_range) == 2:
        filters.append(f"year:{year_range[0]}-{year_range[1]}")
    if genre:
        filters.append(f"genre:{genre}")
    if is_hipster:
        filters.append("tag:hipster")
    if is_new:
        filters.append("tag:new")

    query_parts = [base_query] + filters
    return quote(" ".join(query_parts))


# =============================================================================
# Decorators for Spotify Client Methods
# =============================================================================

def validate(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for Spotify API methods that handles authentication and device validation.
    
    This decorator:
    - Checks and refreshes authentication if needed
    - Validates active device and retries with candidate device if needed
    - Handles network request exceptions
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function with validation logic
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Handle authentication
        if not self.auth_ok():
            self.auth_refresh()

        # Handle device validation for playback methods
        if not self.is_active_device():
            kwargs['device'] = self._get_candidate_device()

        try:
            return func(self, *args, **kwargs)
        except RequestException as e:
            # Log the error if logger is available
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"Network error in {func.__name__}: {e}")
            raise

    return wrapper


def ensure_username(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to ensure that the username is set before calling the function.
    
    This decorator automatically calls set_username() if the username is None.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function with username validation
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self, 'username', None) is None:
            self.set_username()
        return func(self, *args, **kwargs)
    
    return wrapper


# =============================================================================
# Utility Functions
# =============================================================================

def extract_spotify_id(uri_or_id: str) -> str:
    """
    Extract Spotify ID from URI or return the ID if already in ID format.
    
    Args:
        uri_or_id: Spotify URI (spotify:track:id) or plain ID
        
    Returns:
        Extracted Spotify ID
        
    Examples:
        >>> extract_spotify_id("spotify:track:4iV5W9uYEdYUVa79Axb7Rh")
        "4iV5W9uYEdYUVa79Axb7Rh"
        >>> extract_spotify_id("4iV5W9uYEdYUVa79Axb7Rh")
        "4iV5W9uYEdYUVa79Axb7Rh"
    """
    if uri_or_id.startswith('spotify:'):
        return uri_or_id.split(':')[-1]
    return uri_or_id


def build_spotify_uri(item_type: str, item_id: str) -> str:
    """
    Build a Spotify URI from type and ID.
    
    Args:
        item_type: Type of Spotify item (track, album, artist, playlist)
        item_id: Spotify ID
        
    Returns:
        Formatted Spotify URI
        
    Examples:
        >>> build_spotify_uri("track", "4iV5W9uYEdYUVa79Axb7Rh")
        "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
    """
    return f"spotify:{item_type}:{item_id}"


def validate_spotify_uri(uri: str) -> bool:
    """
    Validate if a string is a properly formatted Spotify URI.
    
    Args:
        uri: String to validate
        
    Returns:
        True if valid Spotify URI, False otherwise
        
    Examples:
        >>> validate_spotify_uri("spotify:track:4iV5W9uYEdYUVa79Axb7Rh")
        True
        >>> validate_spotify_uri("invalid:uri")
        False
    """
    if not uri or not isinstance(uri, str):
        return False
        
    parts = uri.split(':')
    if len(parts) != 3:
        return False
        
    if parts[0] != 'spotify':
        return False
        
    valid_types = {'track', 'album', 'artist', 'playlist', 'show', 'episode'}
    if parts[1] not in valid_types:
        return False
        
    # Basic ID validation (should be alphanumeric, length 22)
    item_id = parts[2]
    if not item_id or len(item_id) != 22 or not item_id.isalnum():
        return False
        
    return True


def format_duration(duration_ms: int) -> str:
    """
    Format duration from milliseconds to human-readable format.
    
    Args:
        duration_ms: Duration in milliseconds
        
    Returns:
        Formatted duration string (e.g., "3:45", "1:23:45")
    """
    if not duration_ms or duration_ms < 0:
        return "0:00"
        
    total_seconds = duration_ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def safe_get(data: Dict, *keys, default=None):
    """
    Safely get nested dictionary values.
    
    Args:
        data: Dictionary to search
        *keys: Sequence of keys to traverse
        default: Default value if key path doesn't exist
        
    Returns:
        Value at the key path or default
        
    Examples:
        >>> safe_get({"a": {"b": {"c": 1}}}, "a", "b", "c")
        1
        >>> safe_get({"a": {"b": {}}}, "a", "b", "c", default="not found")
        "not found"
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current