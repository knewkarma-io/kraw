from types import SimpleNamespace
from typing import Literal, Union, Optional, List, Dict

import aiohttp
import karmakaze

from . import dummies

__all__ = ["Reddit"]

from .connection import Connection


class Reddit:

    SORT = Literal["controversial", "new", "top", "best", "hot", "rising", "all"]
    TIMEFRAME = Literal["hour", "day", "week", "month", "year", "all"]
    TIME_FORMAT = Literal["concise", "locale"]
    COMMENTS_KIND = Literal["user_overview", "user", "post"]
    POSTS_KIND = Literal[
        "best",
        "controversial",
        "front_page",
        "new",
        "popular",
        "rising",
        "subreddit",
        "user",
        "search_subreddit",
    ]
    SEARCH_KIND = Literal["users", "subreddits", "posts"]
    SUBREDDITS_KIND = Literal["all", "default", "new", "popular", "user_moderated"]
    USERS_KIND = Literal["all", "popular", "new"]

    def __init__(self, headers: Dict):
        self._headers = headers
        self._parse = karmakaze.SanitiseAndParse()
        self.connection = Connection(headers=headers)

    async def infra_status(
        self,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
    ) -> Union[List[Dict], None]:

        if status:
            status.update(f"Checking Reddit's infrastructure status")

        status_response: Dict = await self.connection.send_request(
            session=session,
            endpoint=self.connection.endpoints.infra_status,
            proxy=proxy,
            proxy_auth=proxy_auth,
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
                    endpoint=self.connection.endpoints.infra_components,
                )

                if isinstance(status_components, Dict):
                    components: List[Dict] = status_components.get("components")

                    return components

    async def comments(
        self,
        session: aiohttp.ClientSession,
        kind: COMMENTS_KIND,
        limit: int,
        sort: SORT,
        timeframe: TIMEFRAME,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
        **kwargs: str,
    ) -> List[SimpleNamespace]:

        comments_map = {
            "user_overview": f"{self.connection.endpoints.user}/{kwargs.get('username')}/overview.json",
            "user": f"{self.connection.endpoints.user}/{kwargs.get('username')}/comments.json",
            "post": f"{self.connection.endpoints.subreddit}/{kwargs.get('subreddit')}"
            f"/comments/{kwargs.get('id')}.json",
        }

        if status:
            status.update(f"Getting {limit} comments from {kind}")

        endpoint = comments_map[kind]
        params = {"limit": limit, "sort": sort, "t": timeframe, "raw_json": 1}

        comments = await self.connection.paginate_response(
            session=session,
            endpoint=endpoint,
            proxy=proxy,
            proxy_auth=proxy_auth,
            params=params,
            limit=limit,
            parser=self._parse.comments,
            message=message,
            status=status,
            is_post_comments=True if kind == "post" else False,
        )

        if message:
            message.ok(f"Got {len(comments)} of {limit} comments from {kind}")

        return comments

    async def post(
        self,
        id: str,
        subreddit: str,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        status: Optional[dummies.Status] = None,
    ) -> SimpleNamespace:
        if status:
            status.update(f"Getting data from post with id {id} in r/{subreddit}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.connection.endpoints.subreddit}/{subreddit}/comments/{id}.json",
            proxy=proxy,
            proxy_auth=proxy_auth,
        )
        sanitised_response = self._parse.post(response=response)

        return sanitised_response

    async def posts(
        self,
        session: aiohttp.ClientSession,
        kind: POSTS_KIND,
        limit: int,
        sort: SORT,
        timeframe: TIMEFRAME,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
        **kwargs: str,
    ) -> List[SimpleNamespace]:

        query = kwargs.get("query")
        subreddit = kwargs.get("subreddit")
        username = kwargs.get("username")

        posts_map = {
            "best": f"{self.connection.endpoints.base}/r/{kind}.json",
            "controversial": f"{self.connection.endpoints.base}/r/{kind}.json",
            "front_page": f"{self.connection.endpoints.base}/.json",
            "new": f"{self.connection.endpoints.base}/new.json",
            "popular": f"{self.connection.endpoints.base}/r/{kind}.json",
            "rising": f"{self.connection.endpoints.base}/r/{kind}.json",
            "subreddit": f"{self.connection.endpoints.subreddit}/{subreddit}.json",
            "user": f"{self.connection.endpoints.user}/{username}/submitted.json",
            "search_subreddit": f"{self.connection.endpoints.subreddit}/{subreddit}/search.json?q={query}&restrict_sr=1",
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
            proxy=proxy,
            proxy_auth=proxy_auth,
            params=params,
            limit=limit,
            parser=self._parse.posts,
            message=message,
            status=status,
        )

        if message:
            message.ok(f"Got {len(posts)} of {limit} {kind} posts")

        return posts

    async def search(
        self,
        session: aiohttp.ClientSession,
        kind: SEARCH_KIND,
        query: str,
        limit: int,
        sort: SORT,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
    ) -> List[SimpleNamespace]:

        search_map = {
            "posts": self.connection.endpoints.base,
            "subreddits": self.connection.endpoints.subreddits,
            "users": self.connection.endpoints.users,
        }

        endpoint = search_map[kind]
        endpoint += f"/search.json"
        params = {"q": query, "limit": limit, "sort": sort, "raw_json": 1}

        if kind == "posts":
            parser = self._parse.posts
        elif kind == "subreddits":
            parser = self._parse.subreddits
        else:
            parser = self._parse.users

        if status:
            status.update(f"Searching for '{query}' in {limit} {kind}")

        results = await self.connection.paginate_response(
            session=session,
            endpoint=endpoint,
            proxy=proxy,
            proxy_auth=proxy_auth,
            params=params,
            parser=parser,
            limit=limit,
            message=message,
            status=status,
        )

        if message:
            message.ok(f"Got {len(results)} of {limit} {kind} search results")

        return results

    async def subreddit(
        self,
        name: str,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        status: Optional[dummies.Status] = None,
    ) -> SimpleNamespace:
        if status:
            status.update(f"Getting data from subreddit r/{name}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.connection.endpoints.subreddit}/{name}/about.json",
            proxy=proxy,
            proxy_auth=proxy_auth,
        )
        sanitised_response = self._parse.subreddit(response=response)

        return sanitised_response

    async def subreddits(
        self,
        session: aiohttp.ClientSession,
        kind: SUBREDDITS_KIND,
        limit: int,
        timeframe: TIMEFRAME,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        **kwargs: str,
    ) -> Union[List[SimpleNamespace], SimpleNamespace]:

        subreddits_map = {
            "all": f"{self.connection.endpoints.subreddits}.json",
            "default": f"{self.connection.endpoints.subreddits}/default.json",
            "new": f"{self.connection.endpoints.subreddits}/new.json",
            "popular": f"{self.connection.endpoints.subreddits}/popular.json",
            "user_moderated": f"{self.connection.endpoints.user}/{kwargs.get('username')}/moderated_subreddits.json",
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
                proxy=proxy,
                proxy_auth=proxy_auth,
                params=params,
                parser=self._parse.subreddits,
                limit=limit,
                message=message,
                status=status,
            )

        if message:
            message.ok(f"Got {len(subreddits)} of {limit} {kind} subreddits")

        return subreddits

    async def user(
        self,
        name: str,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        status: Optional[dummies.Status] = None,
    ) -> SimpleNamespace:
        if status:
            status.update(f"Getting data from user u/{name}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.connection.endpoints.user}/{name}/about.json",
            proxy=proxy,
            proxy_auth=proxy_auth,
        )
        sanitised_response = self._parse.user(response=response)

        return sanitised_response

    async def users(
        self,
        session: aiohttp.ClientSession,
        kind: USERS_KIND,
        limit: int,
        timeframe: TIMEFRAME,
        message: Optional[dummies.Message] = None,
        status: Optional[dummies.Status] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
    ) -> List[SimpleNamespace]:

        users_map = {
            "all": f"{self.connection.endpoints.users}.json",
            "new": f"{self.connection.endpoints.users}/new.json",
            "popular": f"{self.connection.endpoints.users}/popular.json",
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
            proxy=proxy,
            proxy_auth=proxy_auth,
            params=params,
            parser=self._parse.users,
            limit=limit,
            message=message,
            status=status,
        )

        if message:
            message.ok(f"Got {len(users)} of {limit} {kind} users")

        return users

    async def wiki_page(
        self,
        name: str,
        subreddit: str,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        status: Optional[dummies.Status] = None,
    ) -> SimpleNamespace:
        if status:
            status.update(f"Getting data from wikipage {name} in r/{subreddit}")

        response = await self.connection.send_request(
            session=session,
            endpoint=f"{self.connection.endpoints.subreddit}/{subreddit}/wiki/{name}.json",
            proxy=proxy,
            proxy_auth=proxy_auth,
        )
        sanitised_response = self._parse.wiki_page(response=response)

        return sanitised_response


# -------------------------------- END ----------------------------------------- #
