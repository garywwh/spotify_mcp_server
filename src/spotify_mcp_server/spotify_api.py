"""
Spotify API Client Module

This module provides a client for interacting with the Spotify Web API.
It handles authentication, playback control, search, and playlist management.
"""

import logging
import os
import time
from typing import Optional, Dict, List

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth
from requests import RequestException

from . import spotify_helper as utils
from .logging_config import get_logger, log_info, log_error, log_warning

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# Normalize the redirect URI to meet Spotify's requirements
if REDIRECT_URI:
    REDIRECT_URI = utils.normalize_redirect_uri(REDIRECT_URI)

SCOPES = ["user-read-currently-playing", "user-read-playback-state",  # spotify connect
          "app-remote-control", "streaming",  # playback
          "playlist-read-private", "playlist-read-collaborative", "playlist-modify-private", "playlist-modify-public",
          # playlists
          "user-read-playback-position", "user-top-read", "user-read-recently-played",  # listening history
          "user-library-modify", "user-library-read",  # library
          ]


# Global OAuth manager
_oauth_manager = SpotifyOAuth(
    scope=",".join(SCOPES),
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI
)

def handle_oauth_callback(code: str) -> Dict:
    """Handle the Spotify OAuth callback and cache the token"""
    logger = get_logger("spotify_mcp_server.oauth")
    try:
        log_info(logger, "Handling OAuth callback", code_length=len(code) if code else 0)
        token_info = _oauth_manager.get_access_token(code, as_dict=True, check_cache=False)
        # Cache the token
        _oauth_manager.cache_handler.save_token_to_cache(token_info)
        log_info(logger, "OAuth token obtained and cached successfully")
        return token_info
    except Exception as e:
        log_error(logger, "Error handling OAuth callback", error=str(e), exception_type=type(e).__name__)
        raise

