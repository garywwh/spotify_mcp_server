"""
Shared test fixtures and configuration for spotify_mcp_server tests.
"""

import pytest
from unittest.mock import Mock, patch
import os


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def mock_spotify_client():
    """Create a mock Spotify client for testing."""
    client = Mock()
    client.auth_ok.return_value = True
    client.is_active_device.return_value = True
    client.username = "testuser"
    return client


@pytest.fixture
def sample_track():
    """Sample track data for testing."""
    return {
        'name': 'Test Song',
        'id': 'track123',
        'artists': [{'name': 'Test Artist', 'id': 'artist123'}],
        'album': {
            'name': 'Test Album',
            'id': 'album123',
            'artists': [{'name': 'Test Artist'}]
        },
        'duration_ms': 180000,
        'track_number': 1,
        'is_playable': True
    }


@pytest.fixture
def sample_artist():
    """Sample artist data for testing."""
    return {
        'name': 'Test Artist',
        'id': 'artist123',
        'genres': ['rock', 'pop'],
        'followers': {'total': 1000000}
    }


@pytest.fixture
def sample_album():
    """Sample album data for testing."""
    return {
        'name': 'Test Album',
        'id': 'album123',
        'artists': [{'name': 'Test Artist', 'id': 'artist123'}],
        'tracks': {
            'items': [
                {
                    'name': 'Track 1',
                    'id': 'track1',
                    'artists': [{'name': 'Test Artist'}]
                }
            ]
        },
        'total_tracks': 10,
        'release_date': '2023-01-01',
        'genres': ['rock']
    }


@pytest.fixture
def sample_playlist():
    """Sample playlist data for testing."""
    return {
        'name': 'Test Playlist',
        'id': 'playlist123',
        'owner': {'display_name': 'testuser'},
        'tracks': {
            'total': 2,
            'items': [
                {
                    'track': {
                        'name': 'Playlist Song 1',
                        'id': 'song1',
                        'artists': [{'name': 'Artist 1'}]
                    }
                },
                {
                    'track': {
                        'name': 'Playlist Song 2',
                        'id': 'song2',
                        'artists': [{'name': 'Artist 2'}]
                    }
                }
            ]
        },
        'description': 'Test playlist description'
    }


@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    return {
        'tracks': {
            'items': [
                {
                    'name': 'Search Result 1',
                    'id': 'result1',
                    'artists': [{'name': 'Result Artist 1'}]
                },
                {
                    'name': 'Search Result 2',
                    'id': 'result2',
                    'artists': [{'name': 'Result Artist 2'}]
                }
            ]
        },
        'artists': {
            'items': [
                {
                    'name': 'Artist Result',
                    'id': 'artist_result',
                    'genres': ['pop']
                }
            ]
        },
        'albums': {
            'items': [
                {
                    'name': 'Album Result',
                    'id': 'album_result',
                    'artists': [{'name': 'Album Artist'}]
                }
            ]
        },
        'playlists': {
            'items': [
                {
                    'name': 'Playlist Result',
                    'id': 'playlist_result',
                    'owner': {'display_name': 'testuser'},
                    'tracks': {'total': 5}
                }
            ]
        }
    }


@pytest.fixture
def sample_devices():
    """Sample devices data for testing."""
    return [
        {
            'id': 'device1',
            'name': 'Computer',
            'type': 'Computer',
            'is_active': True,
            'is_private_session': False,
            'is_restricted': False,
            'volume_percent': 50
        },
        {
            'id': 'device2',
            'name': 'Phone',
            'type': 'Smartphone',
            'is_active': False,
            'is_private_session': False,
            'is_restricted': False,
            'volume_percent': 30
        }
    ]


@pytest.fixture
def sample_queue():
    """Sample queue data for testing."""
    return {
        'currently_playing': {
            'name': 'Currently Playing Song',
            'id': 'current123',
            'artists': [{'name': 'Current Artist'}]
        },
        'queue': [
            {
                'name': 'Next Song 1',
                'id': 'next1',
                'artists': [{'name': 'Next Artist 1'}]
            },
            {
                'name': 'Next Song 2',
                'id': 'next2',
                'artists': [{'name': 'Next Artist 2'}]
            }
        ]
    }


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'SPOTIFY_CLIENT_ID': 'test_client_id',
        'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
        'SPOTIFY_REDIRECT_URI': 'http://localhost:8080/callback'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks after each test."""
    yield
    # This fixture runs after each test to ensure clean state


@pytest.fixture
def mock_fastapi_request():
    """Create a mock FastAPI request object."""
    request = Mock()
    request.query_params = Mock()
    return request


@pytest.fixture
def mock_oauth_manager():
    """Create a mock OAuth manager."""
    with patch('spotify_mcp_server.spotify_api._oauth_manager') as mock_manager:
        mock_manager.get_authorize_url.return_value = "https://accounts.spotify.com/authorize?..."
        mock_manager.get_access_token.return_value = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh',
            'expires_in': 3600
        }
        mock_manager.validate_token.return_value = {'access_token': 'valid_token'}
        mock_manager.refresh_access_token.return_value = {'access_token': 'new_token'}
        yield mock_manager


@pytest.fixture
def mock_spotipy():
    """Create a mock spotipy.Spotify instance."""
    with patch('spotify_mcp_server.spotify_api.spotipy.Spotify') as mock_spotify:
        mock_instance = Mock()
        mock_spotify.return_value = mock_instance
        yield mock_instance