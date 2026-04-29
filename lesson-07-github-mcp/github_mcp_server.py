"""
Lesson 07 — GitHub MCP Server
==============================
A custom MCP server that wraps the GitHub REST API.
Exposes tools Claude can use to interact with GitHub.

How it works:
1. MCP server starts and registers all tools
2. Claude connects and discovers available tools
3. User asks a question
4. Claude decides which tool to call
5. MCP server calls GitHub API and returns result
6. Claude answers the user

Tools exposed:
- list_repos       — list your repositories
- get_repo         — get details about a specific repo
- list_issues      — list issues in a repo
- create_issue     — create a new issue
- list_prs         — list pull requests
- search_code      — search code in a repo
- get_profile      — get your GitHub profile
"""

import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# -----------------------------------------------------------------------
# GitHub API client
# -----------------------------------------------------------------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API   = "https://api.github.com"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


def github_get(endpoint: str, params: dict = None) -> dict | list:
    """Make a GET request to GitHub API."""
    response = httpx.get(
        f"{GITHUB_API}{endpoint}",
        headers=headers,
        params=params,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def github_post(endpoint: str, data: dict) -> dict:
    """Make a POST request to GitHub API."""
    response = httpx.post(
        f"{GITHUB_API}{endpoint}",
        headers=headers,
        json=data,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


# -----------------------------------------------------------------------
# Create MCP server
# FastMCP is the simplest way to build an MCP server in Python
# It auto-generates the tool schemas from your function signatures
# -----------------------------------------------------------------------
mcp = FastMCP("GitHub MCP Server")


# -----------------------------------------------------------------------
# Tool 1 — Get your GitHub profile
# -----------------------------------------------------------------------
@mcp.tool()
def get_profile() -> str:
    """Get the authenticated user's GitHub profile information."""
    data = github_get("/user")
    return (
        f"Username: {data.get('login')}\n"
        f"Name: {data.get('name')}\n"
        f"Bio: {data.get('bio')}\n"
        f"Public repos: {data.get('public_repos')}\n"
        f"Followers: {data.get('followers')}\n"
        f"Following: {data.get('following')}\n"
        f"Location: {data.get('location')}\n"
        f"Company: {data.get('company')}"
    )


# -----------------------------------------------------------------------
# Tool 2 — List repositories
# -----------------------------------------------------------------------
@mcp.tool()
def list_repos(sort: str = "updated", limit: int = 10) -> str:
    """
    List your GitHub repositories.

    Args:
        sort: Sort by 'updated', 'created', 'pushed', or 'full_name'
        limit: Number of repos to return (max 30)
    """
    data = github_get("/user/repos", params={
        "sort": sort,
        "per_page": min(limit, 30),
        "affiliation": "owner"
    })

    if not data:
        return "No repositories found."

    result = []
    for repo in data:
        result.append(
            f"- {repo['name']}: {repo.get('description') or 'No description'} "
            f"[{'private' if repo['private'] else 'public'}] "
            f"⭐ {repo['stargazers_count']}"
        )

    return f"Your repositories ({len(data)} shown):\n" + "\n".join(result)


# -----------------------------------------------------------------------
# Tool 3 — Get repo details
# -----------------------------------------------------------------------
@mcp.tool()
def get_repo(owner: str, repo: str) -> str:
    """
    Get details about a specific GitHub repository.

    Args:
        owner: Repository owner username
        repo: Repository name
    """
    data = github_get(f"/repos/{owner}/{repo}")

    return (
        f"Repo: {data['full_name']}\n"
        f"Description: {data.get('description') or 'None'}\n"
        f"Language: {data.get('language') or 'Not specified'}\n"
        f"Stars: {data['stargazers_count']}\n"
        f"Forks: {data['forks_count']}\n"
        f"Open issues: {data['open_issues_count']}\n"
        f"Default branch: {data['default_branch']}\n"
        f"Created: {data['created_at'][:10]}\n"
        f"Last updated: {data['updated_at'][:10]}\n"
        f"URL: {data['html_url']}"
    )


# -----------------------------------------------------------------------
# Tool 4 — List issues
# -----------------------------------------------------------------------
@mcp.tool()
def list_issues(owner: str, repo: str, state: str = "open", limit: int = 10) -> str:
    """
    List issues in a GitHub repository.

    Args:
        owner: Repository owner username
        repo: Repository name
        state: 'open', 'closed', or 'all'
        limit: Number of issues to return (max 30)
    """
    data = github_get(f"/repos/{owner}/{repo}/issues", params={
        "state": state,
        "per_page": min(limit, 30)
    })

    if not data:
        return f"No {state} issues found in {owner}/{repo}."

    result = []
    for issue in data:
        if "pull_request" in issue:
            continue  # skip PRs — they show up in issues endpoint too
        labels = ", ".join([l["name"] for l in issue.get("labels", [])]) or "none"
        result.append(
            f"#{issue['number']}: {issue['title']}\n"
            f"  Labels: {labels} | Created: {issue['created_at'][:10]}"
        )

    return f"Issues in {owner}/{repo} ({state}):\n" + "\n".join(result)


# -----------------------------------------------------------------------
# Tool 5 — Create issue
# -----------------------------------------------------------------------
@mcp.tool()
def create_issue(owner: str, repo: str, title: str, body: str = "") -> str:
    """
    Create a new issue in a GitHub repository.

    Args:
        owner: Repository owner username
        repo: Repository name
        title: Issue title
        body: Issue description (optional)
    """
    data = github_post(f"/repos/{owner}/{repo}/issues", {
        "title": title,
        "body": body
    })

    return (
        f"Issue created successfully!\n"
        f"Number: #{data['number']}\n"
        f"Title: {data['title']}\n"
        f"URL: {data['html_url']}"
    )


# -----------------------------------------------------------------------
# Tool 6 — List pull requests
# -----------------------------------------------------------------------
@mcp.tool()
def list_prs(owner: str, repo: str, state: str = "open") -> str:
    """
    List pull requests in a GitHub repository.

    Args:
        owner: Repository owner username
        repo: Repository name
        state: 'open', 'closed', or 'all'
    """
    data = github_get(f"/repos/{owner}/{repo}/pulls", params={
        "state": state,
        "per_page": 10
    })

    if not data:
        return f"No {state} pull requests found in {owner}/{repo}."

    result = []
    for pr in data:
        result.append(
            f"#{pr['number']}: {pr['title']}\n"
            f"  By: {pr['user']['login']} | "
            f"Branch: {pr['head']['ref']} → {pr['base']['ref']}"
        )

    return f"Pull requests in {owner}/{repo} ({state}):\n" + "\n".join(result)


# -----------------------------------------------------------------------
# Tool 7 — Search code
# -----------------------------------------------------------------------
@mcp.tool()
def search_code(query: str, owner: str = "", repo: str = "") -> str:
    """
    Search for code on GitHub.

    Args:
        query: Search query e.g. 'anthropic client'
        owner: Limit search to this owner (optional)
        repo: Limit search to this repo (optional)
    """
    search_query = query
    if owner and repo:
        search_query += f" repo:{owner}/{repo}"
    elif owner:
        search_query += f" user:{owner}"

    data = github_get("/search/code", params={
        "q": search_query,
        "per_page": 5
    })

    items = data.get("items", [])
    if not items:
        return f"No code found for query: {query}"

    result = []
    for item in items:
        result.append(
            f"- {item['repository']['full_name']}/{item['path']}\n"
            f"  URL: {item['html_url']}"
        )

    total = data.get("total_count", 0)
    return (
        f"Found {total:,} results for '{query}' (showing top {len(items)}):\n"
        + "\n".join(result)
    )


# -----------------------------------------------------------------------
# Run the MCP server
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print("Starting GitHub MCP Server...")
    print("Tools available:")
    print("  - get_profile")
    print("  - list_repos")
    print("  - get_repo")
    print("  - list_issues")
    print("  - create_issue")
    print("  - list_prs")
    print("  - search_code")
    print()
    mcp.run()