from typing import Literal, Union, Optional, List, Dict

import karmakaze
from aiohttp import ClientSession

from . import dummies

__all__ = ["Reddit"]

from .connection import Connection


class Endpoints:

    base: str = "https://www.reddit.com"
    user: str = f"{base}/u"
    users: str = f"{base}/users"
    subreddit: str = f"{base}/r"
    subreddits: str = f"{base}/subreddits"
    username_available: str = f"{base}/api/username_available.json"
    infra_status: str = "https://www.redditstatus.com/api/v2/status.json"
    infra_components: str = "https://www.redditstatus.com/api/v2/components.json"


class Reddit:

    SORT = Literal["controversial", "new", "top", "best", "hot", "rising", "all"]
    TIMEFRAME = Literal["hour", "day", "week", "month", "year", "all"]
    TIME_FORMAT = Literal["concise", "locale"]

    def __init__(self, headers: Dict):
        self._headers = headers
        self._sanitise = karmakaze.Sanitise()
        self.connection = Connection(headers=headers)
        self.endpoints = Endpoints()

    async def infra_status(
        self,
        session: ClientSession,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
    ) -> Union[List[Dict], None]:

        if status:
            status.update(f"Checking Reddit's infrastructure status")

        status_response: Dict = await self.connection.send_request(
            session=session,
            endpoint=self.endpoints.infra_status,
        )

        indicator = status_response.get("status").get("indicator")
        description = status_response.get("status").get("description")
        if description:
            if indicator == "none":

                message.ok(description) if message else print(description)
            else:
                status_message = f"{description} ([yellow]{indicator}[/])"
                (
                    message.warning(status_message)
                    if message
                    else print(status_message.strip("[,],/,yellow"))
                )

                if status:
                    status.update("Getting status components")

                status_components: Dict = await self.connection.send_request(
                    session=session,
                    endpoint=self.endpoints.infra_components,
                )

                if isinstance(status_components, Dict):
                    components: List[Dict] = status_components.get("components")

                    return components

    async def comments(
        self,
        session: ClientSession,
        kind: Literal["user_overview", "user", "post"],
        limit: int,
        sort: SORT,
        timeframe: TIMEFRAME,
        status: Optional[dummies.Status] = None,
        **kwargs: str,
    ) -> List[Dict]:

        comments_map = {
            "user_overview": f"{self.endpoints.user}/{kwargs.get('username')}/overview.json",
            "user": f"{self.endpoints.user}/{kwargs.get('username')}/comments.json",
            "post": f"{self.endpoints.subreddit}/{kwargs.get('subreddit')}"
            f"/comments/{kwargs.get('id')}.json",
        }

        if status:
            status.update(f"Getting {limit} {kind} comments")

        endpoint = comments_map[kind]
        params = {"limit": limit, "sort": sort, "t": timeframe, "raw_json": 1}

        comments = await self.connection.paginate_response(
            session=session,
            endpoint=endpoint,
            params=params,
            limit=limit,
            sanitiser=self._sanitise.comments,
            status=status,
            is_post_comments=True if kind == "post" else False,
        )

        return comments

    async def post(
        self,
        id: str,
        subreddit: str,
        session: ClientSession,
        status: Optional[dummies.Status] = None,
    ) -> Dict:
        if status:
            status.update(f"Getting data from post with id {id} in r/{subreddit}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.endpoints.subreddit}/{subreddit}/comments/{id}.json",
        )
        sanitised_response = self._sanitise.post(response=response)

        return sanitised_response

    async def posts(
        self,
        session: ClientSession,
        kind: Literal[
            "best",
            "controversial",
            "front_page",
            "new",
            "popular",
            "rising",
            "subreddit",
            "user",
            "search_subreddit",
        ],
        limit: int,
        sort: SORT,
        timeframe: TIMEFRAME,
        status: Optional[dummies.Status] = None,
        **kwargs: str,
    ) -> List[Dict]:

        query = kwargs.get("query")
        subreddit = kwargs.get("subreddit")
        username = kwargs.get("username")

        posts_map = {
            "best": f"{self.endpoints.base}/r/{kind}.json",
            "controversial": f"{self.endpoints.base}/r/{kind}.json",
            "front_page": f"{self.endpoints.base}/.json",
            "new": f"{self.endpoints.base}/new.json",
            "popular": f"{self.endpoints.base}/r/{kind}.json",
            "rising": f"{self.endpoints.base}/r/{kind}.json",
            "subreddit": f"{self.endpoints.subreddit}/{subreddit}.json",
            "user": f"{self.endpoints.user}/{username}/submitted.json",
            "search_subreddit": f"{self.endpoints.subreddit}/{subreddit}/search.json?q={query}&restrict_sr=1",
        }

        if status:
            status.update(
                f"Searching for '{query}' in {limit} posts from {subreddit}"
                if kind == "search_subreddit"
                else f"Getting {limit} {kind} posts"
            )

        endpoint = posts_map[kind]

        params = {"limit": limit, "sort": sort, "t": timeframe, "raw_json": 1}

        if kind == "search_subreddit":
            params = params.update({"q": query, "restrict_sr": 1})

        posts = await self.connection.paginate_response(
            session=session,
            endpoint=endpoint,
            params=params,
            limit=limit,
            sanitiser=self._sanitise.posts,
            status=status,
        )

        return posts

    async def search(
        self,
        session: ClientSession,
        kind: Literal["users", "subreddits", "posts"],
        query: str,
        limit: int,
        sort: SORT,
        status: Optional[dummies.Status] = None,
    ) -> List[Dict]:

        search_map = {
            "posts": self.endpoints.base,
            "subreddits": self.endpoints.subreddits,
            "users": self.endpoints.users,
        }

        endpoint = search_map[kind]
        endpoint += f"/search.json"
        params = {"q": query, "limit": limit, "sort": sort, "raw_json": 1}

        sanitiser = (
            self._sanitise.posts
            if kind == "posts"
            else self._sanitise.subreddits_or_users
        )

        if status:
            status.update(f"Searching for '{query}' in {limit} {kind}")

        search_results = await self.connection.paginate_response(
            session=session,
            endpoint=endpoint,
            params=params,
            sanitiser=sanitiser,
            limit=limit,
            status=status,
        )

        return search_results

    async def subreddit(
        self, name: str, session: ClientSession, status: Optional[dummies.Status] = None
    ) -> Dict:
        if status:
            status.update(f"Getting data from subreddit r/{name}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.endpoints.subreddit}/{name}/about.json",
        )
        sanitised_response = self._sanitise.subreddit_or_user(response=response)

        return sanitised_response

    async def subreddits(
        self,
        session: ClientSession,
        kind: Literal["all", "default", "new", "popular", "user_moderated"],
        limit: int,
        timeframe: TIMEFRAME,
        status: Optional[dummies.Status] = None,
        **kwargs: str,
    ) -> Union[List[Dict], Dict]:

        subreddits_map = {
            "all": f"{self.endpoints.subreddits}.json",
            "default": f"{self.endpoints.subreddits}/default.json",
            "new": f"{self.endpoints.subreddits}/new.json",
            "popular": f"{self.endpoints.subreddits}/popular.json",
            "user_moderated": f"{self.endpoints.user}/{kwargs.get('username')}/moderated_subreddits.json",
        }

        if status:
            status.update(f"Getting {limit} {kind} subreddits")

        endpoint = subreddits_map[kind]
        params = {"raw_json": 1}

        if kind == "user_moderated":
            subreddits = await self.connection.send_request(
                session=session,
                endpoint=endpoint,
            )
        else:
            params.update({"limit": limit, "t": timeframe})
            subreddits = await self.connection.paginate_response(
                session=session,
                endpoint=endpoint,
                params=params,
                sanitiser=self._sanitise.subreddits_or_users,
                limit=limit,
                status=status,
            )

        return subreddits

    async def user(
        self, name: str, session: ClientSession, status: Optional[dummies.Status] = None
    ) -> Dict:
        if status:
            status.update(f"Getting data from user u/{name}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.endpoints.user}/{name}/about.json",
        )
        sanitised_response = self._sanitise.subreddit_or_user(response=response)

        return sanitised_response

    async def users(
        self,
        session: ClientSession,
        kind: Literal["all", "popular", "new"],
        limit: int,
        timeframe: TIMEFRAME,
        status: Optional[dummies.Status] = None,
    ) -> List[Dict]:

        users_map = {
            "all": f"{self.endpoints.users}.json",
            "new": f"{self.endpoints.users}/new.json",
            "popular": f"{self.endpoints.users}/popular.json",
        }

        if status:
            status.update(f"Getting {limit} {kind} users")

        endpoint = users_map[kind]
        params = {
            "limit": limit,
            "t": timeframe,
        }

        users = await self.connection.paginate_response(
            session=session,
            endpoint=endpoint,
            params=params,
            sanitiser=self._sanitise.subreddits_or_users,
            limit=limit,
            status=status,
        )

        return users

    async def wiki_page(
        self,
        name: str,
        subreddit: str,
        session: ClientSession,
        status: Optional[dummies.Status] = None,
    ) -> Dict:
        if status:
            status.update(f"Getting data from wikipage {name} in r/{subreddit}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.endpoints.subreddit}/{subreddit}/wiki/{name}.json",
        )
        sanitised_response = self._sanitise.wiki_page(response=response)

        return sanitised_response


# -------------------------------- END ----------------------------------------- #
