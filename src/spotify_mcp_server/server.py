
"""
Spotify MCP Server Module

This module provides a FastMCP server for controlling Spotify playback,
searching for content, and managing playlists through a standardized API.
"""

import sys
import json
import logging
from typing import List, Optional

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from spotipy import SpotifyException
from fastapi.responses import JSONResponse

from .spotify_api import Client, REDIRECT_URI, handle_oauth_callback
from .spotify_helper import normalize_redirect_uri
from .logging_config import setup_logging, log_info, log_error

# Initialize logging
logger = setup_logging("spotify_mcp_server.server", level=logging.INFO)
# Normalize the redirect URI to meet Spotify's requirements
if REDIRECT_URI:
    REDIRECT_URI = normalize_redirect_uri(REDIRECT_URI)
spotify_client = Client(logger)

class ToolModel(BaseModel):
    @classmethod
    def as_tool(cls):
        return types.Tool(
            name="Spotify" + cls.__name__,
            description=cls.__doc__,
            inputSchema=cls.model_json_schema()
        )


class Playback(ToolModel):
    """Manages the current playback with the following actions:
    - get: Get information about user's current track.
    - start: Starts playing new item or resumes current playback if called with no uri.
    - pause: Pauses current playback.
    - skip: Skips current track.
    """
    action: str = Field(description="Action to perform: 'get', 'start', 'pause' or 'skip'.")
    spotify_uri: Optional[str] = Field(default=None, description="Spotify uri of item to play for 'start' action. " +
                                                                 "If omitted, resumes current playback.")
    num_skips: Optional[int] = Field(default=1, description="Number of tracks to skip for `skip` action.")


class Queue(ToolModel):
    """Manage the playback queue - get the queue or add tracks."""
    action: str = Field(description="Action to perform: 'add' or 'get'.")
    track_id: Optional[str] = Field(default=None, description="Track ID to add to queue (required for add action)")


class GetInfo(ToolModel):
    """Get detailed information about a Spotify item (track, album, artist, or playlist)."""
    item_uri: str = Field(description="URI of the item to get information about. " +
                                      "If 'playlist' or 'album', returns its tracks. " +
                                      "If 'artist', returns albums and top tracks.")


class Search(ToolModel):
    """Search for tracks, albums, artists, or playlists on Spotify."""
    query: str = Field(description="query term")
    qtype: Optional[str] = Field(default="track",
                                 description="Type of items to search for (track, album, artist, playlist, " +
                                             "or comma-separated combination)")
    limit: Optional[int] = Field(default=10, description="Maximum number of items to return")


class Playlist(ToolModel):
    """Manage Spotify playlists.
    - get: Get a list of user's playlists.
    - get_tracks: Get tracks in a specific playlist.
    - add_tracks: Add tracks to a specific playlist.
    - remove_tracks: Remove tracks from a specific playlist.
    - change_details: Change details of a specific playlist.
    """
    action: str = Field(
        description="Action to perform: 'get', 'get_tracks', 'add_tracks', 'remove_tracks', 'change_details'.")
    playlist_id: Optional[str] = Field(default=None, description="ID of the playlist to manage.")
    track_ids: Optional[List[str]] = Field(default=None, description="List of track IDs to add/remove.")
    name: Optional[str] = Field(default=None, description="New name for the playlist.")
    description: Optional[str] = Field(default=None, description="New description for the playlist.")


class Devices(ToolModel):
    """Get available Spotify devices"""
    pass  # No parameters needed


# Initialize FastMCP server
mcp_server = FastMCP("spotify-mcp")

# Get the Starlette app from MCP server directly
app = mcp_server.streamable_http_app()

# Define the callback handler
async def spotify_callback(request):
    """Handle Spotify OAuth callback"""
    code = request.query_params.get('code')
    log_info(logger, "Received OAuth callback", code=code)
    if not code:
        log_error(logger, "No code provided in callback")
        return JSONResponse({"detail": "No code provided"}, status_code=400)

    try:
        token_info = handle_oauth_callback(code)
        log_info(logger, "Successfully handled OAuth callback")
        # Return success message
        return JSONResponse(content={"status": "Authentication successful"})
    except Exception as e:
        log_error(logger, "Error in OAuth callback", error=str(e), exception_type=type(e).__name__)
        return JSONResponse({"detail": str(e)}, status_code=500)

# Add the callback route to the app
from starlette.routing import Route
app.routes.append(Route("/callback", spotify_callback))


