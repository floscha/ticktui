"""TickTick API Client using official REST endpoints."""

import httpx
import secrets
import base64
from urllib.parse import urlencode
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import os
import json


@dataclass
class Task:
    """Represents a TickTick task."""
    id: str
    title: str
    project_id: str
    content: str = ""
    priority: int = 0  # 0=none, 1=low, 3=medium, 5=high
    status: int = 0  # 0=normal, 2=completed
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    is_all_day: bool = False
    tags: list[str] = None
    items: list[dict] = None  # Subtasks/checklist items
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.items is None:
            self.items = []
    
    @classmethod
    def from_api(cls, data: dict) -> "Task":
        """Create a Task from API response data."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            project_id=data.get("projectId", ""),
            content=data.get("content", ""),
            priority=data.get("priority", 0),
            status=data.get("status", 0),
            due_date=cls._parse_date(data.get("dueDate")),
            start_date=cls._parse_date(data.get("startDate")),
            is_all_day=data.get("isAllDay", False),
            tags=data.get("tags", []),
            items=data.get("items", []),
        )
    
    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse a TickTick date string."""
        if not date_str:
            return None
        try:
            # TickTick uses ISO format with timezone
            return datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+0000", "+00:00"))
        except (ValueError, AttributeError):
            return None
    
    def to_api(self) -> dict:
        """Convert to API request format."""
        data = {
            "title": self.title,
            "projectId": self.project_id,
            "content": self.content,
            "priority": self.priority,
        }
        if self.due_date:
            data["dueDate"] = self.due_date.isoformat()
        if self.start_date:
            data["startDate"] = self.start_date.isoformat()
        if self.is_all_day:
            data["isAllDay"] = self.is_all_day
        if self.tags:
            data["tags"] = self.tags
        return data
    
    @property
    def priority_label(self) -> str:
        """Get human-readable priority label."""
        return {0: "None", 1: "Low", 3: "Medium", 5: "High"}.get(self.priority, "None")
    
    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == 2