class Client:
    def __init__(self, logger: logging.Logger):
        """Initialize Spotify client with necessary permissions"""
        self.logger = logger
        self.auth_manager = _oauth_manager
        self.cache_handler = self.auth_manager.cache_handler

        try:
            # Check if we have cached token
            cached_token = self.auth_manager.cache_handler.get_cached_token()
            if not cached_token:
                auth_url = self.auth_manager.get_authorize_url()
                log_info(self.logger, "No cached token found", auth_url=auth_url)
                raise Exception(f"Please authenticate Spotify at: {auth_url}")

            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

            # Verify the token works
            try:
                user_info = self.sp.current_user()
                log_info(self.logger, "Spotify client initialized successfully", 
                        user_id=user_info.get('id', 'unknown'))
            except Exception as e:
                auth_url = self.auth_manager.get_authorize_url()
                log_error(self.logger, "Failed to verify token", 
                         error=str(e), auth_url=auth_url, exception_type=type(e).__name__)
                raise Exception(f"Please re-authenticate Spotify at: {auth_url}")

        except Exception as e:
            log_error(self.logger, "Failed to initialize Spotify client", 
                     error=str(e), exception_type=type(e).__name__)
            raise

        self.username = None

    @utils.validate
    def set_username(self, device=None):
        self.username = self.sp.current_user()['display_name']

    @utils.validate
    def search(self, query: str, qtype: str = 'track', limit=10, device=None):
        """
        Searches based of query term.
        - query: query term
        - qtype: the types of items to return. One or more of 'artist', 'album',  'track', 'playlist'.
                 If multiple types are desired, pass in a comma separated string; e.g. 'track,album'
        - limit: max # items to return
        """
        if self.username is None:
            self.set_username()
        results = self.sp.search(q=query, limit=limit, type=qtype)
        if not results:
            raise ValueError("No search results found.")
        return utils.parse_search_results(results, qtype, self.username)

    def recommendations(self, artists: Optional[List] = None, tracks: Optional[List] = None, limit=20):
        """
        Get track recommendations based on seed artists and tracks.
        - artists: List of artist IDs to use as seeds
        - tracks: List of track IDs to use as seeds
        - limit: Maximum number of recommendations to return
        """
        if not artists and not tracks:
            raise ValueError("At least one seed artist or track is required")
        
        try:
            recs = self.sp.recommendations(seed_artists=artists, seed_tracks=tracks, limit=limit)
            return [utils.parse_track(track) for track in recs['tracks']]
        except Exception as e:
            log_error(self.logger, "Error getting recommendations", error=str(e), exception_type=type(e).__name__)
            raise

    def get_info(self, item_uri: str) -> dict:
        """
        Returns more info about item.
        - item_uri: uri. Looks like 'spotify:track:xxxxxx', 'spotify:album:xxxxxx', etc.
        """
        _, qtype, item_id = item_uri.split(":")
        match qtype:
            case 'track':
                return utils.parse_track(self.sp.track(item_id), detailed=True)
            case 'album':
                album_info = utils.parse_album(self.sp.album(item_id), detailed=True)
                return album_info
            case 'artist':
                artist_info = utils.parse_artist(self.sp.artist(item_id), detailed=True)
                albums = self.sp.artist_albums(item_id)
                top_tracks = self.sp.artist_top_tracks(item_id)['tracks']
                albums_and_tracks = {
                    'albums': albums,
                    'tracks': {'items': top_tracks}
                }
                parsed_info = utils.parse_search_results(albums_and_tracks, qtype="album,track")
                artist_info['top_tracks'] = parsed_info['tracks']
                artist_info['albums'] = parsed_info['albums']

                return artist_info
            case 'playlist':
                if self.username is None:
                    self.set_username()
                playlist = self.sp.playlist(item_id)
                log_info(self.logger, "Retrieved playlist info", playlist_id=item_id, 
                        playlist_name=playlist.get('name', 'unknown'))
                playlist_info = utils.parse_playlist(playlist, self.username, detailed=True)

                return playlist_info

        raise ValueError(f"Unknown qtype {qtype}")

    def get_current_track(self) -> Optional[Dict]:
        """Get information about the currently playing track"""
        try:
            # current_playback vs current_user_playing_track?
            current = self.sp.current_user_playing_track()
            if not current:
                log_info(self.logger, "No playback session found")
                return None
            if current.get('currently_playing_type') != 'track':
                log_info(self.logger, "Current playback is not a track", 
                        currently_playing_type=current.get('currently_playing_type'))
                return None

            track_info = utils.parse_track(current['item'])
            if 'is_playing' in current:
                track_info['is_playing'] = current['is_playing']

            log_info(self.logger, "Current track retrieved", 
                    track_name=track_info.get('name', 'Unknown'),
                    artist=track_info.get('artist', 'Unknown'),
                    is_playing=track_info.get('is_playing', False))
            return track_info
        except Exception as e:
            log_error(self.logger, "Error getting current track info", 
                     error=str(e), exception_type=type(e).__name__)
            raise

    @utils.validate
    def start_playback(self, spotify_uri=None, device=None):
        """
        Starts spotify playback of uri. If spotify_uri is omitted, resumes current playback.
        - spotify_uri: ID of resource to play, or None. Typically looks like 'spotify:track:xxxxxx' or 'spotify:album:xxxxxx'.
        """
        try:
            log_info(self.logger, "Starting playback", spotify_uri=spotify_uri, 
                    device_name=device.get('name') if device else None)
            if not spotify_uri:
                if self.is_track_playing():
                    log_info(self.logger, "No track_id provided and playback already active")
                    return
                if not self.get_current_track():
                    raise ValueError("No track_id provided and no current playback to resume.")

            if spotify_uri is not None:
                if spotify_uri.startswith('spotify:track:'):
                    uris = [spotify_uri]
                    context_uri = None
                else:
                    uris = None
                    context_uri = spotify_uri
            else:
                uris = None
                context_uri = None

            device_id = device.get('id') if device else None

            self.logger.info(f"Starting playback of on {device}: context_uri={context_uri}, uris={uris}")
            result = self.sp.start_playback(uris=uris, context_uri=context_uri, device_id=device_id)
            self.logger.info(f"Playback result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error starting playback: {str(e)}.")
            raise

    @utils.validate
    def pause_playback(self, device=None):
        """Pauses playback."""
        playback = self.sp.current_playback()
        if playback and playback.get('is_playing'):
            self.sp.pause_playback(device.get('id') if device else None)

    @utils.validate
    def add_to_queue(self, track_id: str, device=None):
        """
        Adds track or album to queue.
        - track_id: ID or URI of track or album. Can be either a Spotify ID or full URI.
        """
        try:
            # Convert ID to URI if necessary
            if not track_id.startswith('spotify:'):
                if ':' not in track_id:
                    track_id = f'spotify:track:{track_id}'

            self.logger.info(f"Adding to queue: {track_id}")
            
            if track_id.startswith('spotify:album:'):
                # For albums, get all tracks and add them individually
                album_info = self.get_info(track_id)
                if 'tracks' in album_info:
                    for track in album_info['tracks']:
                        track_uri = f"spotify:track:{track['id']}"
                        self.sp.add_to_queue(track_uri, device.get('id') if device else None)
            else:
                # For individual tracks, add directly
                self.sp.add_to_queue(track_id, device.get('id') if device else None)
        except Exception as e:
            self.logger.error(f"Error adding to queue: {str(e)}")
            raise

    @utils.validate
    def get_queue(self, device=None):
        """Returns the current queue of tracks."""
        queue_info = self.sp.queue()
        queue_info['currently_playing'] = self.get_current_track()

        queue_info['queue'] = [utils.parse_track(track) for track in queue_info.pop('queue')]

        return queue_info

    def get_liked_songs(self, limit=50) -> List[Dict]:
        """
        Get user's saved/liked tracks.
        - limit: Maximum number of tracks to return
        """
        try:
            results = self.sp.current_user_saved_tracks(limit=limit)
            return [utils.parse_track(item['track']) for item in results['items']]
        except Exception as e:
            self.logger.error(f"Error getting liked songs: {str(e)}")
            raise

    def is_track_playing(self) -> bool:
        """Returns if a track is actively playing."""
        curr_track = self.get_current_track()
        if not curr_track:
            return False
        if curr_track.get('is_playing'):
            return True
        return False

    def get_current_user_playlists(self, limit=50) -> List[Dict]:
        """
        Get current user's playlists.
        - limit: Max number of playlists to return.
        """
        playlists = self.sp.current_user_playlists()
        if not playlists:
            raise ValueError("No playlists found.")
        return [utils.parse_playlist(playlist, self.username) for playlist in playlists['items']]
    
    @utils.ensure_username
    def get_playlist_tracks(self, playlist_id: str, limit=50) -> List[Dict]:
        """
        Get tracks from a playlist.
        - playlist_id: ID of the playlist to get tracks from.
        - limit: Max number of tracks to return.
        """
        playlist = self.sp.playlist(playlist_id)
        if not playlist:
            raise ValueError("No playlist found.")
        return utils.parse_tracks(playlist['tracks']['items'])
    
    @utils.ensure_username
    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str], position: Optional[int] = None):
        """
        Add tracks to a playlist.
        - playlist_id: ID of the playlist to modify.
        - track_ids: List of track IDs to add.
        - position: Position to insert the tracks at (optional).
        """
        if not playlist_id:
            raise ValueError("No playlist ID provided.")
        if not track_ids:
            raise ValueError("No track IDs provided.")
        
        try:
            response = self.sp.playlist_add_items(playlist_id, track_ids, position=position)
            self.logger.info(f"Response from adding tracks: {track_ids} to playlist {playlist_id}: {response}")
        except Exception as e:
            self.logger.error(f"Error adding tracks to playlist: {str(e)}")

    @utils.ensure_username
    def remove_tracks_from_playlist(self, playlist_id: str, track_ids: List[str]):
        """
        Remove tracks from a playlist.
        - playlist_id: ID of the playlist to modify.
        - track_ids: List of track IDs to remove.
        """
        if not playlist_id:
            raise ValueError("No playlist ID provided.")
        if not track_ids:
            raise ValueError("No track IDs provided.")
        
        try:
            response = self.sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)
            self.logger.info(f"Response from removing tracks: {track_ids} from playlist {playlist_id}: {response}")
        except Exception as e:
            self.logger.error(f"Error removing tracks from playlist: {str(e)}")

    @utils.ensure_username
    def change_playlist_details(self, playlist_id: str, name: Optional[str] = None, description: Optional[str] = None):
        """
        Change playlist details.
        - playlist_id: ID of the playlist to modify.
        - name: New name for the playlist.
        - public: Whether the playlist should be public.
        - description: New description for the playlist.
        """
        if not playlist_id:
            raise ValueError("No playlist ID provided.")
        
        try:
            response = self.sp.playlist_change_details(playlist_id, name=name, description=description)
            self.logger.info(f"Response from changing playlist details: {response}")
        except Exception as e:
            self.logger.error(f"Error changing playlist details: {str(e)}")
       
    def get_devices(self):
        """Get a list of available devices"""
        try:
            # If token is expired, try to refresh it
            if not self.auth_ok():
                if not self.auth_refresh():
                    raise Exception("Failed to refresh token")
                
            devices = self.sp.devices()
            return devices.get('devices', [])
        except Exception as e:
            self.logger.error(f"Failed to get devices: {e}")
            raise

    def is_active_device(self) -> bool:
        """Check if there is an active Spotify device."""
        try:
            devices = self.get_devices()
            return any(device.get('is_active') for device in devices)
        except Exception as e:
            self.logger.error(f"Error checking active device: {e}")
            return False

    def _get_candidate_device(self):
        devices = self.get_devices()
        if not devices:
            raise ConnectionError("No active device. Is Spotify open?")
        for device in devices:
            if device.get('is_active'):
                return device
        self.logger.info(f"No active device, assigning {devices[0]['name']}.")
        return devices[0]

    def auth_ok(self) -> bool:
        try:
            token = self.cache_handler.get_cached_token()
            if token is None:
                self.logger.info("Auth check result: no token exists")
                return False
                
            # Only check expiration, don't try to refresh
            is_expired = token['expires_at'] < time.time()
            self.logger.info(f"Auth check result: {'valid' if not is_expired else 'expired'}")
            return not is_expired
        except Exception as e:
            self.logger.error(f"Error checking auth status: {str(e)}")
            return False

    def auth_refresh(self):
        try:
            token = self.cache_handler.get_cached_token()
            if token and 'refresh_token' in token:
                new_token = self.auth_manager.refresh_access_token(token['refresh_token'])
                self.cache_handler.save_token_to_cache(new_token)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error refreshing token: {e}")
            return False

    def skip_track(self, n=1):
        # todo: Better error handling
        for _ in range(n):
            self.sp.next_track()

    def previous_track(self):
        self.sp.previous_track()

    def seek_to_position(self, position_ms):
        self.sp.seek_track(position_ms=position_ms)

    def set_volume(self, volume_percent):
        self.sp.volume(volume_percent)