@mcp_server.tool(name="SpotifyPlayback")
async def handle_playback(action: str, spotify_uri: Optional[str] = None, num_skips: int = 1) -> str:
    """Manages the current playback with the following actions:
    - get: Get information about user's current track.
    - start: Starts playing new item or resumes current playback if called with no uri.
    - pause: Pauses current playback.
    - skip: Skips current track.
    """
    log_info(logger, "Playback action requested", action=action, spotify_uri=spotify_uri, num_skips=num_skips)
    try:
        match action:
            case "get":
                log_info(logger, "Attempting to get current track")
                curr_track = spotify_client.get_current_track()
                if curr_track:
                    track_name = curr_track.get('name', 'Unknown')
                    log_info(logger, "Current track retrieved", track_name=track_name)
                    return json.dumps(curr_track, indent=2)
                log_info(logger, "No track currently playing")
                return "No track playing."
            case "start":
                log_info(logger, "Starting playback", spotify_uri=spotify_uri)
                spotify_client.start_playback(spotify_uri=spotify_uri)
                log_info(logger, "Playback started successfully")
                return "Playback starting."
            case "pause":
                log_info(logger, "Attempting to pause playback")
                spotify_client.pause_playback()
                log_info(logger, "Playback paused successfully")
                return "Playback paused."
            case "skip":
                log_info(logger, "Skipping tracks", num_skips=num_skips)
                spotify_client.skip_track(n=num_skips)
                return "Skipped to next track."
            case _:
                log_error(logger, "Unknown playback action", action=action)
                return f"Unknown action: {action}"
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in playback", 
                 action=action, error=str(se), exception_type="SpotifyException")
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}"
        log_error(logger, "Unexpected error in playback", 
                 action=action, error=str(e), exception_type=type(e).__name__)
        return error_msg


@mcp_server.tool(name="SpotifySearch")
async def handle_search(query: str, qtype: str = "track", limit: int = 10) -> str:
    """Search for tracks, albums, artists, or playlists on Spotify."""
    log_info(logger, "Performing search", query=query, qtype=qtype, limit=limit)
    try:
        search_results = spotify_client.search(query=query, qtype=qtype, limit=limit)
        result_count = sum(len(v) if isinstance(v, list) else 1 for v in search_results.values())
        log_info(logger, "Search completed successfully", result_count=result_count)
        return json.dumps(search_results, indent=2)
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in search", 
                 query=query, qtype=qtype, error=str(se), exception_type="SpotifyException")
        return error_msg
    except Exception as e:
        error_msg = f"Search error occurred: {str(e)}"
        log_error(logger, "Unexpected error in search", 
                 query=query, qtype=qtype, error=str(e), exception_type=type(e).__name__)
        return error_msg


@mcp_server.tool(name="SpotifyQueue")
async def handle_queue(action: str, track_id: Optional[str] = None) -> str:
    """Manage the playback queue - get the queue or add tracks."""
    log_info(logger, "Queue operation requested", action=action, track_id=track_id)
    try:
        match action:
            case "add":
                if not track_id:
                    log_error(logger, "Missing track_id for add action", action=action)
                    return "track_id is required for add action"
                spotify_client.add_to_queue(track_id)
                log_info(logger, "Track added to queue successfully", track_id=track_id)
                return "Track added to queue."
            case "get":
                queue = spotify_client.get_queue()
                queue_length = len(queue.get('queue', [])) if isinstance(queue, dict) else 0
                log_info(logger, "Queue retrieved successfully", queue_length=queue_length)
                return json.dumps(queue, indent=2)
            case _:
                log_error(logger, "Unknown queue action", action=action)
                return f"Unknown queue action: {action}. Supported actions are: add and get."
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in queue operation", 
                 action=action, track_id=track_id, error=str(se), exception_type="SpotifyException")
        return error_msg
    except Exception as e:
        error_msg = f"Queue operation error: {str(e)}"
        log_error(logger, "Unexpected error in queue operation", 
                 action=action, track_id=track_id, error=str(e), exception_type=type(e).__name__)
        return error_msg


@mcp_server.tool(name="SpotifyGetInfo")
async def handle_get_info(item_uri: str) -> str:
    """Get detailed information about a Spotify item (track, album, artist, or playlist)."""
    log_info(logger, "Getting item info", item_uri=item_uri)
    try:
        item_info = spotify_client.get_info(item_uri=item_uri)
        item_type = item_uri.split(':')[1] if ':' in item_uri else 'unknown'
        log_info(logger, "Item info retrieved successfully", item_uri=item_uri, item_type=item_type)
        return json.dumps(item_info, indent=2)
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in get_info", 
                 item_uri=item_uri, error=str(se), exception_type="SpotifyException")
        return error_msg
    except Exception as e:
        error_msg = f"Get info error: {str(e)}"
        log_error(logger, "Unexpected error in get_info", 
                 item_uri=item_uri, error=str(e), exception_type=type(e).__name__)
        return error_msg


