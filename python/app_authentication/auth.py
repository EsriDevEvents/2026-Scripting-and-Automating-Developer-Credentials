"""
auth.py handles authentication negotiation with ArcGIS.
"""
import os
import time
import json
import logging
import sys
from arcgis import GIS
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ============================================================================
# Constants
# ============================================================================

MS_PER_SECOND = 1000
MS_PER_MINUTE = 60 * 1000
MS_PER_HOUR = 60 * 60 * 1000


# ============================================================================
# Configuration
# ============================================================================

def load_configuration():
    """
    Load configuration from server-configuration.json file.
    
    Returns:
        dict: Configuration dictionary
        
    Raises:
        FileNotFoundError: If configuration file does not exist
        json.JSONDecodeError: If configuration file is not valid JSON
    """
    config_path = Path(__file__).parent / "server-configuration.json"
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in configuration file {config_path}: {e.msg}", e.doc, e.pos)


# Load environment variables and configuration
load_dotenv()
configuration = load_configuration()


# ============================================================================
# Utility & Helper Functions
# ============================================================================

def is_arcgis_error(arcgis_server_response):
    """
    Determine if a response from the ArcGIS server is an error, since the server seems to always send
    back status 200 and the error is in the JSON response but it only appears if there is an error.
    
    Args:
        arcgis_server_response (dict): An object returned from a failed ArcGIS service endpoint
        
    Returns:
        bool: True if arcgis_server_response looks like an error, False if it does not
    """
    return (
        arcgis_server_response is None
        or "error" in arcgis_server_response
    )


def error_response(error_code, error_message):
    """
    Format an error response so it looks the same as an ArcGIS error for errors that happen in this service.
    This should help clients handle errors with just one consistent format.
    
    Args:
        error_code (int): An HTTP status code to report
        error_message (str): An error message to help explain what went wrong
        
    Returns:
        dict: Formatted error response
    """
    return {
        "error": {
            "code": error_code,
            "error": "invalid_server_response",
            "error_description": f"Invalid server response: {error_message}",
            "message": f"Invalid server response: {error_message}",
            "details": [],
        }
    }


