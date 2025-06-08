"""
Unit tests for the spotify_helper module.
"""

import pytest
from unittest.mock import Mock, patch
from requests import RequestException

from spotify_mcp_server.spotify_helper import (
    normalize_redirect_uri,
    parse_track,
    parse_artist,
    parse_playlist,
    parse_album,
    parse_search_results,
    parse_tracks,
    build_search_query,
    validate,
    ensure_username,
    extract_spotify_id,
    build_spotify_uri,
    validate_spotify_uri,
    format_duration,
    safe_get
)


class TestNormalizeRedirectUri:
    """Test cases for normalize_redirect_uri function."""

    def test_normalize_redirect_uri_empty_url(self):
        """Test with empty URL."""
        assert normalize_redirect_uri("") == ""
        assert normalize_redirect_uri(None) is None

    def test_normalize_redirect_uri_localhost_to_127_0_0_1(self):
        """Test conversion of localhost to 127.0.0.1."""
        url = "http://localhost:8080/callback"
        expected = "http://127.0.0.1:8080/callback"
        assert normalize_redirect_uri(url) == expected

    def test_normalize_redirect_uri_localhost_without_port(self):
        """Test conversion of localhost without port."""
        url = "http://localhost/callback"
        expected = "http://127.0.0.1/callback"
        assert normalize_redirect_uri(url) == expected

    def test_normalize_redirect_uri_non_localhost(self):
        """Test that non-localhost URLs are unchanged."""
        url = "https://example.com:8080/callback"
        assert normalize_redirect_uri(url) == url

    def test_normalize_redirect_uri_https_localhost(self):
        """Test HTTPS localhost conversion."""
        url = "https://localhost:3000/callback"
        expected = "https://127.0.0.1:3000/callback"
        assert normalize_redirect_uri(url) == expected


class TestParseTrack:
    """Test cases for parse_track function."""

    def test_parse_track_none_input(self):
        """Test with None input."""
        assert parse_track(None) is None

    def test_parse_track_basic(self):
        """Test basic track parsing."""
        track_item = {
            'name': 'Test Song',
            'id': 'track123',
            'artists': [{'name': 'Test Artist'}],
            'is_playable': True
        }
        result = parse_track(track_item)
        expected = {
            'name': 'Test Song',
            'id': 'track123',
            'artist': 'Test Artist'
        }
        assert result == expected

    def test_parse_track_with_is_playing(self):
        """Test track parsing with is_playing field."""
        track_item = {
            'name': 'Test Song',
            'id': 'track123',
            'artists': [{'name': 'Test Artist'}],
            'is_playing': True
        }
        result = parse_track(track_item)
        assert result['is_playing'] is True

    def test_parse_track_detailed(self):
        """Test detailed track parsing."""
        track_item = {
            'name': 'Test Song',
            'id': 'track123',
            'artists': [{'name': 'Test Artist', 'id': 'artist123'}],
            'album': {'name': 'Test Album', 'id': 'album123', 'artists': [{'name': 'Test Artist'}]},
            'track_number': 1,
            'duration_ms': 180000
        }
        result = parse_track(track_item, detailed=True)
        assert result['track_number'] == 1
        assert result['duration_ms'] == 180000
        assert 'album' in result

    def test_parse_track_multiple_artists(self):
        """Test track with multiple artists."""
        track_item = {
            'name': 'Test Song',
            'id': 'track123',
            'artists': [
                {'name': 'Artist 1'},
                {'name': 'Artist 2'}
            ]
        }
        result = parse_track(track_item)
        assert result['artists'] == ['Artist 1', 'Artist 2']

    def test_parse_track_not_playable(self):
        """Test track that is not playable."""
        track_item = {
            'name': 'Test Song',
            'id': 'track123',
            'artists': [{'name': 'Test Artist'}],
            'is_playable': False
        }
        result = parse_track(track_item)
        assert result['is_playable'] is False


