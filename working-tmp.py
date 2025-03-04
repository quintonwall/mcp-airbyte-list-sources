import os
import json
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from fastmcp import FastMCP

# Create a FastMCP instance
mcp = FastMCP("Airbyte Status Checker")

# Load environment variables
load_dotenv()

# Airbyte API configuration
API_BASE_URL = "https://api.airbyte.com/v1"
API_KEY = os.getenv("AIRBYTE_API_KEY")
WORKSPACE_ID = os.getenv("AIRBYTE_WORKSPACE_ID")

if not WORKSPACE_ID or not API_KEY:
    raise ValueError("Missing required Airbyte credentials in .env file")

# Headers for API requests
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_sources():
    """Get all sources in the workspace"""
    url = f"{API_BASE_URL}/sources"
    params = {"workspaceIds": WORKSPACE_ID}
    
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    
    return response.json().get("data", [])

def check_source_connection(source_id):
    """Check the connection status of a source"""
    url = f"{API_BASE_URL}/sources/check_connection_to_source"
    
    payload = {
        "sourceId": source_id
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    
    return response.json()

@mcp.tool()
async def check_airbyte_source(source_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Check the status of an Airbyte source or list all sources.
    
    Args:
        source_name: Name of the source to check. If not provided, lists all sources.
        
    Returns:
        A dictionary with status information.
    """
    try:
        # Get all sources in the workspace
        sources = get_sources()
        
        if not source_name:
            # If no source name provided, return list of all sources
            source_list = [
                {"name": source.get("name"), "id": source.get("sourceId"), "source_type": source.get("sourceType")} 
                for source in sources
            ]
            
            return {
                "status": "success",
                "message": "📋 Here's a list of all sources",
                "sources": source_list
            }
        else:
            # Find the source by name
            source = None
            for s in sources:
                if s.get("name", "").lower() == source_name.lower():
                    source = s
                    break
            
            if not source:
                return {
                    "status": "error",
                    "message": f"❌ Source '{source_name}' not found"
                }
            
            # Check connection status
            source_id = source.get("sourceId")
            check_result = check_source_connection(source_id)
            
            status = check_result.get("status", "")
            job_info = check_result.get("jobInfo", {})
            
            if status == "succeeded":
                emoji = "✅"
                message = f"Connection to source '{source_name}' is healthy"
            else:
                emoji = "❌"
                message = f"Connection to source '{source_name}' failed"
                
                # Add failure details if available
                if job_info.get("failureReason"):
                    message += f": {job_info.get('failureReason')}"
            
            return {
                "status": status,
                "message": f"{emoji} {message}",
                "source_name": source_name,
                "source_id": source_id,
                "source_type": source.get("sourceType"),
                "job_info": job_info
            }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Error: {str(e)}"
        }

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')