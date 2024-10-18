import asyncio
import time
from random import randint
from typing import Callable, Literal, Union, Optional, List, Dict

from aiohttp import ClientSession
from karmakaze.sanitise import Sanitise

from .dummy import Status
from .endpoints import Endpoints

__all__ = ["Reddit"]


class Reddit:
    """Represents the Reddit API accessible tp Knew Karma and provides methods for getting related data."""

    SORT = Literal["controversial", "new", "top", "best", "hot", "rising", "all"]
    TIMEFRAME = Literal["hour", "day", "week", "month", "year", "all"]
    TIME_FORMAT = Literal["concise", "locale"]

    def __init__(self, headers: Optional[Dict] = None):
        self._headers = headers

    async def on_session(
        self, session: ClientSession, endpoint: str, params: Optional[Dict] = None
    ) -> Union[Dict, List, bool, None]:

        try:
            async with session.get(
                url=endpoint, headers=self._headers, params=params
            ) as response:
                response.raise_for_status()
                response_data: Union[Dict, List] = await response.json()
                return response_data

        except Exception as error:
            raise error

    async def _paginate_items(
        self,
        session: ClientSession,
        endpoint: str,
        limit: int,
        sanitiser: Callable,
        status: Optional[Status] = None,
        params: Optional[Dict] = None,
        is_post_comments: Optional[bool] = False,
    ) -> List[Dict]:

        # Initialise an empty list to store all items across paginated requests.
        all_items: List = []
        # Initialise the ID of the last item fetched to None (used for pagination).
        last_item_id = None

        # Continue fetching data until the limit is reached or no more items are available.
        while len(all_items) < limit:
            # Make an asynchronous request to the endpoint.
            response = await self.on_session(
                session=session,
                endpoint=(
                    f"{endpoint}?after={last_item_id}&count={len(all_items)}"
                    if last_item_id
                    else endpoint
                ),
                params=params,
            )
            if is_post_comments:
                items = self._process_post_comments(response=response)
            else:

                # If not handling comments, simply extract the items from the response.
                items = sanitiser(response)

                # If no items are found, break the loop as there's nothing more to fetch.
                if not items:
                    break

                # Determine how many more items are needed to reach the limit.
                items_to_limit = limit - len(all_items)

                # Add the processed items to the all_items list, up to the specified limit.
                all_items.extend(items[:items_to_limit])

                # Update the last_item_id to the ID of the last fetched item for pagination.
                last_item_id = (
                    Sanitise.pagination_id(response=response[1])
                    if is_post_comments
                    else Sanitise.pagination_id(response=response)
                )

                # If we've reached the specified limit, break the loop.
                if len(all_items) == limit:
                    break

                # Introduce a random sleep duration between 1 and 5 seconds to avoid rate-limiting.
                sleep_duration = randint(1, 5)

                # If a status object is provided, use it to display a countdown timer.
                if status:
                    await self._pagination_countdown_timer(
                        status=status,
                        duration=sleep_duration,
                        current_count=len(all_items),
                        overall_count=limit,
                    )
                else:
                    # Otherwise, just sleep for the calculated duration.
                    await asyncio.sleep(sleep_duration)

        # Return the list of all fetched and processed items (without duplicates).
        return all_items

    async def _paginate_more_items(
        self,
        session: ClientSession,
        more_items_ids: List[str],
        endpoint: str,
        fetched_items: List[Dict],
    ):
        for more_id in more_items_ids:
            # Construct the endpoint for each additional comment ID.
            more_endpoint = f"{endpoint}&comment={more_id}"
            # Make an asynchronous request to fetch the additional comments.
            more_response = await self.on_session(
                session=session, endpoint=more_endpoint
            )
            # Extract the items (comments) from the response.
            more_items, _ = Sanitise.comments(
                response=more_response[1].get("data", {}).get("children", [])
            )

            # Add the fetched items to the main items list.
            fetched_items.extend(more_items)

    async def _process_post_comments(self, response):
        # If the request is for post comments, handle the response accordingly.
        items = []  # Initialise a list to store fetched items.
        more_items_ids = []  # Initialise a list to store IDs from "more" items.

        # Iterate over the children in the response to extract comments or "more" items.
        for item in response[1].get("data").get("children"):
            if Sanitise.kind(item) == "t1":
                sanitised_item = Sanitise.comments(item)

                # If the item is a comment (kind == "t1"), add it to the items list.
                items.append(sanitised_item)
            elif Sanitise.kind(item) == "more":
                # If the item is of kind "more", extract the IDs for additional comments.
                more_items_ids.extend(item)

        # If there are more items to fetch (kind == "more"), make additional requests.
        if more_items_ids:
            await self._paginate_more_items(
                session=session,
                fetched_items=items,
                more_items_ids=more_items_ids,
                endpoint=endpoint,
            )

        return items

    @staticmethod
    async def _pagination_countdown_timer(
        duration: int,
        current_count: int,
        overall_count: int,
        status: Optional[Status] = None,
    ):

        end_time: float = time.time() + duration
        while time.time() < end_time:
            remaining_time: float = end_time - time.time()
            remaining_seconds: int = int(remaining_time)
            remaining_milliseconds: int = int(
                (remaining_time - remaining_seconds) * 100
            )

            countdown_text: str = (
                f"[cyan]{current_count}[/] (of [cyan]{overall_count}[/]) items fetched so far. "
                f"Resuming in [cyan]{remaining_seconds}.{remaining_milliseconds:02}[/] seconds"
            )

            (
                status.update(countdown_text)
                if status
                else print(countdown_text.strip("[,],/,cyan"))
            )
            await asyncio.sleep(0.01)  # Sleep for 10 milliseconds

    async def infra_status(
        self, session: ClientSession, **kwargs
    ) -> Union[List[Dict], None]:

        notify = kwargs.get("notify")
        status = kwargs.get("status")

        if status:
            status.update(f"Checking Reddit [bold]API/Infrastructure[/] status")

        status_response: Dict = await self.on_session(
            endpoint=Endpoints.infra_status, session=session
        )

        indicator = status_response.get("status").get("indicator")
        description = status_response.get("status").get("description")
        if description:
            if indicator == "none":

                notify.ok(description) if notify else print(description)
            else:
                status_message = f"{description} ([yellow]{indicator}[/])"
                (
                    notify.warning(status_message)
                    if notify
                    else print(status_message.strip("[,],/,yellow"))
                )  # TODO: remove the colours in print

                if status:
                    status.update("Getting status components")

                status_components: Dict = await self.on_session(
                    endpoint=Endpoints.infra_components,
                    session=session,
                )

                if isinstance(status_components, Dict):
                    components: List[Dict] = status_components.get("components")

                    return components

    async def post(
        self,
        id: str,
        subreddit: str,
        session: ClientSession,
        status: Optional[Status] = None,
    ) -> Dict:
        if status:
            status.update(f"Getting data from post with id {id} in r/{subreddit}")

        response = await self.on_session(
            endpoint=f"{Endpoints.subreddit}/{subreddit}/comments/{id}.json",
            session=session,
        )
        sanitised_response = Sanitise.post(response=response)

        return sanitised_response

    async def subreddit(
        self, name: str, session: ClientSession, status: Optional[Status] = None
    ) -> Dict:
        if status:
            status.update(f"Getting data from subreddit r/{name}")

        esponse = await self.on_session(
            endpoint=f"{Endpoints.subreddit}/{name}/about.json",
            session=session,
        )
        sanitised_response = Sanitise.subreddit_or_user(response=response)

        return sanitised_response

    async def user(
        self, name: str, session: ClientSession, status: Optional[Status] = None
    ) -> Dict:
        if status:
            status.update(f"Getting data from user u/{name}")

        esponse = await self.on_session(
            endpoint=f"{Endpoints.user}/{name}/about.json",
            session=session,
        )
        sanitised_response = Sanitise.subreddit_or_user(response=response)

        return sanitised_response

    async def wiki_page(
        self,
        name: str,
        subreddit: str,
        session: ClientSession,
        status: Optional[Status] = None,
    ) -> Dict:
        if status:
            status.update(f"Getting data from wikipage {name} in r/{subreddit}")

        esponse = await self.on_session(
            endpoint=f"{Endpoints.subreddit}/{subreddit}/wiki/{kwargs.get('page_name')}.json",
            session=session,
        )
        sanitised_response = Sanitise.wiki_page(response=response)

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
        status: Optional[Status],
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

        posts = await self._paginate_items(
            session=session,
            endpoint=endpoint,
            params=(
                params.update({"q": query, "restrict_sr": 1})
                if kind == "search_subreddit"
                else params
            ),
            limit=limit,
            sanitiser=Sanitise.posts,
            status=status,
        )

        return posts

    async def comments(
        self,
        session: ClientSession,
        kind: Literal["user_overview", "user", "post"],
        limit: int,
        sort: SORT,
        timeframe: TIMEFRAME,
        status: Optional[Status] = None,
        **kwargs: str,
    ) -> List[Dict]:

        comments_map = {
            "user_overview": f"{Endpoints.user}/{username}/overview.json",
            "user": f"{Endpoints.user}/{username}/comments.json",
            "post": f"{Endpoints.subreddit}/{subreddit}"
            f"/comments/{kwargs.get('id')}.json",
        }

        if status:
            status.update(f"Getting {limit} {kind} comments")

        endpoint = comments_map[kind]
        params = {"limit": limit, "sort": sort, "t": timeframe, "raw_json": 1}

        comments = self._paginate_items(
            session=session,
            endpoint=endpoint,
            parmas=params,
            limit=limit,
            sanitiser=Sanitise.comments,
            status=status,
            is_post_comments=True if kind == "post" else False,
        )

        return comments

    async def subreddits(
        self,
        session: ClientSession,
        kind: Literal["all", "default", "new", "popular", "user_moderated"],
        limit: int,
        timeframe: TIMEFRAME,
        status: Optional[Status] = None,
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
            subreddits = await self.on_session(
                endpoint=endpoint,
                session=session,
            )
        else:
            params.update({"limit": limit, "t": timeframe})
            subreddits = await self._paginate_items(
                session=session,
                endpoint=endpoint,
                params=params,
                sanitiser=Sanitise.subreddits_or_users,
                limit=limit,
                status=status,
            )

        return subreddits

    async def users(
        self,
        session: ClientSession,
        kind: Literal["all", "popular", "new"],
        limit: int,
        timeframe: TIMEFRAME,
        status: Optional[Status] = None,
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

        users = await self._paginate_items(
            session=session,
            endpoint=endpoint,
            params=params,
            sanitiser=Sanitise.subreddits_or_users,
            limit=limit,
            status=status,
        )

        return users

    async def search(
        self,
        session: ClientSession,
        kind: Literal["users", "subreddits", "posts"],
        query: str,
        limit: int,
        sort: SORT,
        status: Optional[Status] = None,
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

        search_results = await self._paginate_items(
            session=session,
            endpoint=endpoint,
            params=params,
            sanitiser=sanitiser,
            limit=limit,
            status=status,
        )

        return search_results


# -------------------------------- END ----------------------------------------- #