@dataclass
class Project:
    """Represents a TickTick project (list)."""
    id: str
    name: str
    color: str = ""
    closed: bool = False
    group_id: Optional[str] = None
    sort_order: int = 0
    
    @classmethod
    def from_api(cls, data: dict) -> "Project":
        """Create a Project from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            color=data.get("color", ""),
            closed=data.get("closed", False),
            group_id=data.get("groupId"),
            sort_order=data.get("sortOrder", 0),
        )


class TickTickAuth:
    """Handles OAuth2 authentication with TickTick."""
    
    AUTHORIZE_URL = "https://ticktick.com/oauth/authorize"
    TOKEN_URL = "https://ticktick.com/oauth/token"
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8080/callback"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
    
    @property
    def access_token(self) -> Optional[str]:
        return self._access_token
    
    @access_token.setter
    def access_token(self, value: str):
        self._access_token = value
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """Generate the OAuth2 authorization URL.
        
        Returns:
            Tuple of (authorization_url, state)
        """
        if state is None:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "tasks:read tasks:write",
            "state": state,
        }
        
        url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"
        return url, state
    
    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            # Create basic auth header
            credentials = f"{self.client_id}:{self.client_secret}"
            basic_auth = base64.b64encode(credentials.encode()).decode()
            
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                headers={
                    "Authorization": f"Basic {basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._access_token = token_data.get("access_token")
            self._refresh_token = token_data.get("refresh_token")
            
            return token_data
    
    async def refresh_access_token(self) -> dict:
        """Refresh the access token using refresh token."""
        if not self._refresh_token:
            raise ValueError("No refresh token available")
        
        async with httpx.AsyncClient() as client:
            credentials = f"{self.client_id}:{self.client_secret}"
            basic_auth = base64.b64encode(credentials.encode()).decode()
            
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                headers={
                    "Authorization": f"Basic {basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._access_token = token_data.get("access_token")
            if "refresh_token" in token_data:
                self._refresh_token = token_data.get("refresh_token")
            
            return token_data


class TickTickClient:
    """Async client for TickTick REST API."""
    
    BASE_URL = "https://api.ticktick.com"
    OPEN_API_URL = "https://api.ticktick.com/open/v1"
    
    def __init__(self, auth: TickTickAuth):
        self.auth = auth
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def _headers(self) -> dict:
        """Get request headers with authorization."""
        return {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    # Project endpoints
    async def get_projects(self) -> list[Project]:
        """Get all projects (lists)."""
        client = await self._get_client()
        response = await client.get(
            f"{self.OPEN_API_URL}/project",
            headers=self._headers,
        )
        response.raise_for_status()
        return [Project.from_api(p) for p in response.json()]
    
    async def get_project(self, project_id: str) -> Project:
        """Get a specific project by ID."""
        client = await self._get_client()
        response = await client.get(
            f"{self.OPEN_API_URL}/project/{project_id}",
            headers=self._headers,
        )
        response.raise_for_status()
        return Project.from_api(response.json())
    
    # Task endpoints
    async def get_project_tasks(self, project_id: str) -> list[Task]:
        """Get all tasks in a project."""
        client = await self._get_client()
        response = await client.get(
            f"{self.OPEN_API_URL}/project/{project_id}/data",
            headers=self._headers,
        )
        response.raise_for_status()
        data = response.json()
        tasks = data.get("tasks", [])
        return [Task.from_api(t) for t in tasks]
    
    async def get_task(self, project_id: str, task_id: str) -> Task:
        """Get a specific task by ID."""
        client = await self._get_client()
        response = await client.get(
            f"{self.OPEN_API_URL}/project/{project_id}/task/{task_id}",
            headers=self._headers,
        )
        response.raise_for_status()
        return Task.from_api(response.json())
    
    async def create_task(self, task: Task) -> Task:
        """Create a new task."""
        client = await self._get_client()
        response = await client.post(
            f"{self.OPEN_API_URL}/task",
            headers=self._headers,
            json=task.to_api(),
        )
        response.raise_for_status()
        return Task.from_api(response.json())
    
    async def update_task(self, task: Task) -> Task:
        """Update an existing task."""
        client = await self._get_client()
        data = task.to_api()
        data["id"] = task.id
        response = await client.post(
            f"{self.OPEN_API_URL}/task/{task.id}",
            headers=self._headers,
            json=data,
        )
        response.raise_for_status()
        return Task.from_api(response.json())
    
    async def complete_task(self, project_id: str, task_id: str) -> None:
        """Mark a task as complete."""
        client = await self._get_client()
        response = await client.post(
            f"{self.OPEN_API_URL}/project/{project_id}/task/{task_id}/complete",
            headers=self._headers,
        )
        response.raise_for_status()
    
    async def delete_task(self, project_id: str, task_id: str) -> None:
        """Delete a task."""
        client = await self._get_client()
        response = await client.delete(
            f"{self.OPEN_API_URL}/project/{project_id}/task/{task_id}",
            headers=self._headers,
        )
        response.raise_for_status()
    
    # Helper methods
    async def get_all_tasks(self) -> list[Task]:
        """Get all tasks from all projects."""
        projects = await self.get_projects()
        all_tasks = []
        for project in projects:
            try:
                tasks = await self.get_project_tasks(project.id)
                all_tasks.extend(tasks)
            except httpx.HTTPStatusError:
                # Skip projects that fail (might be special projects)
                continue
        return all_tasks


class TokenStorage:
    """Simple file-based token storage."""
    
    def __init__(self, path: str = None):
        if path is None:
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "ticktui")
            os.makedirs(config_dir, exist_ok=True)
            path = os.path.join(config_dir, "tokens.json")
        self.path = path
    
    def save(self, access_token: str, refresh_token: str = None) -> None:
        """Save tokens to file."""
        data = {"access_token": access_token}
        if refresh_token:
            data["refresh_token"] = refresh_token
        with open(self.path, "w") as f:
            json.dump(data, f)
        # Restrict permissions
        os.chmod(self.path, 0o600)
    
    def load(self) -> dict:
        """Load tokens from file."""
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r") as f:
            return json.load(f)
    
    def clear(self) -> None:
        """Clear stored tokens."""
        if os.path.exists(self.path):
            os.remove(self.path)
