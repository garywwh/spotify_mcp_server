"""Pydantic models for Spotify MCP server

This module contains request and response Pydantic models used by the
MCP tools. Keeping them in a separate module keeps the server file concise
and makes the models reusable in tests and documentation.
"""
from typing import Any, Dict, List, Optional

import mcp.types as types
from pydantic import BaseModel, Field


class ToolModel(BaseModel):
    @classmethod
    def as_tool(cls):
        annotations = types.ToolAnnotations(
            title=(cls.__doc__ or cls.__name__).strip() if cls.__doc__ else cls.__name__,
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=None,
            openWorldHint=True,
        )

        return types.Tool(
            name="Spotify" + cls.__name__,
            title=(cls.__doc__ or cls.__name__).strip() if cls.__doc__ else cls.__name__,
            description=(cls.__doc__ or "").strip(),
            inputSchema=cls.model_json_schema(),
            annotations=annotations,
        )


class Playback(ToolModel):
    """Manages the current playback with the following actions:
    - get: Get information about user's current track.
    - start: Starts playing new item or resumes current playback if called with no uri.
    - pause: Pauses current playback.
    - skip: Skips current track.
    """
    action: str = Field(description="Action to perform: 'get', 'start', 'pause' or 'skip'.")
    spotify_uri: Optional[str] = Field(default=None, description="Spotify uri of item to play for 'start' action.")
    num_skips: Optional[int] = Field(default=1, description="Number of tracks to skip for `skip` action.")
    # device_id is optional and may be added dynamically by callers
    device_id: Optional[str] = Field(default=None, description="Optional device id for playback operations.")


class Queue(ToolModel):
    """Manage the playback queue - get the queue or add tracks."""
    action: str = Field(description="Action to perform: 'add' or 'get'.")
    track_id: Optional[str] = Field(default=None, description="Track ID to add to queue (required for add action)")


class GetInfo(ToolModel):
    """Get detailed information about a Spotify item (track, album, artist, or playlist)."""
    item_uri: str = Field(description="URI of the item to get information about.")


class Search(ToolModel):
    """Search for tracks, albums, artists, or playlists on Spotify."""
    query: str = Field(description="query term")
    qtype: Optional[str] = Field(default="track", description="Type of items to search for")
    limit: Optional[int] = Field(default=10, description="Maximum number of items to return")


class Playlist(ToolModel):
    """Manage Spotify playlists.
    - get, get_tracks, add_tracks, remove_tracks, change_details
    """
    action: str = Field(description="Action to perform: 'get','get_tracks','add_tracks','remove_tracks','change_details'.")
    playlist_id: Optional[str] = Field(default=None, description="ID of the playlist to manage.")
    track_ids: Optional[List[str]] = Field(default=None, description="List of track IDs to add/remove.")
    name: Optional[str] = Field(default=None, description="New name for the playlist.")
    description: Optional[str] = Field(default=None, description="New description for the playlist.")


class Devices(ToolModel):
    """Get available Spotify devices"""
    pass


# -------------------------
# Response models
# -------------------------


class PlaybackResponse(BaseModel):
    status: str
    message: Optional[str] = None
    current_track: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    status: str
    results: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class QueueResponse(BaseModel):
    status: str
    queue: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    track_id: Optional[str] = None


class GetInfoResponse(BaseModel):
    status: str
    item: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class PlaylistResponse(BaseModel):
    status: str
    playlists: Optional[List[Dict[str, Any]]] = None
    tracks: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None
    playlist_id: Optional[str] = None
    added: Optional[int] = None
    removed: Optional[int] = None


class DevicesResponse(BaseModel):
    status: str
    devices: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None
