"""
Spotify MCP Server Module

This module provides a FastMCP server for controlling Spotify playback,
searching for content, and managing playlists through a standardized API.
"""

import sys
import json
import logging
from typing import List, Optional, Any, Dict
import inspect

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from spotipy import SpotifyException
from fastapi.responses import JSONResponse

from .spotify_api import Client, REDIRECT_URI, handle_oauth_callback
from .spotify_helper import normalize_redirect_uri
from .logging_config import setup_logging, log_info, log_error
from .models import (
    ToolModel,
    Playback,
    Queue,
    GetInfo,
    Search,
    Playlist,
    Devices,
    PlaybackResponse,
    SearchResponse,
    QueueResponse,
    GetInfoResponse,
    PlaylistResponse,
    DevicesResponse,
)

# Initialize logging
logger = setup_logging("spotify_mcp_server.server", level=logging.INFO)
# Normalize the redirect URI to meet Spotify's requirements
if REDIRECT_URI:
    REDIRECT_URI = normalize_redirect_uri(REDIRECT_URI)
spotify_client = Client(logger)

# models are defined in spotify_mcp_server.models


# Initialize FastMCP server
mcp_server = FastMCP("spotify-mcp")

# Define the callback handler
@mcp_server.custom_route("/callback", methods=["GET"])
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

# Override the default list_tools handler to include the Pydantic ToolModel schemas
# Capture the original low-level list_tools (if present) and replace it with a wrapper
_original_list_tools = getattr(mcp_server._mcp_server, "list_tools", None)

async def _list_tools_override(*args, **kwargs):
    # Call the original list_tools if present, otherwise start with an empty list
    try:
        default_tools = []
        if _original_list_tools is not None:
            # call the original; it may be sync or async
            try:
                result = _original_list_tools(*args, **kwargs)
            except TypeError:
                # Some bound methods might expect no args even if called with args; try without
                result = _original_list_tools()
            if inspect.isawaitable(result):
                default_tools = await result
            else:
                default_tools = result or []
        else:
            default_tools = []
    except Exception as e:
        # Log and continue with an empty list to avoid breaking discovery over HTTP
        logger.warning("original list_tools failed; continuing with empty default_tools: %s", e)
        default_tools = []

    # Build Tool entries from our Pydantic models
    extra_tools = [
        Playback.as_tool(),
        Search.as_tool(),
        Queue.as_tool(),
        GetInfo.as_tool(),
        Playlist.as_tool(),
        Devices.as_tool(),
    ]

    # Avoid duplicates by name
    try:
        names = {t.name for t in default_tools}
    except Exception:
        names = set()

    combined = default_tools + [t for t in extra_tools if t.name not in names]
    return combined

# assign the wrapper onto the low-level mcp server so HTTP discovery sees the merged list
mcp_server._mcp_server.list_tools = _list_tools_override

@mcp_server.tool(
    name="SpotifyPlayback",
    description=(
        "Manage current user's playback: get, start, pause, skip, previous. "
        "Requires user token + scopes: user-read-playback-state, user-modify-playback-state."
    ),
)
async def handle_playback(payload: Playback) -> dict:
    """Manages the current playback with the following actions:
    - get: Get information about user's current track.
    - start: Starts playing new item or resumes current playback if called with no uri.
    - pause: Pauses current playback.
    - skip: Skips current track.
    - previous: Goes to previous track.
    """
    # Use the Pydantic payload fields
    action = payload.action
    spotify_uri = payload.spotify_uri
    num_skips = payload.num_skips or 1
    device_id = getattr(payload, 'device_id', None)

    log_info(logger, "Playback action requested", action=action, spotify_uri=spotify_uri, num_skips=num_skips, device_id=device_id)
    try:
        match action:
            case "get":
                log_info(logger, "Attempting to get current track")
                curr_track = spotify_client.get_current_track()
                if curr_track:
                    track_name = curr_track.get('name', 'Unknown')
                    log_info(logger, "Current track retrieved", track_name=track_name)
                    return PlaybackResponse(status="ok", current_track=curr_track).model_dump()
                log_info(logger, "No track currently playing")
                return PlaybackResponse(status="ok", current_track=None, message="No track playing.").model_dump()
            case "start":
                log_info(logger, "Starting playback", spotify_uri=spotify_uri, device_id=device_id)
                spotify_client.start_playback(spotify_uri=spotify_uri, device=device_id)
                log_info(logger, "Playback started successfully")
                return PlaybackResponse(status="ok", message="Playback starting.").model_dump()
            case "pause":
                log_info(logger, "Attempting to pause playback", device_id=device_id)
                spotify_client.pause_playback(device=device_id)
                log_info(logger, "Playback paused successfully")
                return PlaybackResponse(status="ok", message="Playback paused.").model_dump()
            case "skip":
                log_info(logger, "Skipping tracks", num_skips=num_skips, device_id=device_id)
                spotify_client.skip_track(n=num_skips)
                return PlaybackResponse(status="ok", message=f"Skipped {num_skips} track(s).").model_dump()
            case "previous":
                log_info(logger, "Going to previous track", device_id=device_id)
                spotify_client.previous_track()
                return PlaybackResponse(status="ok", message="Went to previous track.").model_dump()
            case _:
                log_error(logger, "Unknown playback action", action=action)
                return PlaybackResponse(status="error", message=f"Unknown action: {action}").model_dump()
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in playback", 
                 action=action, error=str(se), exception_type="SpotifyException")
        return PlaybackResponse(status="error", message=error_msg).model_dump()
    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}"
        log_error(logger, "Unexpected error in playback", 
                 action=action, error=str(e), exception_type=type(e).__name__)
        return PlaybackResponse(status="error", message=error_msg).model_dump()


