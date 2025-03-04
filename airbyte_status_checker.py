import os
import json
import requests
import time
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from fastmcp import FastMCP

# Create a FastMCP instance
mcp = FastMCP("Airbyte Connection Checker")

# Load environment variables
load_dotenv()

# Airbyte API configuration
API_BASE_URL = "https://api.airbyte.com/v1"
API_KEY = os.getenv("AIRBYTE_API_KEY")
WORKSPACE_ID = os.getenv("AIRBYTE_WORKSPACE_ID")
CLIENT_ID = os.getenv("AIRBYTE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AIRBYTE_CLIENT_SECRET")

if not WORKSPACE_ID or not API_KEY:
    raise ValueError("Missing required Airbyte credentials in .env file")

# Headers for API requests
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Token refresh function
def refresh_airbyte_token():
    """Refresh the Airbyte API token"""
    try:
        refresh_token = os.getenv('AIRBYTE_API_KEY')
        if not refresh_token:
            raise ValueError("AIRBYTE_API_KEY not found in environment variables")

        base_url = API_BASE_URL.rstrip('/')
        response = requests.post(
            f'{base_url}/applications/token',
            data={
                'grant_type': 'refresh_token',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': refresh_token
            }
        )
        response.raise_for_status()

        new_token = response.json().get('access_token')
        if not new_token:
            raise ValueError("No access token in response")

        # Update global API_KEY and HEADERS
        global API_KEY, HEADERS
        API_KEY = new_token
        HEADERS = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        return new_token
    except Exception as e:
        print(f"Failed to refresh token: {str(e)}")
        raise

def get_connections():
    """Get all connections in the workspace"""
    url = f"{API_BASE_URL}/connections"
    params = {"workspaceIds": WORKSPACE_ID}
    
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    
    return response.json().get("data", [])

def check_connection_status(connection_id):
    """Check the status of a connection"""
    url = f"{API_BASE_URL}/connections/get"
    
    payload = {
        "connectionId": connection_id
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    
    return response.json()

def get_connection_streams(connection_id):
    """Get the streams for a connection"""
    url = f"{API_BASE_URL}/connections/get"
    
    payload = {
        "connectionId": connection_id
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    
    connection_data = response.json()
    # Extract stream information from the connection data
    # This might need adjustment based on the actual API response structure
    streams = connection_data.get("syncCatalog", {}).get("streams", [])
    return [stream.get("stream", {}).get("name") for stream in streams if stream.get("config", {}).get("selected")]

@mcp.tool()
async def check_airbyte_connection(connection_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Check the status of an Airbyte connection or list all connections.
    
    Args:
        connection_name: Name of the connection to check. If not provided, lists all connections.
        
    Returns:
        A dictionary with status information.
    """
    try:
        # Try to refresh the token if needed
        try:
            if CLIENT_ID and CLIENT_SECRET:
                refresh_airbyte_token()
        except Exception as e:
            print(f"Token refresh failed, continuing with existing token: {str(e)}")
        
        # Get all connections in the workspace
        connections = get_connections()
        
        if not connection_name:
            # If no connection name provided, return list of all connections
            connection_list = [
                {
                    "name": conn.get("name"), 
                    "id": conn.get("connectionId"), 
                    "status": "🟢 Active" if conn.get("status", "").lower() == "active" else "🔴 Inactive"
                } 
                for conn in connections
            ]
            
            return {
                "status": "success",
                "message": "📋 Here's a list of all connections",
                "connections": connection_list
            }
        else:
            # Find the connection by name
            connection = None
            for conn in connections:
                if conn.get("name", "").lower() == connection_name.lower():
                    connection = conn
                    break
            
            if not connection:
                return {
                    "status": "error",
                    "message": f"❌ Connection '{connection_name}' not found"
                }
            
            # Get connection details
            connection_id = connection.get("connectionId")
            connection_details = check_connection_status(connection_id)
            
            # Get streams for this connection
            streams = get_connection_streams(connection_id)
            
            status = connection.get("status", "")
            
            if status.lower() == "active":
                emoji = "✅"
                message = f"Connection '{connection_name}' is active"
            else:
                emoji = "❌"
                message = f"Connection '{connection_name}' is inactive"
            
            return {
                "status": status,
                "message": f"{emoji} {message}",
                "connection_name": connection_name,
                "connection_id": connection_id,
                "streams": streams,
                "details": connection_details
            }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Error: {str(e)}"
        }

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')