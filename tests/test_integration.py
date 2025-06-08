"""
Integration tests for the spotify_mcp_server.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient

from spotify_mcp_server.server import app
from spotify_mcp_server.spotify_helper import normalize_redirect_uri

import os

REDIRECT_URI = None

def get_normalized_redirect_uri():
    global REDIRECT_URI
    REDIRECT_URI = os.environ.get("REDIRECT_URI")
    if REDIRECT_URI:
        REDIRECT_URI = normalize_redirect_uri(REDIRECT_URI)

# Call this at app startup or in main
get_normalized_redirect_uri()


class TestServerIntegration:
    """Integration tests for the MCP server."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_app_creation(self):
        """Test that the FastAPI app is created successfully."""
        assert app is not None
        assert hasattr(app, 'routes')

    def test_callback_route_exists(self):
        """Test that the callback route is registered."""
        route_paths = [route.path for route in app.routes]
        assert "/callback" in route_paths

    def test_callback_endpoint_no_code(self):
        """Test callback endpoint without code parameter."""
        response = self.client.get("/callback")
        assert response.status_code == 400
        assert "No code provided" in response.json()["detail"]

    @patch('spotify_mcp_server.server.handle_oauth_callback')
    def test_callback_endpoint_success(self, mock_handle):
        """Test successful callback endpoint."""
        mock_handle.return_value = {"access_token": "test_token"}
        
        response = self.client.get("/callback?code=test_code")
        assert response.status_code == 200
        assert response.json()["status"] == "Authentication successful"
        mock_handle.assert_called_once_with("test_code")

    @patch('spotify_mcp_server.server.handle_oauth_callback')
    def test_callback_endpoint_error(self, mock_handle):
        """Test callback endpoint with error."""
        mock_handle.side_effect = Exception("OAuth error")
        
        response = self.client.get("/callback?code=test_code")
        assert response.status_code == 500
        assert "OAuth error" in response.json()["detail"]


class TestMCPToolsIntegration:
    """Integration tests for MCP tools."""

    @pytest.mark.asyncio
    async def test_playback_tool_integration(self):
        """Test playback tool integration."""
        from spotify_mcp_server.server import handle_playback
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.return_value = {
                "name": "Test Song",
                "artist": "Test Artist"
            }
            
            result = await handle_playback("get")
            assert isinstance(result, str)
            data = json.loads(result)
            assert data["name"] == "Test Song"

    @pytest.mark.asyncio
    async def test_search_tool_integration(self):
        """Test search tool integration."""
        from spotify_mcp_server.server import handle_search
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.return_value = {
                "tracks": [
                    {"name": "Search Result", "artist": "Search Artist"}
                ]
            }
            
            result = await handle_search("test query")
            assert isinstance(result, str)
            data = json.loads(result)
            assert "tracks" in data

    @pytest.mark.asyncio
    async def test_queue_tool_integration(self):
        """Test queue tool integration."""
        from spotify_mcp_server.server import handle_queue
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_queue.return_value = {
                "currently_playing": {"name": "Current"},
                "queue": [{"name": "Next"}]
            }
            
            result = await handle_queue("get")
            assert isinstance(result, str)
            data = json.loads(result)
            assert "currently_playing" in data

    @pytest.mark.asyncio
    async def test_playlist_tool_integration(self):
        """Test playlist tool integration."""
        from spotify_mcp_server.server import handle_playlist
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_user_playlists.return_value = [
                {"name": "My Playlist", "id": "playlist123"}
            ]
            
            result = await handle_playlist("get")
            assert isinstance(result, str)
            data = json.loads(result)
            assert len(data) == 1
            assert data[0]["name"] == "My Playlist"

    @pytest.mark.asyncio
    async def test_devices_tool_integration(self):
        """Test devices tool integration."""
        from spotify_mcp_server.server import handle_devices
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_devices.return_value = [
                {"name": "Computer", "id": "device123", "is_active": True}
            ]
            
            result = await handle_devices()
            assert isinstance(result, str)
            data = json.loads(result)
            assert len(data) == 1
            assert data[0]["name"] == "Computer"

    @pytest.mark.asyncio
    async def test_get_info_tool_integration(self):
        """Test get info tool integration."""
        from spotify_mcp_server.server import handle_get_info
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_info.return_value = {
                "name": "Track Info",
                "type": "track"
            }
            
            result = await handle_get_info("spotify:track:123")
            assert isinstance(result, str)
            data = json.loads(result)
            assert data["name"] == "Track Info"


class TestErrorHandling:
    """Integration tests for error handling."""

    @pytest.mark.asyncio
    async def test_spotify_exception_handling(self):
        """Test handling of Spotify exceptions across tools."""
        from spotify_mcp_server.server import handle_playback
        from spotipy import SpotifyException
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.side_effect = SpotifyException(
                http_status=401, code=-1, msg="Unauthorized"
            )
            
            result = await handle_playback("get")
            assert "Spotify Client error occurred" in result
            assert "Unauthorized" in result

    @pytest.mark.asyncio
    async def test_general_exception_handling(self):
        """Test handling of general exceptions."""
        from spotify_mcp_server.server import handle_search
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.side_effect = Exception("Network error")
            
            result = await handle_search("test")
            assert "Search error occurred" in result
            assert "Network error" in result

    @pytest.mark.asyncio
    async def test_validation_error_handling(self):
        """Test handling of validation errors."""
        from spotify_mcp_server.server import handle_queue
        
        # Test missing required parameter
        result = await handle_queue("add")  # Missing track_id
        assert "track_id is required" in result

    @pytest.mark.asyncio
    async def test_invalid_action_handling(self):
        """Test handling of invalid actions."""
        from spotify_mcp_server.server import handle_playback
        
        result = await handle_playback("invalid_action")
        assert "Unknown action" in result


