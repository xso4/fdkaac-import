import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

def github_commit_date(repo_url, sha, token):
    parsed = urlparse(repo_url)
    if parsed.netloc.lower() != "github.com":
        return None
    path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if "/" not in path:
        return None
    api_url = f"https://api.github.com/repos/{path}/commits/{sha}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(api_url, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("commit", {}).get("committer", {}).get("date")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None

def main():
    json_path = ".github/upstream-version.json"
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {json_path} not found")
        sys.exit(1)

    data["last_run_utc"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    updated_repos = []
    token = os.environ.get("GITHUB_TOKEN")
    
    for name, repo_data in data["repositories"].items():
        env_key = f"SHA_{name.upper().replace('-', '_')}"
        new_sha = os.environ.get(env_key)
        
        if new_sha:
            print(f"Updating {name}: {repo_data['commit']} -> {new_sha}")
            repo_data['commit'] = new_sha
            commit_date = github_commit_date(repo_data["url"], new_sha, token)
            repo_data['date'] = commit_date or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            updated_repos.append(name)
        else:
            print(f"No new hash provided for {name}, keeping {repo_data['commit']}")

    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully updated upstream-version.json. Updated: {', '.join(updated_repos)}")

    with open("release_notes.md", "w") as f:
        f.write("## Component Versions\n\n")
        f.write("| Component | Commit | Date (UTC) |\n")
        f.write("|-----------|--------|------------|\n")
        for name, repo_data in data["repositories"].items():
            commit = repo_data['commit']
            short_commit = commit[:7] if len(commit) >= 7 else commit
            date = repo_data['date']
            url = repo_data['url'].replace('.git', '')
            f.write(f"| [{name}]({url}) | [{short_commit}]({url}/commit/{commit}) | {date} |\n")

if __name__ == "__main__":
    main()
