"""
Unit tests for the server module.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.responses import JSONResponse
from spotipy import SpotifyException

from spotify_mcp_server.logging_config import setup_logging
from spotify_mcp_server.server import (
    ToolModel,
    Playback,
    Queue,
    GetInfo,
    Search,
    Playlist,
    Devices,
    spotify_callback,
    handle_playback,
    handle_search,
    handle_queue,
    handle_get_info,
    handle_playlist,
    handle_devices
)


class TestSetupLogging:
    """Test cases for setup_logging function."""

    def test_setup_logging_creates_logger(self):
        """Test that setup_logging creates a logger with info and error methods."""
        logger = setup_logging("test_logger")
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')

    def test_logger_info_method(self, capsys):
        """Test logger info method outputs to stderr."""
        logger = setup_logging("test_logger")
        logger.info("Test info message")
        captured = capsys.readouterr()
        assert "Test info message" in captured.err

    def test_logger_error_method(self, capsys):
        """Test logger error method outputs to stderr."""
        logger = setup_logging("test_logger")
        logger.error("Test error message")
        captured = capsys.readouterr()
        assert "Test error message" in captured.err


class TestToolModel:
    """Test cases for ToolModel class."""

    def test_tool_model_as_tool(self):
        """Test ToolModel as_tool class method."""
        class TestTool(ToolModel):
            """Test tool description."""
            pass

        tool = TestTool.as_tool()
        assert tool.name == "SpotifyTestTool"
        assert tool.description == "Test tool description."
        assert tool.inputSchema is not None


class TestPlaybackModel:
    """Test cases for Playback model."""

    def test_playback_model_creation(self):
        """Test Playback model creation with valid data."""
        playback = Playback(action="get")
        assert playback.action == "get"
        assert playback.spotify_uri is None
        assert playback.num_skips == 1

    def test_playback_model_with_uri(self):
        """Test Playback model with Spotify URI."""
        playback = Playback(action="start", spotify_uri="spotify:track:123")
        assert playback.action == "start"
        assert playback.spotify_uri == "spotify:track:123"

    def test_playback_model_with_skips(self):
        """Test Playback model with number of skips."""
        playback = Playback(action="skip", num_skips=3)
        assert playback.action == "skip"
        assert playback.num_skips == 3


class TestQueueModel:
    """Test cases for Queue model."""

    def test_queue_model_creation(self):
        """Test Queue model creation."""
        queue = Queue(action="get")
        assert queue.action == "get"
        assert queue.track_id is None

    def test_queue_model_with_track_id(self):
        """Test Queue model with track ID."""
        queue = Queue(action="add", track_id="track123")
        assert queue.action == "add"
        assert queue.track_id == "track123"


class TestGetInfoModel:
    """Test cases for GetInfo model."""

    def test_get_info_model_creation(self):
        """Test GetInfo model creation."""
        get_info = GetInfo(item_uri="spotify:track:123")
        assert get_info.item_uri == "spotify:track:123"


class TestSearchModel:
    """Test cases for Search model."""

    def test_search_model_creation(self):
        """Test Search model creation."""
        search = Search(query="test query")
        assert search.query == "test query"
        assert search.qtype == "track"
        assert search.limit == 10

    def test_search_model_with_options(self):
        """Test Search model with custom options."""
        search = Search(query="test", qtype="artist", limit=20)
        assert search.query == "test"
        assert search.qtype == "artist"
        assert search.limit == 20


class TestPlaylistModel:
    """Test cases for Playlist model."""

    def test_playlist_model_creation(self):
        """Test Playlist model creation."""
        playlist = Playlist(action="get")
        assert playlist.action == "get"
        assert playlist.playlist_id is None
        assert playlist.track_ids is None
        assert playlist.name is None
        assert playlist.description is None

    def test_playlist_model_with_details(self):
        """Test Playlist model with details."""
        playlist = Playlist(
            action="change_details",
            playlist_id="playlist123",
            name="New Name",
            description="New Description"
        )
        assert playlist.action == "change_details"
        assert playlist.playlist_id == "playlist123"
        assert playlist.name == "New Name"
        assert playlist.description == "New Description"


class TestDevicesModel:
    """Test cases for Devices model."""

    def test_devices_model_creation(self):
        """Test Devices model creation."""
        devices = Devices()
        # No parameters needed for Devices model


class TestSpotifyCallback:
    """Test cases for spotify_callback function."""

    @pytest.mark.asyncio
    async def test_spotify_callback_success(self):
        """Test successful Spotify callback."""
        mock_request = Mock()
        mock_request.query_params.get.return_value = "test_code"
        
        with patch('spotify_mcp_server.server.handle_oauth_callback') as mock_handle:
            mock_handle.return_value = {"access_token": "test_token"}
            
            response = await spotify_callback(mock_request)
            
            assert isinstance(response, JSONResponse)
            mock_handle.assert_called_once_with("test_code")

    @pytest.mark.asyncio
    async def test_spotify_callback_no_code(self):
        """Test Spotify callback without code."""
        mock_request = Mock()
        mock_request.query_params.get.return_value = None
        
        response = await spotify_callback(mock_request)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_spotify_callback_exception(self):
        """Test Spotify callback with exception."""
        mock_request = Mock()
        mock_request.query_params.get.return_value = "test_code"
        
        with patch('spotify_mcp_server.server.handle_oauth_callback') as mock_handle:
            mock_handle.side_effect = Exception("OAuth error")
            
            response = await spotify_callback(mock_request)
            
            assert isinstance(response, JSONResponse)
            assert response.status_code == 500


class TestHandlePlayback:
    """Test cases for handle_playback function."""

    @pytest.mark.asyncio
    async def test_handle_playback_get(self):
        """Test handle_playback with get action."""
        mock_track = {
            "name": "Test Song",
            "artist": "Test Artist"
        }
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.return_value = mock_track
            
            result = await handle_playback("get")
            
            mock_client.get_current_track.assert_called_once()
            assert "Test Song" in result

    @pytest.mark.asyncio
    async def test_handle_playback_get_no_track(self):
        """Test handle_playback get action with no current track."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.return_value = None
            
            result = await handle_playback("get")
            
            assert result == "No track playing."

    @pytest.mark.asyncio
    async def test_handle_playback_start(self):
        """Test handle_playback with start action."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_playback("start", "spotify:track:123")
            
            mock_client.start_playback.assert_called_once_with(spotify_uri="spotify:track:123")
            assert result == "Playback starting."

    @pytest.mark.asyncio
    async def test_handle_playback_pause(self):
        """Test handle_playback with pause action."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_playback("pause")
            
            mock_client.pause_playback.assert_called_once()
            assert result == "Playback paused."

    @pytest.mark.asyncio
    async def test_handle_playback_skip(self):
        """Test handle_playback with skip action."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_playback("skip", num_skips=2)
            
            mock_client.skip_track.assert_called_once_with(n=2)
            assert result == "Skipped to next track."

    @pytest.mark.asyncio
    async def test_handle_playback_unknown_action(self):
        """Test handle_playback with unknown action."""
        result = await handle_playback("unknown")
        assert "Unknown action: unknown" in result

    @pytest.mark.asyncio
    async def test_handle_playback_spotify_exception(self):
        """Test handle_playback with SpotifyException."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.side_effect = SpotifyException(
                http_status=401, code=-1, msg="Unauthorized"
            )
            
            result = await handle_playback("get")
            
            assert "Spotify Client error occurred" in result

    @pytest.mark.asyncio
    async def test_handle_playback_general_exception(self):
        """Test handle_playback with general exception."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.side_effect = Exception("General error")
            
            result = await handle_playback("get")
            
            assert "Unexpected error occurred" in result


class TestHandleSearch:
    """Test cases for handle_search function."""

    @pytest.mark.asyncio
    async def test_handle_search_success(self):
        """Test successful search."""
        mock_results = {
            "tracks": [
                {"name": "Test Song", "artist": "Test Artist"}
            ]
        }
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.return_value = mock_results
            
            result = await handle_search("test query")
            
            mock_client.search.assert_called_once_with(query="test query", qtype="track", limit=10)
            assert "Test Song" in result

    @pytest.mark.asyncio
    async def test_handle_search_with_options(self):
        """Test search with custom options."""
        mock_results = {"artists": []}
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.return_value = mock_results
            
            result = await handle_search("test", qtype="artist", limit=5)
            
            mock_client.search.assert_called_once_with(query="test", qtype="artist", limit=5)

    @pytest.mark.asyncio
    async def test_handle_search_spotify_exception(self):
        """Test search with SpotifyException."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.side_effect = SpotifyException(
                http_status=400, code=-1, msg="Bad request"
            )
            
            result = await handle_search("test")
            
            assert "Spotify Client error occurred" in result

    @pytest.mark.asyncio
    async def test_handle_search_general_exception(self):
        """Test search with general exception."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.side_effect = Exception("Search error")
            
            result = await handle_search("test")
            
            assert "Search error occurred" in result


class TestHandleQueue:
    """Test cases for handle_queue function."""

    @pytest.mark.asyncio
    async def test_handle_queue_add(self):
        """Test adding track to queue."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_queue("add", "track123")
            
            mock_client.add_to_queue.assert_called_once_with("track123")
            assert result == "Track added to queue."

    @pytest.mark.asyncio
    async def test_handle_queue_add_no_track_id(self):
        """Test adding to queue without track ID."""
        result = await handle_queue("add")
        assert "track_id is required for add action" in result

    @pytest.mark.asyncio
    async def test_handle_queue_get(self):
        """Test getting queue."""
        mock_queue = {
            "currently_playing": {"name": "Current Song"},
            "queue": [{"name": "Next Song"}]
        }
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_queue.return_value = mock_queue
            
            result = await handle_queue("get")
            
            mock_client.get_queue.assert_called_once()
            assert "Current Song" in result

    @pytest.mark.asyncio
    async def test_handle_queue_unknown_action(self):
        """Test queue with unknown action."""
        result = await handle_queue("unknown")
        assert "Unknown queue action: unknown" in result

    @pytest.mark.asyncio
    async def test_handle_queue_spotify_exception(self):
        """Test queue with SpotifyException."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.add_to_queue.side_effect = SpotifyException(
                http_status=404, code=-1, msg="Not found"
            )
            
            result = await handle_queue("add", "track123")
            
            assert "Spotify Client error occurred" in result


class TestHandleGetInfo:
    """Test cases for handle_get_info function."""

    @pytest.mark.asyncio
    async def test_handle_get_info_success(self):
        """Test successful get info."""
        mock_info = {
            "name": "Test Item",
            "type": "track"
        }
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_info.return_value = mock_info
            
            result = await handle_get_info("spotify:track:123")
            
            mock_client.get_info.assert_called_once_with(item_uri="spotify:track:123")
            assert "Test Item" in result

    @pytest.mark.asyncio
    async def test_handle_get_info_spotify_exception(self):
        """Test get info with SpotifyException."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_info.side_effect = SpotifyException(
                http_status=404, code=-1, msg="Not found"
            )
            
            result = await handle_get_info("spotify:track:123")
            
            assert "Spotify Client error occurred" in result

    @pytest.mark.asyncio
    async def test_handle_get_info_general_exception(self):
        """Test get info with general exception."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_info.side_effect = Exception("Info error")
            
            result = await handle_get_info("spotify:track:123")
            
            assert "Get info error" in result


class TestHandlePlaylist:
    """Test cases for handle_playlist function."""

    @pytest.mark.asyncio
    async def test_handle_playlist_get(self):
        """Test getting playlists."""
        mock_playlists = [
            {"name": "Playlist 1", "id": "playlist1"},
            {"name": "Playlist 2", "id": "playlist2"}
        ]
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_user_playlists.return_value = mock_playlists
            
            result = await handle_playlist("get")
            
            mock_client.get_current_user_playlists.assert_called_once()
            assert "Playlist 1" in result

    @pytest.mark.asyncio
    async def test_handle_playlist_get_tracks(self):
        """Test getting playlist tracks."""
        mock_tracks = [
            {"name": "Track 1", "id": "track1"},
            {"name": "Track 2", "id": "track2"}
        ]
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_playlist_tracks.return_value = mock_tracks
            
            result = await handle_playlist("get_tracks", playlist_id="playlist123")
            
            mock_client.get_playlist_tracks.assert_called_once_with("playlist123")
            assert "Track 1" in result

    @pytest.mark.asyncio
    async def test_handle_playlist_get_tracks_no_id(self):
        """Test getting playlist tracks without playlist ID."""
        result = await handle_playlist("get_tracks")
        assert "playlist_id is required for get_tracks action" in result

    @pytest.mark.asyncio
    async def test_handle_playlist_add_tracks(self):
        """Test adding tracks to playlist."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_playlist(
                "add_tracks",
                playlist_id="playlist123",
                track_ids=["track1", "track2"]
            )
            
            mock_client.add_tracks_to_playlist.assert_called_once_with(
                playlist_id="playlist123",
                track_ids=["track1", "track2"]
            )
            assert result == "Tracks added to playlist."

    @pytest.mark.asyncio
    async def test_handle_playlist_add_tracks_missing_params(self):
        """Test adding tracks without required parameters."""
        result = await handle_playlist("add_tracks", playlist_id="playlist123")
        assert "playlist_id and track_ids are required" in result

    @pytest.mark.asyncio
    async def test_handle_playlist_remove_tracks(self):
        """Test removing tracks from playlist."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_playlist(
                "remove_tracks",
                playlist_id="playlist123",
                track_ids=["track1", "track2"]
            )
            
            mock_client.remove_tracks_from_playlist.assert_called_once_with(
                playlist_id="playlist123",
                track_ids=["track1", "track2"]
            )
            assert result == "Tracks removed from playlist."

    @pytest.mark.asyncio
    async def test_handle_playlist_change_details(self):
        """Test changing playlist details."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            result = await handle_playlist(
                "change_details",
                playlist_id="playlist123",
                name="New Name",
                description="New Description"
            )
            
            mock_client.change_playlist_details.assert_called_once_with(
                playlist_id="playlist123",
                name="New Name",
                description="New Description"
            )
            assert result == "Playlist details changed."

    @pytest.mark.asyncio
    async def test_handle_playlist_change_details_no_changes(self):
        """Test changing playlist details without name or description."""
        result = await handle_playlist("change_details", playlist_id="playlist123")
        assert "At least one of name or description is required" in result

    @pytest.mark.asyncio
    async def test_handle_playlist_unknown_action(self):
        """Test playlist with unknown action."""
        result = await handle_playlist("unknown")
        assert "Unknown playlist action: unknown" in result

    @pytest.mark.asyncio
    async def test_handle_playlist_spotify_exception(self):
        """Test playlist with SpotifyException."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_user_playlists.side_effect = SpotifyException(
                http_status=403, code=-1, msg="Forbidden"
            )
            
            result = await handle_playlist("get")
            
            assert "Spotify Client error occurred" in result


class TestHandleDevices:
    """Test cases for handle_devices function."""

    @pytest.mark.asyncio
    async def test_handle_devices_success(self):
        """Test successful device listing."""
        mock_devices = [
            {"name": "Device 1", "id": "device1", "is_active": True},
            {"name": "Device 2", "id": "device2", "is_active": False}
        ]
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_devices.return_value = mock_devices
            
            result = await handle_devices()
            
            mock_client.get_devices.assert_called_once()
            assert "Device 1" in result

    @pytest.mark.asyncio
    async def test_handle_devices_with_params(self):
        """Test device listing with parameters (should be ignored)."""
        mock_devices = []
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_devices.return_value = mock_devices
            
            result = await handle_devices({"some": "param"})
            
            mock_client.get_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_devices_spotify_exception(self):
        """Test device listing with SpotifyException."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_devices.side_effect = SpotifyException(
                http_status=500, code=-1, msg="Server error"
            )
            
            result = await handle_devices()
            
            assert "Spotify Client error occurred" in result

    @pytest.mark.asyncio
    async def test_handle_devices_general_exception(self):
        """Test device listing with general exception."""
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_devices.side_effect = Exception("Device error")
            
            result = await handle_devices()
            
            assert "Error getting devices" in result