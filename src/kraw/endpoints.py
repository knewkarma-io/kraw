class Endpoints:
    base: str = "https://www.reddit.com"
    user: str = f"{base}/u"
    users: str = f"{base}/users"
    subreddit: str = f"{base}/r"
    subreddits: str = f"{base}/subreddits"
    username_available: str = f"{base}/api/username_available.json"
    infra_status: str = "https://www.redditstatus.com/api/v2/status.json"
    infra_components: str = "https://www.redditstatus.com/api/v2/components.json"


# -------------------------------- END ----------------------------------------- #