class TestDataFlow:
    """Integration tests for data flow between components."""

    @pytest.mark.asyncio
    async def test_search_to_playback_flow(self):
        """Test flow from search to playback."""
        from spotify_mcp_server.server import handle_search, handle_playback
        
        # Mock search results
        search_results = {
            "tracks": [
                {
                    "name": "Found Song",
                    "id": "found123",
                    "uri": "spotify:track:found123"
                }
            ]
        }
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.search.return_value = search_results
            
            # Search for a track
            search_result = await handle_search("test song")
            search_data = json.loads(search_result)
            
            # Use the found track for playback
            track_uri = f"spotify:track:{search_data['tracks'][0]['id']}"
            playback_result = await handle_playback("start", track_uri)
            
            mock_client.start_playback.assert_called_once_with(spotify_uri=track_uri)
            assert "Playback starting" in playback_result

    @pytest.mark.asyncio
    async def test_playlist_management_flow(self):
        """Test complete playlist management flow."""
        from spotify_mcp_server.server import handle_playlist
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            # Get playlists
            mock_client.get_current_user_playlists.return_value = [
                {"name": "Test Playlist", "id": "playlist123"}
            ]
            
            playlists_result = await handle_playlist("get")
            playlists_data = json.loads(playlists_result)
            playlist_id = playlists_data[0]["id"]
            
            # Add tracks to playlist
            add_result = await handle_playlist(
                "add_tracks",
                playlist_id=playlist_id,
                track_ids=["track1", "track2"]
            )
            
            mock_client.add_tracks_to_playlist.assert_called_once_with(
                playlist_id=playlist_id,
                track_ids=["track1", "track2"]
            )
            assert "Tracks added to playlist" in add_result

    @pytest.mark.asyncio
    async def test_queue_management_flow(self):
        """Test queue management flow."""
        from spotify_mcp_server.server import handle_queue
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            # Add track to queue
            add_result = await handle_queue("add", "track123")
            mock_client.add_to_queue.assert_called_once_with("track123")
            assert "Track added to queue" in add_result
            
            # Get queue
            mock_client.get_queue.return_value = {
                "currently_playing": {"name": "Current"},
                "queue": [{"name": "track123"}]
            }
            
            queue_result = await handle_queue("get")
            queue_data = json.loads(queue_result)
            assert "currently_playing" in queue_data
            assert len(queue_data["queue"]) == 1


class TestConcurrency:
    """Integration tests for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test concurrent tool calls don't interfere."""
        import asyncio
        from spotify_mcp_server.server import handle_playback, handle_search
        
        with patch('spotify_mcp_server.server.spotify_client') as mock_client:
            mock_client.get_current_track.return_value = {"name": "Current"}
            mock_client.search.return_value = {"tracks": [{"name": "Search"}]}
            
            # Run multiple operations concurrently
            tasks = [
                handle_playback("get"),
                handle_search("test"),
                handle_playback("get"),
                handle_search("another test")
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All operations should complete successfully
            assert len(results) == 4
            assert all(isinstance(result, str) for result in results)
            
            # Check that both types of operations were called
            assert mock_client.get_current_track.call_count == 2
            assert mock_client.search.call_count == 2


class TestConfiguration:
    """Integration tests for configuration and setup."""

    def test_logger_setup(self):
        """Test logger setup and functionality."""
        from spotify_mcp_server.logging_config import setup_logging
        
        logger = setup_logging("test_logger")
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        
        # Test that logger methods are callable
        logger.info("Test message")
        logger.error("Test error")

    def test_redirect_uri_normalization(self):
        """Test redirect URI normalization functionality."""
        from spotify_mcp_server.spotify_helper import normalize_redirect_uri
        
        # Test that the normalize_redirect_uri function exists and works
        test_uri = "http://localhost:8080/callback"
        normalized = normalize_redirect_uri(test_uri)
        
        # The function should return a normalized URI
        assert isinstance(normalized, str)
        assert "callback" in normalized
        
        # Test with a URI that needs normalization
        test_uri_with_port = "http://localhost:3000/callback"
        normalized_with_port = normalize_redirect_uri(test_uri_with_port)
        assert isinstance(normalized_with_port, str)

    def test_tool_model_schema_generation(self):
        """Test that tool models generate proper schemas."""
        from spotify_mcp_server.server import Playback, Search, Queue
        
        # Test schema generation
        playback_tool = Playback.as_tool()
        assert playback_tool.name == "SpotifyPlayback"
        assert playback_tool.description is not None
        assert playback_tool.inputSchema is not None
        
        search_tool = Search.as_tool()
        assert search_tool.name == "SpotifySearch"
        assert search_tool.inputSchema is not None
        
        queue_tool = Queue.as_tool()
        assert queue_tool.name == "SpotifyQueue"
        assert queue_tool.inputSchema is not None