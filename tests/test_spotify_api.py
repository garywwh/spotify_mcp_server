"""
Unit tests for the spotify_api module.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from spotipy import SpotifyException
import os

from spotify_mcp_server.spotify_api import Client, handle_oauth_callback


class TestHandleOauthCallback:
    """Test cases for handle_oauth_callback function."""

    @patch('spotify_mcp_server.spotify_api._oauth_manager')
    def test_handle_oauth_callback_success(self, mock_oauth_manager):
        """Test successful OAuth callback handling."""
        mock_token_info = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_in': 3600
        }
        mock_oauth_manager.get_access_token.return_value = mock_token_info

        result = handle_oauth_callback("test_code")
        
        mock_oauth_manager.get_access_token.assert_called_once_with("test_code", as_dict=True, check_cache=False)
        assert result == mock_token_info

    @patch('spotify_mcp_server.spotify_api._oauth_manager')
    def test_handle_oauth_callback_exception(self, mock_oauth_manager):
        """Test OAuth callback handling with exception."""
        mock_oauth_manager.get_access_token.side_effect = Exception("OAuth error")

        with pytest.raises(Exception, match="OAuth error"):
            handle_oauth_callback("test_code")


class TestClient:
    """Test cases for the Client class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock()
        
        # Mock the OAuth manager and Spotify client during initialization
        with patch('spotify_mcp_server.spotify_api._oauth_manager') as mock_oauth, \
             patch('spotify_mcp_server.spotify_api.spotipy.Spotify') as mock_spotify:
            
            # Mock a valid cached token
            mock_oauth.cache_handler.get_cached_token.return_value = {
                'access_token': 'test_token',
                'expires_at': time.time() + 3600
            }
            
            # Mock successful user verification
            mock_spotify_instance = Mock()
            mock_spotify.return_value = mock_spotify_instance
            mock_spotify_instance.current_user.return_value = {'id': 'test_user'}
            
            self.client = Client(self.mock_logger)
        
        # After initialization, replace the sp attribute with a fresh mock for testing
        # This allows us to test the actual Client methods while mocking only the Spotify API calls
        self.mock_spotify_instance = Mock()
        self.client.sp = self.mock_spotify_instance

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_client_initialization(self, mock_spotify):
        """Test client initialization."""
        assert self.client.logger == self.mock_logger
        assert self.client.username is None

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_set_username(self, mock_spotify):
        """Test setting username."""
        mock_spotify_instance = Mock()
        mock_spotify_instance.current_user.return_value = {'display_name': 'testuser'}
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock the client's sp attribute to use our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        
        self.client.set_username()
        assert self.client.username == 'testuser'

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    @patch('spotify_mcp_server.spotify_helper.parse_search_results')
    def test_search(self, mock_parse_results, mock_spotify):
        """Test search functionality."""
        mock_spotify_instance = Mock()
        mock_search_results = {
            'tracks': {
                'items': [
                    {
                        'name': 'Test Song',
                        'id': 'track123',
                        'artists': [{'name': 'Test Artist'}]
                    }
                ]
            }
        }
        mock_spotify_instance.search.return_value = mock_search_results
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock the parse_search_results function
        mock_parse_results.return_value = {'tracks': ['parsed_track_data']}
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        self.client.set_username = Mock()
        self.client.username = 'testuser'
        
        result = self.client.search("test query")
        
        mock_spotify_instance.search.assert_called_once()
        assert 'tracks' in result

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    @patch('spotify_mcp_server.spotify_helper.parse_track')
    def test_get_current_track(self, mock_parse_track, mock_spotify):
        """Test getting current track."""
        mock_spotify_instance = Mock()
        mock_current_track = {
            'item': {
                'name': 'Current Song',
                'id': 'current123',
                'artists': [{'name': 'Current Artist'}]
            },
            'is_playing': True,
            'currently_playing_type': 'track'
        }
        mock_spotify_instance.current_user_playing_track.return_value = mock_current_track
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock the parse_track function
        mock_parse_track.return_value = {
            'name': 'Current Song',
            'id': 'current123',
            'artist': 'Current Artist'
        }
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        result = self.client.get_current_track()
        
        assert result['name'] == 'Current Song'
        assert result['is_playing'] is True

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_get_current_track_no_playback(self, mock_spotify):
        """Test getting current track when nothing is playing."""
        mock_spotify_instance = Mock()
        mock_spotify_instance.current_playback.return_value = None
        mock_spotify.return_value = mock_spotify_instance
        
        with patch.object(self.client, 'auth_ok', return_value=True), \
             patch.object(self.client, 'is_active_device', return_value=True):
            result = self.client.get_current_track()
        
        assert result is None

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_start_playback(self, mock_spotify):
        """Test starting playback."""
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        
        self.client.start_playback("spotify:track:123")
        
        mock_spotify_instance.start_playback.assert_called_once()

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_pause_playback(self, mock_spotify):
        """Test pausing playback."""
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        
        self.client.pause_playback()
        
        mock_spotify_instance.pause_playback.assert_called_once()

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_add_to_queue(self, mock_spotify):
        """Test adding track to queue."""
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        
        self.client.add_to_queue("track123")
        
        mock_spotify_instance.add_to_queue.assert_called_once_with("spotify:track:track123", None)

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_get_queue(self, mock_spotify):
        """Test getting playback queue."""
        mock_spotify_instance = Mock()
        mock_queue = {
            'currently_playing': {
                'name': 'Current Song',
                'id': 'current123',
                'artists': [{'name': 'Current Artist'}]
            },
            'queue': [
                {
                    'name': 'Next Song',
                    'id': 'next123',
                    'artists': [{'name': 'Next Artist'}]
                }
            ]
        }
        mock_spotify_instance.queue.return_value = mock_queue
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        
        result = self.client.get_queue()
        
        assert 'currently_playing' in result
        assert 'queue' in result

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    @patch('spotify_mcp_server.spotify_helper.parse_playlist')
    def test_get_current_user_playlists(self, mock_parse_playlist, mock_spotify):
        """Test getting user playlists."""
        mock_spotify_instance = Mock()
        mock_playlists = {
            'items': [
                {
                    'name': 'Test Playlist',
                    'id': 'playlist123',
                    'owner': {'display_name': 'testuser'},
                    'tracks': {'total': 10}
                }
            ]
        }
        mock_spotify_instance.current_user_playlists.return_value = mock_playlists
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock the parse_playlist function
        mock_parse_playlist.return_value = {
            'name': 'Test Playlist',
            'id': 'playlist123',
            'owner': 'testuser',
            'tracks': 10
        }
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        self.client.username = 'testuser'
        
        result = self.client.get_current_user_playlists()
        
        assert len(result) == 1
        assert result[0]['name'] == 'Test Playlist'

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    @patch('spotify_mcp_server.spotify_helper.parse_tracks')
    def test_get_playlist_tracks(self, mock_parse_tracks, mock_spotify):
        """Test getting playlist tracks."""
        mock_spotify_instance = Mock()
        mock_playlist = {
            'tracks': {
                'items': [
                    {
                        'track': {
                            'name': 'Playlist Song',
                            'id': 'song123',
                            'artists': [{'name': 'Playlist Artist'}]
                        }
                    }
                ]
            }
        }
        mock_spotify_instance.playlist.return_value = mock_playlist
        mock_spotify.return_value = mock_spotify_instance
        
        # Mock the parse_tracks function
        mock_parse_tracks.return_value = [
            {
                'name': 'Playlist Song',
                'id': 'song123',
                'artist': 'Playlist Artist'
            }
        ]
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.ensure_username decorator
        self.client.username = 'testuser'
        
        result = self.client.get_playlist_tracks("playlist123")
        
        assert len(result) == 1
        assert result[0]['name'] == 'Playlist Song'

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_add_tracks_to_playlist(self, mock_spotify):
        """Test adding tracks to playlist."""
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.ensure_username decorator
        self.client.username = 'testuser'
        
        self.client.add_tracks_to_playlist("playlist123", ["track1", "track2"])
        
        mock_spotify_instance.playlist_add_items.assert_called_once()

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_remove_tracks_from_playlist(self, mock_spotify):
        """Test removing tracks from playlist."""
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.ensure_username decorator
        self.client.username = 'testuser'
        
        self.client.remove_tracks_from_playlist("playlist123", ["track1", "track2"])
        
        mock_spotify_instance.playlist_remove_all_occurrences_of_items.assert_called_once()

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_change_playlist_details(self, mock_spotify):
        """Test changing playlist details."""
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.ensure_username decorator
        self.client.username = 'testuser'
        
        self.client.change_playlist_details("playlist123", name="New Name", description="New Description")
        
        mock_spotify_instance.playlist_change_details.assert_called_once()

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_get_devices(self, mock_spotify):
        """Test getting available devices."""
        mock_spotify_instance = Mock()
        mock_devices = {
            'devices': [
                {
                    'id': 'device123',
                    'name': 'Test Device',
                    'type': 'Computer',
                    'is_active': True
                }
            ]
        }
        mock_spotify_instance.devices.return_value = mock_devices
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        self.client.is_active_device = Mock(return_value=True)
        
        result = self.client.get_devices()
        
        assert len(result) == 1
        assert result[0]['name'] == 'Test Device'

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_is_active_device(self, mock_spotify):
        """Test checking if device is active."""
        mock_spotify_instance = Mock()
        mock_devices = {
            'devices': [
                {
                    'id': 'device123',
                    'name': 'Test Device',
                    'is_active': True
                }
            ]
        }
        mock_spotify_instance.devices.return_value = mock_devices
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        
        result = self.client.is_active_device()
        
        assert result is True

    @patch('spotify_mcp_server.spotify_api.spotipy.Spotify')
    def test_get_candidate_device(self, mock_spotify):
        """Test getting candidate device."""
        mock_spotify_instance = Mock()
        mock_devices = {
            'devices': [
                {
                    'id': 'device123',
                    'name': 'Test Device',
                    'is_active': False
                }
            ]
        }
        mock_spotify_instance.devices.return_value = mock_devices
        mock_spotify.return_value = mock_spotify_instance
        
        # Set the client's sp attribute to our mock
        self.client.sp = mock_spotify_instance
        
        # Mock the methods called by the @utils.validate decorator
        self.client.auth_ok = Mock(return_value=True)
        
        result = self.client._get_candidate_device()
        
        assert result['id'] == 'device123'

    def test_auth_ok(self):
        """Test authentication check."""
        # Mock cache handler to return a valid token
        mock_token = {
            'access_token': 'valid_token',
            'expires_at': time.time() + 3600  # Valid for 1 hour
        }
        with patch.object(self.client.cache_handler, 'get_cached_token', return_value=mock_token):
            result = self.client.auth_ok()
            assert result is True

    def test_auth_ok_invalid(self):
        """Test authentication check with invalid token."""
        # Mock cache handler to return None (no token)
        with patch.object(self.client.cache_handler, 'get_cached_token', return_value=None):
            result = self.client.auth_ok()
            assert result is False

    def test_auth_ok_expired(self):
        """Test authentication check with expired token."""
        # Mock cache handler to return an expired token
        mock_token = {
            'access_token': 'expired_token',
            'expires_at': time.time() - 3600  # Expired 1 hour ago
        }
        with patch.object(self.client.cache_handler, 'get_cached_token', return_value=mock_token):
            result = self.client.auth_ok()
            assert result is False

    def test_auth_refresh(self):
        """Test authentication refresh."""
        mock_token = {
            'access_token': 'old_token',
            'refresh_token': 'refresh_token'
        }
        mock_new_token = {'access_token': 'new_token'}
        
        with patch.object(self.client.cache_handler, 'get_cached_token', return_value=mock_token), \
             patch.object(self.client.auth_manager, 'refresh_access_token', return_value=mock_new_token) as mock_refresh, \
             patch.object(self.client.cache_handler, 'save_token_to_cache') as mock_save:
            
            result = self.client.auth_refresh()
            
            mock_refresh.assert_called_once_with('refresh_token')
            mock_save.assert_called_once_with(mock_new_token)
            assert result is True

    def test_skip_track(self):
        """Test skipping tracks."""
        self.client.skip_track(2)
        assert self.mock_spotify_instance.next_track.call_count == 2

    def test_previous_track(self):
        """Test going to previous track."""
        self.client.previous_track()
        self.mock_spotify_instance.previous_track.assert_called_once()

    def test_seek_to_position(self):
        """Test seeking to position."""
        self.client.seek_to_position(30000)
        self.mock_spotify_instance.seek_track.assert_called_once_with(position_ms=30000)

    def test_set_volume(self):
        """Test setting volume."""
        self.client.set_volume(50)
        self.mock_spotify_instance.volume.assert_called_once_with(50)

    def test_get_info_track(self):
        """Test getting track info."""
        mock_track = {
            'name': 'Test Track',
            'id': 'track123',
            'artists': [{'name': 'Test Artist', 'id': 'artist123'}],
            'album': {'name': 'Test Album', 'id': 'album123', 'artists': [{'name': 'Test Artist', 'id': 'artist123'}]}
        }
        self.mock_spotify_instance.track.return_value = mock_track
        
        result = self.client.get_info("spotify:track:123")
        assert result['name'] == 'Test Track'

    def test_get_info_artist(self):
        """Test getting artist info."""
        mock_artist = {
            'name': 'Test Artist',
            'id': 'artist123'
        }
        mock_albums = {
            'items': [
                {
                    'name': 'Test Album',
                    'id': 'album123',
                    'artists': [{'name': 'Test Artist'}]
                }
            ]
        }
        mock_top_tracks = {
            'tracks': [
                {
                    'name': 'Top Track',
                    'id': 'track123',
                    'artists': [{'name': 'Test Artist'}]
                }
            ]
        }
        self.mock_spotify_instance.artist.return_value = mock_artist
        self.mock_spotify_instance.artist_albums.return_value = mock_albums
        self.mock_spotify_instance.artist_top_tracks.return_value = mock_top_tracks
        
        result = self.client.get_info("spotify:artist:123")
        
        assert result['name'] == 'Test Artist'
        assert 'albums' in result
        assert 'top_tracks' in result

    def test_spotify_exception_handling(self):
        """Test handling of SpotifyException."""
        self.mock_spotify_instance.current_user_playing_track.side_effect = SpotifyException(
            http_status=401, 
            code=-1, 
            msg="Unauthorized"
        )
        
        with pytest.raises(SpotifyException):
            self.client.get_current_track()

    def test_recommendations(self):
        """Test getting recommendations."""
        mock_recommendations = {
            'tracks': [
                {
                    'name': 'Recommended Track',
                    'id': 'rec123',
                    'artists': [{'name': 'Rec Artist'}]
                }
            ]
        }
        self.mock_spotify_instance.recommendations.return_value = mock_recommendations
        
        result = self.client.recommendations(artists=['artist123'], tracks=['track123'])
        
        assert len(result) == 1
        assert result[0]['name'] == 'Recommended Track'

    def test_get_liked_songs(self):
        """Test getting liked songs."""
        mock_liked_songs = {
            'items': [
                {
                    'track': {
                        'name': 'Liked Song',
                        'id': 'liked123',
                        'artists': [{'name': 'Liked Artist'}]
                    }
                }
            ]
        }
        self.mock_spotify_instance.current_user_saved_tracks.return_value = mock_liked_songs
        
        result = self.client.get_liked_songs()
        
        assert len(result) == 1
        assert result[0]['name'] == 'Liked Song'

    def test_is_track_playing(self):
        """Test checking if track is playing."""
        # Mock current_user_playing_track to return a playing track
        mock_current_track = {
            'currently_playing_type': 'track',
            'is_playing': True,
            'item': {
                'name': 'Test Track',
                'id': 'track123',
                'artists': [{'name': 'Test Artist', 'id': 'artist123'}],
                'album': {'name': 'Test Album', 'id': 'album123', 'artists': [{'name': 'Test Artist', 'id': 'artist123'}]}
            }
        }
        self.mock_spotify_instance.current_user_playing_track.return_value = mock_current_track
        
        result = self.client.is_track_playing()
        
        assert result is True