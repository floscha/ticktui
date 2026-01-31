"""OAuth2 redirect server for handling TickTick authentication callback."""

import asyncio
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread
from typing import Optional
import socket


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""
    
    # Class-level storage for the authorization code
    auth_code: Optional[str] = None
    auth_state: Optional[str] = None
    error: Optional[str] = None
    callback_received = asyncio.Event()
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        parsed = urlparse(self.path)
        
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            
            if "code" in params:
                OAuthCallbackHandler.auth_code = params["code"][0]
                OAuthCallbackHandler.auth_state = params.get("state", [None])[0]
                self._send_success_response()
            elif "error" in params:
                OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
                self._send_error_response(OAuthCallbackHandler.error)
            else:
                OAuthCallbackHandler.error = "No authorization code received"
                self._send_error_response(OAuthCallbackHandler.error)
        else:
            self.send_error(404, "Not Found")
    
    def _send_success_response(self):
        """Send a success HTML response."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>TickTUI - Authorization Successful</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container {
                    text-align: center;
                    padding: 2rem;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    backdrop-filter: blur(10px);
                }
                h1 { margin-bottom: 0.5rem; }
                p { opacity: 0.9; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to TickTUI.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())
    
    def _send_error_response(self, error: str):
        """Send an error HTML response."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TickTUI - Authorization Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    backdrop-filter: blur(10px);
                }}
                h1 {{ margin-bottom: 0.5rem; }}
                p {{ opacity: 0.9; }}
                .error-icon {{
                    font-size: 4rem;
                    margin-bottom: 1rem;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">✗</div>
                <h1>Authorization Failed</h1>
                <p>{error}</p>
                <p>Please close this window and try again.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())


class OAuthRedirectServer:
    """Local server to handle OAuth2 redirect callbacks."""
    
    def __init__(self, port: int = 8080, host: str = "localhost"):
        self.port = port
        self.host = host
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[Thread] = None
    
    @property
    def redirect_uri(self) -> str:
        """Get the redirect URI for this server."""
        return f"http://{self.host}:{self.port}/callback"
    
    def _find_available_port(self) -> int:
        """Find an available port starting from self.port."""
        for port in range(self.port, self.port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((self.host, port))
                    return port
            except OSError:
                continue
        raise RuntimeError(f"No available ports found starting from {self.port}")
    
    def start(self) -> int:
        """Start the OAuth redirect server.
        
        Returns:
            The port the server is running on.
        """
        # Reset handler state
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.auth_state = None
        OAuthCallbackHandler.error = None
        
        # Find available port
        self.port = self._find_available_port()
        
        self.server = HTTPServer((self.host, self.port), OAuthCallbackHandler)
        self._thread = Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        
        return self.port
    
    def stop(self):
        """Stop the OAuth redirect server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        self._thread = None
    
    def wait_for_callback(self, timeout: float = 300) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Wait for the OAuth callback.
        
        Args:
            timeout: Maximum time to wait in seconds.
            
        Returns:
            Tuple of (auth_code, state, error)
        """
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            if OAuthCallbackHandler.auth_code or OAuthCallbackHandler.error:
                # Small delay to ensure response is sent to browser
                time.sleep(0.2)
                break
            time.sleep(0.1)
        
        return (
            OAuthCallbackHandler.auth_code,
            OAuthCallbackHandler.auth_state,
            OAuthCallbackHandler.error,
        )


async def perform_oauth_flow(
    client_id: str,
    client_secret: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Perform the complete OAuth2 flow.
    
    Args:
        client_id: TickTick API client ID
        client_secret: TickTick API client secret
        
    Returns:
        Tuple of (access_token, refresh_token, error)
    """
    from .api import TickTickAuth
    
    # Start local server
    server = OAuthRedirectServer()
    server.start()
    
    try:
        # Create auth handler with correct redirect URI
        auth = TickTickAuth(client_id, client_secret, server.redirect_uri)
        
        # Generate authorization URL
        auth_url, state = auth.get_authorization_url()
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Wait for callback in a thread to not block the event loop
        code, returned_state, error = await asyncio.to_thread(
            server.wait_for_callback, 300
        )
        
        if error:
            return None, None, error
        
        if not code:
            return None, None, "Authorization timed out"
        
        # Verify state
        if returned_state != state:
            return None, None, "State mismatch - possible CSRF attack"
        
        # Exchange code for token
        token_data = await auth.exchange_code(code)
        
        return (
            token_data.get("access_token"),
            token_data.get("refresh_token"),
            None,
        )
        
    finally:
        server.stop()