@mcp_server.tool(
    name="SpotifySearch",
    description=(
        "Search for tracks, albums, artists, or playlists on Spotify. "
        "Returns parsed search results grouped by type."
    ),
)
async def handle_search(payload: Search) -> dict:
    """Search for tracks, albums, artists, or playlists on Spotify."""
    query = payload.query
    qtype = payload.qtype or "track"
    limit = payload.limit or 10
    log_info(logger, "Performing search", query=query, qtype=qtype, limit=limit)

    try:
        search_results = spotify_client.search(query=query, qtype=qtype, limit=limit)
        result_count = sum(len(v) if isinstance(v, list) else 1 for v in search_results.values())
        log_info(logger, "Search completed successfully", result_count=result_count)
        return SearchResponse(status="ok", results=search_results).model_dump()
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in search", 
                 query=query, qtype=qtype, error=str(se), exception_type="SpotifyException")
        return SearchResponse(status="error", message=error_msg).model_dump()
    except Exception as e:
        error_msg = f"Search error occurred: {str(e)}"
        log_error(logger, "Unexpected error in search", 
                 query=query, qtype=qtype, error=str(e), exception_type=type(e).__name__)
        return SearchResponse(status="error", message=error_msg).model_dump()


@mcp_server.tool(
    name="SpotifyQueue",
    description=("Manage the playback queue - add items or retrieve the current queue."),
)
async def handle_queue(payload: Queue) -> dict:
    """Manage the playback queue - get the queue or add tracks."""
    action = payload.action
    track_id = payload.track_id
    log_info(logger, "Queue operation requested", action=action, track_id=track_id)

    try:
        match action:
            case "add":
                if not track_id:
                    log_error(logger, "Missing track_id for add action", action=action)
                    return QueueResponse(status="error", message="track_id is required for add action").model_dump()
                spotify_client.add_to_queue(track_id)
                log_info(logger, "Track added to queue successfully", track_id=track_id)
                return QueueResponse(status="ok", message="Track added to queue.", track_id=track_id).model_dump()
            case "get":
                queue = spotify_client.get_queue()
                queue_length = len(queue.get('queue', [])) if isinstance(queue, dict) else 0
                log_info(logger, "Queue retrieved successfully", queue_length=queue_length)
                return QueueResponse(status="ok", queue=queue).model_dump()
            case _:
                log_error(logger, "Unknown queue action", action=action)
                return QueueResponse(status="error", message=f"Unknown queue action: {action}. Supported actions are: add and get.").model_dump()
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in queue operation", 
                 action=action, track_id=track_id, error=str(se), exception_type="SpotifyException")
        return QueueResponse(status="error", message=error_msg).model_dump()
    except Exception as e:
        error_msg = f"Queue operation error: {str(e)}"
        log_error(logger, "Unexpected error in queue operation", 
                 action=action, track_id=track_id, error=str(e), exception_type=type(e).__name__)
        return QueueResponse(status="error", message=error_msg).model_dump()


@mcp_server.tool(
    name="SpotifyGetInfo",
    description=("Get detailed information about a Spotify item (track, album, artist, or playlist)."),
)
async def handle_get_info(payload: GetInfo) -> dict:
    """Get detailed information about a Spotify item (track, album, artist, or playlist)."""
    item_uri = payload.item_uri
    log_info(logger, "Getting item info", item_uri=item_uri)
    try:
        item_info = spotify_client.get_info(item_uri=item_uri)
        item_type = item_uri.split(':')[1] if ':' in item_uri else 'unknown'
        log_info(logger, "Item info retrieved successfully", item_uri=item_uri, item_type=item_type)
        return GetInfoResponse(status="ok", item=item_info).model_dump()
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in get_info", 
                 item_uri=item_uri, error=str(se), exception_type="SpotifyException")
        return GetInfoResponse(status="error", message=error_msg).model_dump()
    except Exception as e:
        error_msg = f"Get info error: {str(e)}"
        log_error(logger, "Unexpected error in get_info", 
                 item_uri=item_uri, error=str(e), exception_type=type(e).__name__)
        return GetInfoResponse(status="error", message=error_msg).model_dump()