class TestParseArtist:
    """Test cases for parse_artist function."""

    def test_parse_artist_none_input(self):
        """Test with None input."""
        assert parse_artist(None) is None

    def test_parse_artist_basic(self):
        """Test basic artist parsing."""
        artist_item = {
            'name': 'Test Artist',
            'id': 'artist123'
        }
        result = parse_artist(artist_item)
        expected = {
            'name': 'Test Artist',
            'id': 'artist123'
        }
        assert result == expected

    def test_parse_artist_detailed(self):
        """Test detailed artist parsing."""
        artist_item = {
            'name': 'Test Artist',
            'id': 'artist123',
            'genres': ['rock', 'pop']
        }
        result = parse_artist(artist_item, detailed=True)
        assert result['genres'] == ['rock', 'pop']


class TestParsePlaylist:
    """Test cases for parse_playlist function."""

    def test_parse_playlist_none_input(self):
        """Test with None input."""
        assert parse_playlist(None, "testuser") is None

    def test_parse_playlist_basic(self):
        """Test basic playlist parsing."""
        playlist_item = {
            'name': 'Test Playlist',
            'id': 'playlist123',
            'owner': {'display_name': 'testuser'},
            'tracks': {'total': 10}
        }
        result = parse_playlist(playlist_item, "testuser")
        expected = {
            'name': 'Test Playlist',
            'id': 'playlist123',
            'owner': 'testuser',
            'user_is_owner': True,
            'total_tracks': 10
        }
        assert result == expected

    def test_parse_playlist_not_owner(self):
        """Test playlist parsing when user is not owner."""
        playlist_item = {
            'name': 'Test Playlist',
            'id': 'playlist123',
            'owner': {'display_name': 'otheruser'},
            'tracks': {'total': 10}
        }
        result = parse_playlist(playlist_item, "testuser")
        assert result['user_is_owner'] is False
        assert result['owner'] == 'otheruser'

    def test_parse_playlist_detailed(self):
        """Test detailed playlist parsing."""
        playlist_item = {
            'name': 'Test Playlist',
            'id': 'playlist123',
            'owner': {'display_name': 'testuser'},
            'tracks': {
                'total': 1,
                'items': [
                    {
                        'track': {
                            'name': 'Test Song',
                            'id': 'track123',
                            'artists': [{'name': 'Test Artist'}]
                        }
                    }
                ]
            },
            'description': 'Test description'
        }
        result = parse_playlist(playlist_item, "testuser", detailed=True)
        assert result['description'] == 'Test description'
        assert len(result['tracks']) == 1
        assert result['tracks'][0]['name'] == 'Test Song'