def format_time_remaining(remaining_ms: int) -> str:
    """
    Format remaining milliseconds as a human-readable time string.
    
    Args:
        remaining_ms (int): Time in milliseconds
        
    Returns:
        str: Formatted time string in HH:MM:SS format
    """
    hours = remaining_ms // MS_PER_HOUR
    minutes = (remaining_ms // MS_PER_MINUTE) % 60
    seconds = (remaining_ms // 1000) % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def is_token_expired(token: dict) -> bool:
    """
    Check if a token has expired based on its expiresDate field.
    
    Args:
        token (dict): Token object with expiresDate field (in milliseconds)
        
    Returns:
        bool: True if token has expired, False otherwise
    """
    return int(time.time() * 1000) > token["expiresDate"]


# ============================================================================
# Cache Management Functions
# ============================================================================

def cache_response(arcgis_server_response: dict) -> dict | None:
    """
    Given a valid response from the server, store this token and use it
    until it expires so we do not have to ask the server for a token on every client request.
    
    Args:
        arcgis_server_response (dict): A successful token request response from the ArcGIS server.
        
    Returns:
        dict|None: An object that is the response plus additional properties we want to remember.
    """
    if not is_arcgis_error(arcgis_server_response):
        # Determine Unix time in milliseconds when this token will expire
        arcgis_server_response["expiresDate"] = (
            int(arcgis_server_response.get("expires_in", 0)) * 1000 + int(time.time() * 1000)
        )
        arcgis_server_response["appTokenBaseURL"] = configuration["appTokenBaseURL"]
        arcgis_server_response["arcgisUserId"] = os.getenv("ARCGIS_USER_ID")

        # Save JSON response in a local file
        try:
            cache_file = configuration.get("cacheFile", "token_cache.json")
            with open(cache_file, "w") as f:
                json.dump(arcgis_server_response, f)
            logger.info(f"Token cached successfully to: {cache_file}")
        except Exception as error:
            logger.error(f"Cannot write cache file at '{configuration.get('cacheFile', 'token_cache.json')}': {error}")

    return arcgis_server_response


def get_cached_token() -> dict:
    """
    If we have a token cache and it has not expired, return the cache. Otherwise raise an exception
    to indicate a new token must be requested.
    
    Returns:
        dict: The parsed and valid cached token object
        
    Raises:
        FileNotFoundError: If cache file does not exist
        ValueError: If token is invalid or expired
        json.JSONDecodeError: If cache file cannot be parsed as JSON
    """
    cache_file = configuration.get("cacheFile", "token_cache.json")
    
    try:
        with open(cache_file, "r") as f:
            response = f.read()

        if not response:
            raise ValueError(f"Cache file is empty: {cache_file}")

        cached_token = json.loads(response)

        if cached_token is None:
            raise ValueError(f"Cache file contains null value: {cache_file}")

        # Check if token has expired
        if is_token_expired(cached_token):
            expires_date = datetime.fromtimestamp(cached_token.get("expiresDate", 0) / 1000)
            raise ValueError(f"Token expired at {expires_date}")

        # Calculate and log time remaining
        time_remaining_ms = cached_token["expiresDate"] - int(time.time() * 1000)
        time_remaining_str = format_time_remaining(time_remaining_ms)
        logger.info(f"Using cached token. Time remaining: {time_remaining_str}")

        return cached_token

    except FileNotFoundError:
        raise FileNotFoundError(f"Cache file not found at: {cache_file}")
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in cache file '{cache_file}': {error}")


# ============================================================================
# Token Request Functions
# ============================================================================

def request_token_with_auth():
    """
    Contact the ArcGIS server and ask for a token using ArcGIS Python API ClientAuth.
    This method uses arcgis.auth.ClientAuth to mimic what is documented on 
    https://developers.arcgis.com/python/latest/guide/authentication-with-application-credentials/
    
    Returns:
        dict: An object that has the token, expiration, and other properties.
        
    Raises:
        ValueError: If CLIENT_ID or CLIENT_SECRET environment variables are not set
        Exception: For any other case where a token cannot be determined
    """
    try:
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("CLIENT_ID and CLIENT_SECRET environment variables must be set")

        # Create ClientAuth session with application credentials
        expiration_minutes = configuration.get("tokenExpirationMinutes", 60)
        portal = GIS(
            client_id=client_id,
            client_secret=client_secret,
            expiration=expiration_minutes
        )

        # Get the token from the auth session
        token = portal.session.auth.token
        logger.info(f"Successfully obtained new token (expires in {expiration_minutes} minutes)")

        # Create response object similar to the JavaScript version
        complete_response = cache_response({
            "access_token": token,
            "expires_in": expiration_minutes * 60,
            "token": token,
        })

        return complete_response

    except ValueError as error:
        logger.error(f"Configuration error: {error}")
        raise
    except Exception as error:
        logger.error(f"Failed to request token from ArcGIS server: {error}")
        raise Exception(f"Error requesting token: {error}")


# ============================================================================
# Public API
# ============================================================================

def get_token(force_refresh=False):
    """
    Request an ArcGIS application token.
    If force_refresh is False and a cached token exists from a prior call and it has not expired,
    it will be returned and the server will not be contacted.
    If force_refresh is True, or no cached token exists, or a cached token exists from a prior call
    but it has expired, the server is contacted for a new token.
    CLIENT_ID and CLIENT_SECRET must be set as environment variables (see README for details.)
    
    Args:
        force_refresh (bool): True to ignore the cache and force a server call. Defaults to False.
        
    Returns:
        dict: An object that has the token properties
        
    Raises:
        Exception: For any case where a token cannot be determined
    """
    try:
        if not force_refresh:
            # First check if the cache is available
            try:
                cached_token = get_cached_token()
                return cached_token
            except (FileNotFoundError, ValueError) as cache_error:
                # Cache is no good, get a new token
                logger.info(f"Cache unavailable ({cache_error}), requesting new token from server")
                return request_token_with_auth()
        else:
            # Ignore the cache and get a new token
            logger.info("Force refresh requested, obtaining new token from server")
            return request_token_with_auth()

    except Exception as error:
        logger.error(f"Cannot obtain token: {error}")
        raise Exception(f"Error getting token: {error}")


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    "get_token",
    "request_token_with_auth",
    "is_arcgis_error",
    "error_response",
    "get_cached_token",
    "cache_response",
    "configuration",
]