@mcp_server.tool(
    name="SpotifyPlaylist",
    description=("Manage Spotify playlists: get, get_tracks, add_tracks, remove_tracks, change_details."),
)
async def handle_playlist(payload: Playlist) -> dict:
    """Manage Spotify playlists."""
    action = payload.action
    playlist_id = payload.playlist_id
    track_ids = payload.track_ids
    name = payload.name
    description = payload.description

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
                return PlaylistResponse(status="ok", playlists=playlists).model_dump()
            case "get_tracks":
                if not playlist_id:
                    log_error(logger, "Missing playlist_id for get_tracks", action=action)
                    return PlaylistResponse(status="error", message="playlist_id is required for get_tracks action.").model_dump()
                tracks = spotify_client.get_playlist_tracks(playlist_id)
                track_count = len(tracks) if isinstance(tracks, list) else 0
                log_info(logger, "Playlist tracks retrieved", playlist_id=playlist_id, track_count=track_count)
                return PlaylistResponse(status="ok", tracks=tracks).model_dump()
            case "add_tracks":
                if not playlist_id or not track_ids:
                    log_error(logger, "Missing required parameters for add_tracks", 
                             action=action, has_playlist_id=bool(playlist_id), has_track_ids=bool(track_ids))
                    return PlaylistResponse(status="error", message="playlist_id and track_ids are required for add_tracks action.").model_dump()
                spotify_client.add_tracks_to_playlist(playlist_id=playlist_id, track_ids=track_ids)
                log_info(logger, "Tracks added to playlist", playlist_id=playlist_id, track_count=len(track_ids))
                return PlaylistResponse(status="ok", message="Tracks added to playlist.", playlist_id=playlist_id, added=len(track_ids)).model_dump()
            case "remove_tracks":
                if not playlist_id or not track_ids:
                    log_error(logger, "Missing required parameters for remove_tracks", 
                             action=action, has_playlist_id=bool(playlist_id), has_track_ids=bool(track_ids))
                    return PlaylistResponse(status="error", message="playlist_id and track_ids are required for remove_tracks action.").model_dump()
                spotify_client.remove_tracks_from_playlist(playlist_id=playlist_id, track_ids=track_ids)
                log_info(logger, "Tracks removed from playlist", playlist_id=playlist_id, track_count=len(track_ids))
                return PlaylistResponse(status="ok", message="Tracks removed from playlist.", playlist_id=playlist_id, removed=len(track_ids)).model_dump()
            case "change_details":
                if not playlist_id:
                    log_error(logger, "Missing playlist_id for change_details", action=action)
                    return PlaylistResponse(status="error", message="playlist_id is required for change_details action.").model_dump()
                if not name and not description:
                    log_error(logger, "Missing name and description for change_details", action=action, playlist_id=playlist_id)
                    return PlaylistResponse(status="error", message="At least one of name or description is required.").model_dump()
                spotify_client.change_playlist_details(
                    playlist_id=playlist_id,
                    name=name,
                    description=description
                )
                log_info(logger, "Playlist details changed", playlist_id=playlist_id, 
                        changed_name=bool(name), changed_description=bool(description))
                return PlaylistResponse(status="ok", message="Playlist details changed.", playlist_id=playlist_id).model_dump()
            case _:
                log_error(logger, "Unknown playlist action", action=action)
                return PlaylistResponse(status="error", message=f"Unknown playlist action: {action}.").model_dump()
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error in playlist operation", 
                 action=action, playlist_id=playlist_id, error=str(se), exception_type="SpotifyException")
        return PlaylistResponse(status="error", message=error_msg).model_dump()
    except Exception as e:
        error_msg = f"Playlist operation error: {str(e)}"
        log_error(logger, "Unexpected error in playlist operation", 
                 action=action, playlist_id=playlist_id, error=str(e), exception_type=type(e).__name__)
        return PlaylistResponse(status="error", message=error_msg).model_dump()


@mcp_server.tool(
    name="SpotifyDevices",
    description=("Get available Spotify devices for the current user."),
)
async def handle_devices(payload: Devices) -> dict:
    """Handle device listing requests"""
    log_info(logger, "Getting available devices")
    try:
        devices = spotify_client.get_devices()
        device_count = len(devices) if isinstance(devices, list) else 0
        log_info(logger, "Devices retrieved successfully", device_count=device_count)
        return DevicesResponse(status="ok", devices=devices).model_dump()
    except SpotifyException as se:
        error_msg = f"Spotify Client error occurred: {str(se)}"
        log_error(logger, "Spotify API error getting devices", 
                 error=str(se), exception_type="SpotifyException")
        return DevicesResponse(status="error", message=error_msg).model_dump()
    except Exception as e:
        error_msg = f"Error getting devices: {str(e)}"
        log_error(logger, "Unexpected error getting devices", 
                 error=str(e), exception_type=type(e).__name__)
        return DevicesResponse(status="error", message=error_msg).model_dump()

# Create the Starlette app after registering routes/tools so custom routes are included
app = mcp_server.streamable_http_app()

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
