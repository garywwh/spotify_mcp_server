# Spotify MCP Server

A MCP (Model Context Protocol) server for controlling Spotify playback, searching for content, and managing playlists.

## Features

- OAuth authentication with Spotify
- Playback control (play, pause, skip, queue management)
- Search for tracks, albums, artists, and playlists
- Playlist management (create, edit, add/remove tracks)
- Device management

## Prerequisites

- Python 3.10+
- Spotify Developer Account
- Spotify Premium Account (required for playback control)

## Setup

### Spotify Developer Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add `http://127.0.0.1:8080/callback` to your app's redirect URIs
4. Note your Client ID and Client Secret

### Environment Variables

Create a `.env` file in the project root with the following variables:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/callback
```

### Installation

1. Install dependencies:

```bash
pip install -e .
```

2. Run the server:

```bash
python -m spotify_mcp_server.server
```

Or using uvicorn directly:

```bash
uvicorn spotify_mcp_server.server:app --host 0.0.0.0 --port 8080
```

3. Follow the authentication instructions printed in the console

## Usage

The server exposes several MCP tools that can be used to control Spotify:

- `SpotifyPlayback`: Control playback (get current track, start, pause, skip)
- `SpotifySearch`: Search for tracks, albums, artists, or playlists
- `SpotifyQueue`: Manage the playback queue
- `SpotifyGetInfo`: Get detailed information about Spotify items
- `SpotifyPlaylist`: Manage playlists
- `SpotifyDevices`: Get available devices

## Project Structure

The server consists of several modules located in `src/spotify_mcp_server/`:

- `server.py`: FastMCP server implementation with MCP tool handlers
- `spotify_api.py`: Spotify API client with OAuth handling and API interactions
- `spotify_helper.py`: Comprehensive helper functions and utilities
- `logging_config.py`: Structured logging configuration

## Authentication Flow

1. Start the server
2. Open the OAuth URL printed in the console
3. Authenticate with Spotify
4. The server will cache your authentication token
5. Server is ready to handle MCP requests

## Testing

The project includes comprehensive unit and integration tests.

### Installing Test Dependencies

To install the package with test dependencies:

```bash
# Install in editable mode with test dependencies
pip install -e ".[test]"
```

### Running Tests

**Quick test run:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=src/spotify_mcp_server --cov-report=term-missing --cov-report=html
```

**Run specific test types:**
```bash
# Unit tests only
pytest tests/test_spotify_helper.py tests/test_spotify_api.py tests/test_server.py

# Integration tests only
pytest tests/test_integration.py

# Specific test file
pytest tests/test_spotify_helper.py

# Specific test function
pytest tests/test_spotify_helper.py::TestNormalizeRedirectUri::test_normalize_redirect_uri_localhost_to_127_0_0_1
```

**Using the test runner script:**
```bash
# Run all tests with coverage
python run_tests.py --coverage

# Run only unit tests
python run_tests.py --type unit

# Run only integration tests
python run_tests.py --type integration

# Fast run without coverage
python run_tests.py --fast

# Verbose output
python run_tests.py --verbose

# Run specific test file
python run_tests.py --file test_spotify_helper.py

# Run specific test function
python run_tests.py --function test_normalize_redirect_uri
```

## Inspired by
Inspired by the work of varunneal on his [spotify-mcp](https://github.com/varunneal/spotify-mcp)