@mcp_server.tool(name="SpotifyPlaylist")
async def handle_playlist(
    action: str,
    playlist_id: Optional[str] = None,
    track_ids: Optional[List[str]] = None,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """Manage Spotify playlists."""
    log_info(logger, "Playlist operation requested", 
             action=action, playlist_id=playlist_id, 
             track_count=len(track_ids) if track_ids else 0,
             has_name=bool(name), has_description=bool(description))
    try:
        match action:
            case "get":
                playlists = spotify_client.get_current_user_playlists()
                playlist_count = len(playlists) if isinstance(playlists, list) else 0
                log_info(logger, "User playlists retrieved", playlist_count=playlist_count)
                return json.dumps(playlists, indent=2)
            case "get_tracks":
                if not playlist_id:
                    log_error(logger, "Missing playlist_id for get_tracks", action=action)
                    return "playlist_id is required for get_tracks action."
                tracks = spotify_client.get_playlist_tracks(playlist_id)
                track_count = len(tracks) if isinstance(tracks, list) else 0
                log_info(logger, "Playlist tracks retrieved", playlist_id=playlist_id, track_count=track_count)
                return json.dumps(tracks, indent=2)
            case "add_tracks":
                if not playlist_id or not track_ids:
                    log_error(logger, "Missing required parameters for add_tracks", 
                             action=action, has_playlist_id=bool(playlist_id), has_track_ids=bool(track_ids))
                    return "playlist_id and track_ids are required for add_tracks action."
                spotify_client.add_tracks_to_playlist(playlist_id=playlist_id, track_ids=track_ids)
                log_info(logger, "Tracks added to playlist", playlist_id=playlist_id, track_count=len(track_ids))
                return "Tracks added to playlist."
            case "remove_tracks":
                if not playlist_id or not track_ids:
                    log_error(logger, "Missing required parameters for remove_tracks", 
                             action=action, has_playlist_id=bool(playlist_id), has_track_ids=bool(track_ids))
                    return "playlist_id and track_ids are required for remove_tracks action."
                spotify_client.remove_tracks_from_playlist(playlist_id=playlist_id, track_ids=track_ids)
                log_info(logger, "Tracks removed from playlist", playlist_id=playlist_id, track_count=len(track_ids))
                return "Tracks removed from playlist."
            case "change_details":
                if not playlist_id:
                    log_error(logger, "Missing playlist_id for change_details", action=action)
                    return "playlist_id is required for change_details action."
                if not name and not description:
                    log_error(logger, "Missing name and description for change_details", action=action, playlist_id=playlist_id)
                    return "At least one of name or description is required."
                spotify_client.change_playlist_details(
                    playlist_id=playlist_id,
                    name=name,
                    description=description
                )
                log_info(logger, "Playlist details changed", playlist_id=playlist_id, 
                        changed_name=bool(name), changed_description=bool(description))
                return "Playlist details changed."
            case _:
                log_error(logger, "Unknown playlist action", action=action)
                return f"Unknown playlist action: {action}."
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in playlist operation", 
                 action=action, playlist_id=playlist_id, error=str(se), exception_type="SpotifyException")
        return error_msg
    except Exception as e:
        error_msg = f"Playlist operation error: {str(e)}"
        log_error(logger, "Unexpected error in playlist operation", 
                 action=action, playlist_id=playlist_id, error=str(e), exception_type=type(e).__name__)
        return error_msg


@mcp_server.tool("SpotifyDevices")
async def handle_devices(params: dict = None) -> str:
    """Handle device listing requests"""
    log_info(logger, "Getting available devices")
    try:
        devices = spotify_client.get_devices()
        device_count = len(devices) if isinstance(devices, list) else 0
        log_info(logger, "Devices retrieved successfully", device_count=device_count)
        return json.dumps(devices)
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error getting devices", 
                 error=str(se), exception_type="SpotifyException")
        return error_msg
    except Exception as e:
        error_msg = f"Error getting devices: {str(e)}"
        log_error(logger, "Unexpected error getting devices", 
                 error=str(e), exception_type=type(e).__name__)
        return error_msg

if __name__ == "__main__":
    import uvicorn
    from .spotify_api import _oauth_manager
    
    # Print OAuth URL and setup instructions
    auth_url = _oauth_manager.get_authorize_url()
    log_info(logger, "Starting Spotify MCP Server", auth_url=auth_url)
    
    print("\nSpotify Setup Instructions:")
    print("1. Open this URL in your browser to authenticate:")
    print(f"   {auth_url}")
    print("2. After authenticating, you'll be redirected to the callback URL")
    print("3. The server should then be ready to handle requests\n")
    
    log_info(logger, "Starting uvicorn server", host="0.0.0.0", port=8080)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
