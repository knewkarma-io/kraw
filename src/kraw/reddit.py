from typing import Literal, Union, Optional, List, Dict

from aiohttp import ClientSession
from karmakaze.sanitise import Sanitise

from . import dummies
from .endpoints import Endpoints

__all__ = ["Reddit"]

from .connection import Connection


class Reddit:

    SORT = Literal["controversial", "new", "top", "best", "hot", "rising", "all"]
    TIMEFRAME = Literal["hour", "day", "week", "month", "year", "all"]
    TIME_FORMAT = Literal["concise", "locale"]

    def __init__(self, headers: Dict):
        self._headers = headers
        self.connection = Connection(headers=headers)

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
            endpoint=Endpoints.infra_status,
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
                    endpoint=Endpoints.infra_components,
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
            "user_overview": f"{Endpoints.user}/{kwargs.get('username')}/overview.json",
            "user": f"{Endpoints.user}/{kwargs.get('username')}/comments.json",
            "post": f"{Endpoints.subreddit}/{kwargs.get('subreddit')}"
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
            sanitiser=Sanitise.comments,
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
            endpoint=f"{Endpoints.subreddit}/{subreddit}/comments/{id}.json",
        )
        sanitised_response = Sanitise.post(response=response)

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
            "best": f"{Endpoints.base}/r/{kind}.json",
            "controversial": f"{Endpoints.base}/r/{kind}.json",
            "front_page": f"{Endpoints.base}/.json",
            "new": f"{Endpoints.base}/new.json",
            "popular": f"{Endpoints.base}/r/{kind}.json",
            "rising": f"{Endpoints.base}/r/{kind}.json",
            "subreddit": f"{Endpoints.subreddit}/{subreddit}.json",
            "user": f"{Endpoints.user}/{username}/submitted.json",
            "search_subreddit": f"{Endpoints.subreddit}/{subreddit}/search.json?q={query}&restrict_sr=1",
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
            sanitiser=Sanitise.posts,
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
            "posts": Endpoints.base,
            "subreddits": Endpoints.subreddits,
            "users": Endpoints.users,
        }

        endpoint = search_map[kind]
        endpoint += f"/search.json"
        params = {"q": query, "limit": limit, "sort": sort, "raw_json": 1}

        sanitiser = Sanitise.posts if kind == "posts" else Sanitise.subreddits_or_users

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
            endpoint=f"{Endpoints.subreddit}/{name}/about.json",
        )
        sanitised_response = Sanitise.subreddit_or_user(response=response)

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
            "all": f"{Endpoints.subreddits}.json",
            "default": f"{Endpoints.subreddits}/default.json",
            "new": f"{Endpoints.subreddits}/new.json",
            "popular": f"{Endpoints.subreddits}/popular.json",
            "user_moderated": f"{Endpoints.user}/{kwargs.get('username')}/moderated_subreddits.json",
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
                sanitiser=Sanitise.subreddits_or_users,
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
            endpoint=f"{Endpoints.user}/{name}/about.json",
        )
        sanitised_response = Sanitise.subreddit_or_user(response=response)

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
            "all": f"{Endpoints.users}.json",
            "new": f"{Endpoints.users}/new.json",
            "popular": f"{Endpoints.users}/popular.json",
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
            sanitiser=Sanitise.subreddits_or_users,
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
            endpoint=f"{Endpoints.subreddit}/{subreddit}/wiki/{name}.json",
        )
        sanitised_response = Sanitise.wiki_page(response=response)

        return sanitised_response


# -------------------------------- END ----------------------------------------- #
