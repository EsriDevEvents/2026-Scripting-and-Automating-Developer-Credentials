"""
auth.py handles authentication negotiation with ArcGIS servers.
"""
import os,time,json
from arcgis import GIS
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta


def load_configuration():
    """
    Load configuration from server-configuration.json file.
    
    Returns:
        dict: Configuration dictionary
    """
    config_path = Path(__file__).parent / "server-configuration.json"
    with open(config_path, "r") as f:
        return json.load(f)


# Load environment variables
load_dotenv()
configuration = load_configuration()


def cache_response(arcgis_server_response):
    """
    Given a valid response from the ArcGIS server, store this token and use it
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
        except Exception as error:
            print(f"Cannot write cache file: {error}")

    return arcgis_server_response


def get_cached_token():
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
    try:
        cache_file = configuration.get("cacheFile", "token_cache.json")
        with open(cache_file, "r") as f:
            response = f.read()

        if not response:
            raise ValueError("Invalid token.")

        cached_token = json.loads(response)

        if cached_token is None:
            raise ValueError("Invalid token.")

        # Determine if this token is still good or it expired
        now = datetime.now()
        expires = cached_token.get("expiresDate")
        date_expires = datetime.fromtimestamp(expires / 1000)
        time_diff = cached_token["expiresDate"] - int(time.time() * 1000)
        is_expired = int(time.time() * 1000) > cached_token["expiresDate"]
        
        hours = time_diff // (1000 * 60 * 60)
        minutes = (time_diff // (1000 * 60)) % 60
        seconds = (time_diff // 1000) % 60
        time_diff_str = f"{hours}:{minutes:02d}:{seconds:02d}"

        # print(f"Date now {now}; expires {date_expires}; diff: {time_diff_str}; isExpired: {is_expired}")

        if is_expired:
            raise ValueError("Token expired.")

        return cached_token

    except FileNotFoundError as error:
        raise FileNotFoundError(f"Cache file not found: {error}")
    except json.JSONDecodeError as error:
        raise ValueError(f"Could not parse response as JSON: {error}")


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


def request_token_with_auth():
    """
    Contact the ArcGIS server and ask for a token using ArcGIS Python API ClientAuth.
    This method uses arcgis.auth.ClientAuth to mimic what is documented on 
    https://developers.arcgis.com/python/latest/guide/authentication-with-application-credentials/
    
    Returns:
        dict: The promise resolves with an object that has the token, expiration, and other properties.
        
    Raises:
        Exception: For any case where a token cannot be determined
    """
    try:
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("CLIENT_ID and CLIENT_SECRET environment variables must be set")

        # Create ClientAuth session with application credentials
        portal = GIS(
            client_id=client_id,
            client_secret=client_secret,
            expiration=configuration.get("tokenExpirationMinutes", 60)
        )

        # Get the token from the auth session
        token = portal.session.auth.token
        print(f"New token: {token}")
        expiration_minutes = configuration.get("tokenExpirationMinutes", 60)

        # Create response object similar to the JavaScript version
        complete_response = cache_response({
            "access_token": token,
            "expires_in": expiration_minutes * 60,
            "token": token,
        })

        return complete_response

    except Exception as error:
        raise Exception(f"Error requesting token: {error}")


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
        dict: Resolves with an object that has the token properties
        
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
                print(f"Cache unavailable ({cache_error}), requesting new token")
                return request_token_with_auth()
        else:
            # Ignore the cache and get a new token
            return request_token_with_auth()

    except Exception as error:
        raise Exception(f"Error getting token: {error}")


# Module exports
__all__ = [
    "get_token",
    "request_token_with_auth",
    "is_arcgis_error",
    "error_response",
    "get_cached_token",
    "cache_response",
    "configuration",
]