class TestParseAlbum:
    """Test cases for parse_album function."""

    def test_parse_album_basic(self):
        """Test basic album parsing."""
        album_item = {
            'name': 'Test Album',
            'id': 'album123',
            'artists': [{'name': 'Test Artist'}]
        }
        result = parse_album(album_item)
        expected = {
            'name': 'Test Album',
            'id': 'album123',
            'artist': 'Test Artist'
        }
        assert result == expected

    def test_parse_album_multiple_artists(self):
        """Test album with multiple artists."""
        album_item = {
            'name': 'Test Album',
            'id': 'album123',
            'artists': [
                {'name': 'Artist 1'},
                {'name': 'Artist 2'}
            ]
        }
        result = parse_album(album_item)
        assert result['artists'] == ['Artist 1', 'Artist 2']

    def test_parse_album_detailed(self):
        """Test detailed album parsing."""
        album_item = {
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
        result = parse_album(album_item, detailed=True)
        assert result['total_tracks'] == 10
        assert result['release_date'] == '2023-01-01'
        assert result['genres'] == ['rock']
        assert len(result['tracks']) == 1


class TestParseSearchResults:
    """Test cases for parse_search_results function."""

    def test_parse_search_results_tracks(self):
        """Test parsing search results for tracks."""
        results = {
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
        result = parse_search_results(results, "track")
        assert 'tracks' in result
        assert len(result['tracks']) == 1
        assert result['tracks'][0]['name'] == 'Test Song'

    def test_parse_search_results_multiple_types(self):
        """Test parsing search results for multiple types."""
        results = {
            'tracks': {
                'items': [
                    {
                        'name': 'Test Song',
                        'id': 'track123',
                        'artists': [{'name': 'Test Artist'}]
                    }
                ]
            },
            'artists': {
                'items': [
                    {
                        'name': 'Test Artist',
                        'id': 'artist123'
                    }
                ]
            }
        }
        result = parse_search_results(results, "track,artist")
        assert 'tracks' in result
        assert 'artists' in result
        assert len(result['tracks']) == 1
        assert len(result['artists']) == 1

    def test_parse_search_results_invalid_type(self):
        """Test parsing search results with invalid type."""
        results = {'tracks': {'items': []}}
        with pytest.raises(ValueError, match="Unknown query type: invalid"):
            parse_search_results(results, "invalid")

    def test_parse_search_results_empty_items(self):
        """Test parsing search results with empty items."""
        results = {
            'tracks': {
                'items': [None, {
                    'name': 'Test Song',
                    'id': 'track123',
                    'artists': [{'name': 'Test Artist'}]
                }]
            }
        }
        result = parse_search_results(results, "track")
        assert len(result['tracks']) == 1  # None item should be skipped


class TestParseTracks:
    """Test cases for parse_tracks function."""

    def test_parse_tracks_basic(self):
        """Test basic tracks parsing."""
        items = [
            {
                'track': {
                    'name': 'Test Song',
                    'id': 'track123',
                    'artists': [{'name': 'Test Artist'}]
                }
            }
        ]
        result = parse_tracks(items)
        assert len(result) == 1
        assert result[0]['name'] == 'Test Song'

    def test_parse_tracks_with_none_items(self):
        """Test tracks parsing with None items."""
        items = [
            None,
            {
                'track': {
                    'name': 'Test Song',
                    'id': 'track123',
                    'artists': [{'name': 'Test Artist'}]
                }
            }
        ]
        result = parse_tracks(items)
        assert len(result) == 1  # None item should be skipped


class TestBuildSearchQuery:
    """Test cases for build_search_query function."""

    def test_build_search_query_basic(self):
        """Test basic search query building."""
        result = build_search_query("test query")
        assert "test%20query" in result

    def test_build_search_query_with_artist(self):
        """Test search query with artist filter."""
        result = build_search_query("test", artist="Test Artist")
        assert "artist%3ATest%20Artist" in result

    def test_build_search_query_with_multiple_filters(self):
        """Test search query with multiple filters."""
        result = build_search_query(
            "test",
            artist="Test Artist",
            album="Test Album",
            year="2023"
        )
        assert "artist%3ATest%20Artist" in result
        assert "album%3ATest%20Album" in result
        assert "year%3A2023" in result

    def test_build_search_query_with_year_range(self):
        """Test search query with year range."""
        result = build_search_query("test", year_range=(2020, 2023))
        assert "year%3A2020-2023" in result

    def test_build_search_query_with_tags(self):
        """Test search query with special tags."""
        result = build_search_query("test", is_hipster=True, is_new=True)
        assert "tag%3Ahipster" in result
        assert "tag%3Anew" in result


class TestValidateDecorator:
    """Test cases for validate decorator."""

    def test_validate_decorator_auth_refresh(self):
        """Test validate decorator calls auth_refresh when auth not ok."""
        mock_client = Mock()
        mock_client.auth_ok.return_value = False
        mock_client.is_active_device.return_value = True

        @validate
        def test_method(self):
            return "success"

        result = test_method(mock_client)
        mock_client.auth_refresh.assert_called_once()
        assert result == "success"

    def test_validate_decorator_device_validation(self):
        """Test validate decorator handles device validation."""
        mock_client = Mock()
        mock_client.auth_ok.return_value = True
        mock_client.is_active_device.return_value = False
        mock_client._get_candidate_device.return_value = "device123"

        @validate
        def test_method(self, device=None):
            return f"device: {device}"

        result = test_method(mock_client)
        mock_client._get_candidate_device.assert_called_once()
        assert "device: device123" in result

    def test_validate_decorator_request_exception(self):
        """Test validate decorator handles RequestException."""
        mock_client = Mock()
        mock_client.auth_ok.return_value = True
        mock_client.is_active_device.return_value = True
        mock_client.logger = Mock()

        @validate
        def test_method(self):
            raise RequestException("Network error")

        with pytest.raises(RequestException):
            test_method(mock_client)
        mock_client.logger.error.assert_called_once()


class TestEnsureUsernameDecorator:
    """Test cases for ensure_username decorator."""

    def test_ensure_username_decorator_sets_username(self):
        """Test ensure_username decorator sets username when None."""
        mock_client = Mock()
        mock_client.username = None

        @ensure_username
        def test_method(self):
            return "success"

        result = test_method(mock_client)
        mock_client.set_username.assert_called_once()
        assert result == "success"

    def test_ensure_username_decorator_skips_when_set(self):
        """Test ensure_username decorator skips when username already set."""
        mock_client = Mock()
        mock_client.username = "testuser"

        @ensure_username
        def test_method(self):
            return "success"

        result = test_method(mock_client)
        mock_client.set_username.assert_not_called()
        assert result == "success"


class TestExtractSpotifyId:
    """Test cases for extract_spotify_id function."""

    def test_extract_spotify_id_from_uri(self):
        """Test extracting ID from Spotify URI."""
        uri = "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
        result = extract_spotify_id(uri)
        assert result == "4iV5W9uYEdYUVa79Axb7Rh"

    def test_extract_spotify_id_from_plain_id(self):
        """Test extracting ID from plain ID (should return as-is)."""
        track_id = "4iV5W9uYEdYUVa79Axb7Rh"
        result = extract_spotify_id(track_id)
        assert result == "4iV5W9uYEdYUVa79Axb7Rh"

    def test_extract_spotify_id_from_album_uri(self):
        """Test extracting ID from album URI."""
        uri = "spotify:album:1DFixLWuPkv3KT3TnV35m3"
        result = extract_spotify_id(uri)
        assert result == "1DFixLWuPkv3KT3TnV35m3"


class TestBuildSpotifyUri:
    """Test cases for build_spotify_uri function."""

    def test_build_track_uri(self):
        """Test building track URI."""
        result = build_spotify_uri("track", "4iV5W9uYEdYUVa79Axb7Rh")
        assert result == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"

    def test_build_album_uri(self):
        """Test building album URI."""
        result = build_spotify_uri("album", "1DFixLWuPkv3KT3TnV35m3")
        assert result == "spotify:album:1DFixLWuPkv3KT3TnV35m3"

    def test_build_artist_uri(self):
        """Test building artist URI."""
        result = build_spotify_uri("artist", "0TnOYISbd1XYRBk9myaseg")
        assert result == "spotify:artist:0TnOYISbd1XYRBk9myaseg"

    def test_build_playlist_uri(self):
        """Test building playlist URI."""
        result = build_spotify_uri("playlist", "37i9dQZF1DX0XUsuxWHRQd")
        assert result == "spotify:playlist:37i9dQZF1DX0XUsuxWHRQd"


class TestValidateSpotifyUri:
    """Test cases for validate_spotify_uri function."""

    def test_validate_valid_track_uri(self):
        """Test validation of valid track URI."""
        uri = "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
        assert validate_spotify_uri(uri) is True

    def test_validate_valid_album_uri(self):
        """Test validation of valid album URI."""
        uri = "spotify:album:1DFixLWuPkv3KT3TnV35m3"
        assert validate_spotify_uri(uri) is True

    def test_validate_valid_artist_uri(self):
        """Test validation of valid artist URI."""
        uri = "spotify:artist:0TnOYISbd1XYRBk9myaseg"
        assert validate_spotify_uri(uri) is True

    def test_validate_valid_playlist_uri(self):
        """Test validation of valid playlist URI."""
        uri = "spotify:playlist:37i9dQZF1DX0XUsuxWHRQd"
        assert validate_spotify_uri(uri) is True

    def test_validate_invalid_prefix(self):
        """Test validation of URI with invalid prefix."""
        uri = "invalid:track:4iV5W9uYEdYUVa79Axb7Rh"
        assert validate_spotify_uri(uri) is False

    def test_validate_invalid_type(self):
        """Test validation of URI with invalid type."""
        uri = "spotify:invalid:4iV5W9uYEdYUVa79Axb7Rh"
        assert validate_spotify_uri(uri) is False

    def test_validate_invalid_id_length(self):
        """Test validation of URI with invalid ID length."""
        uri = "spotify:track:short"
        assert validate_spotify_uri(uri) is False

    def test_validate_invalid_format(self):
        """Test validation of URI with invalid format."""
        uri = "spotify:track"
        assert validate_spotify_uri(uri) is False

    def test_validate_empty_string(self):
        """Test validation of empty string."""
        assert validate_spotify_uri("") is False

    def test_validate_none(self):
        """Test validation of None."""
        assert validate_spotify_uri(None) is False


class TestFormatDuration:
    """Test cases for format_duration function."""

    def test_format_duration_seconds_only(self):
        """Test formatting duration with seconds only."""
        duration_ms = 45000  # 45 seconds
        result = format_duration(duration_ms)
        assert result == "0:45"

    def test_format_duration_minutes_and_seconds(self):
        """Test formatting duration with minutes and seconds."""
        duration_ms = 225000  # 3 minutes 45 seconds
        result = format_duration(duration_ms)
        assert result == "3:45"

    def test_format_duration_with_hours(self):
        """Test formatting duration with hours."""
        duration_ms = 4425000  # 1 hour 13 minutes 45 seconds
        result = format_duration(duration_ms)
        assert result == "1:13:45"

    def test_format_duration_zero(self):
        """Test formatting zero duration."""
        result = format_duration(0)
        assert result == "0:00"

    def test_format_duration_negative(self):
        """Test formatting negative duration."""
        result = format_duration(-1000)
        assert result == "0:00"

    def test_format_duration_none(self):
        """Test formatting None duration."""
        result = format_duration(None)
        assert result == "0:00"


class TestSafeGet:
    """Test cases for safe_get function."""

    def test_safe_get_existing_path(self):
        """Test safe_get with existing key path."""
        data = {"a": {"b": {"c": "value"}}}
        result = safe_get(data, "a", "b", "c")
        assert result == "value"

    def test_safe_get_missing_key(self):
        """Test safe_get with missing key."""
        data = {"a": {"b": {}}}
        result = safe_get(data, "a", "b", "c")
        assert result is None

    def test_safe_get_with_default(self):
        """Test safe_get with custom default value."""
        data = {"a": {"b": {}}}
        result = safe_get(data, "a", "b", "c", default="not found")
        assert result == "not found"

    def test_safe_get_single_key(self):
        """Test safe_get with single key."""
        data = {"key": "value"}
        result = safe_get(data, "key")
        assert result == "value"

    def test_safe_get_empty_dict(self):
        """Test safe_get with empty dictionary."""
        data = {}
        result = safe_get(data, "key")
        assert result is None

    def test_safe_get_non_dict_intermediate(self):
        """Test safe_get when intermediate value is not a dict."""
        data = {"a": "not_a_dict"}
        result = safe_get(data, "a", "b", "c")
        assert result is None