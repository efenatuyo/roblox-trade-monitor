from helpers import pass_session, DBHelper
from trademonitor import helpers
import errors
from trademonitor.data_types import item_types, user_types
from datetime import datetime, timezone, timedelta
from typing import Union, List, Tuple, Optional

import aiohttp
import asyncio
import uuid

class Monitor:
    def __init__(self, db: DBHelper):
        self.check_after_time = int((datetime.now(timezone.utc) - timedelta(hours=10)).timestamp() * 1000)
        self.last_iteration_time: List[int] = []
        self.db = db

    @staticmethod
    @pass_session
    async def get_limited_ids(session: Optional[aiohttp.ClientSession] = None) -> Union[errors.Request.Failed, item_types.ItemDetails]:
        assert session
        async with session.get(item_types.BASE_GENERIC_ITEM_URL) as response:
            if response.status == 200:
                extracted_vars = helpers.JSVariableExtractor(await response.text()).extract()
                return extracted_vars[item_types.BASE_GENERIC_ITEM_VAR_NAME].value
            raise errors.Request.Failed(f"URL: {item_types.BASE_GENERIC_ITEM_URL}, STATUS: {response.status}")

    @staticmethod
    @pass_session
    async def get_limited_item_info(item_id: str, session: Optional[aiohttp.ClientSession] = None) -> Union[errors.Request.Failed, item_types.BCCopiesData]:
        assert session
        url = item_types.BASE_GENERIC_ITEM_INFO_URL.replace("{ITEMID}", item_id)
        async with session.get(url) as response:
            if response.status == 200:
                extracted_vars = helpers.JSVariableExtractor(await response.text()).extract()
                return extracted_vars[item_types.BASE_GENERIC_ITEM_INFO_VAR_NAME].value
            raise errors.Request.Failed(f"URL: {url}, STATUS: {response.status}")

    def new_owners(self, bc_copies: item_types.BCCopiesData, check_after_time: int) -> item_types.NewItemOwners:
        items = []
        for i, last_updated in enumerate(bc_copies["bc_updated"]):
            if last_updated > check_after_time:
                self.last_iteration_time.append(last_updated)
                items.append((int(bc_copies["bc_uaids"][i]), int(bc_copies["owner_ids"][i]), last_updated))
        return items

    @staticmethod
    @pass_session
    async def get_uaid_past_owners(uaid: Union[int, str], session: Optional[aiohttp.ClientSession] = None) -> List[str]:
        assert session
        url = item_types.BAE_GENERIC_UAID_INFO_URL.replace("{ITEMID}", str(uaid))
        async with session.get(url) as response:
            html = await response.text()
        return [str(uid) for uid in helpers._extract_past_owners(html)]

    async def check_uaid_avaible_for_trade(self, uaid: str) -> bool:
        return await self.db.can_uaid_be_traded(int(uaid))
    
    @pass_session
    async def possible_items_received(self, user_id: Union[int, str], time_occured: int, session: Optional[aiohttp.ClientSession] = None) -> item_types.ItemsReceived:
        assert session
        user_id = str(user_id)
        html_url = user_types.BASE_PLAYER_DETAILS_URL.replace("{USERID}", user_id)
        api_url = user_types.BASE_PLAYER_DETAILS_API_URL.replace("{USERID}", user_id)

        async with session.get(html_url) as html_response:
            if html_response.status != 200:
                raise errors.Request.Failed(f"URL: {html_url}, STATUS: {html_response.status}")
            extracted_vars = helpers.JSVariableExtractor(await html_response.text()).extract()
            user_assets_html: user_types.ScannedPlayerAssets = extracted_vars[user_types.BASE_PLAYER_DETAILS_VAR_NAME].value

        async with session.get(api_url) as api_response:
            if api_response.status != 200:
                raise errors.Request.Failed(f"URL: {api_url}, STATUS: {api_response.status}")
            user_assets_api: user_types.PlayerDetails = await api_response.json()

        possible_items = []

        for item_id, item_uaids in user_assets_api["playerAssets"].items():
            for item_uaid in item_uaids:
                if str(item_uaid) not in [str(item_data[0]) for item_data in user_assets_html.get(item_id, [])]:
                    if await self.check_uaid_avaible_for_trade(str(item_uaid)):
                        possible_items.append((int(item_id), int(item_uaid)))

        for item_id, item_datas in user_assets_html.items():
            for item_data in item_datas:
                if await self.check_uaid_avaible_for_trade(str(item_data[0])):
                    if abs(time_occured - item_data[3]) <= 600000:
                        possible_items.append((int(item_id), int(item_data[0])))

        return possible_items

    async def deep_check_items_received(self, predicted_items_received: item_types.ItemsReceived, receiver_id: Union[int, str], sender_id: Union[int, str]) -> item_types.ItemsReceived:
        receiver_id, sender_id = str(receiver_id), str(sender_id)
        received_items = []

        for item_data in predicted_items_received:
            past_owners = await self.get_uaid_past_owners(item_data[1])
            try:
                sender_index = past_owners.index(sender_id)
            except ValueError:
                continue

            try:
                receiver_index = past_owners.index(receiver_id)
            except ValueError:
                receiver_index = None

            if (sender_index == 0 and receiver_index is None) or \
               (receiver_index is not None and receiver_index - sender_index == -1):
                received_items.append(item_data)

        return received_items

    async def process_items_batch(self, item_ids: List[str]) -> None:
        for item_id in item_ids:
            try:
                item_info = await self.get_limited_item_info(item_id)
                assert not isinstance(item_info, errors.Request.Failed)

                for uaid, owner_id, time_occured in self.new_owners(item_info, self.check_after_time):
                    old_owners = await self.get_uaid_past_owners(uaid)
                    try:
                        current_index = old_owners.index(str(owner_id))
                    except ValueError:
                        current_index = None

                    old_index = current_index + 1 if current_index is not None else 0
                    if old_index >= len(old_owners):
                        continue

                    old_owner_id = old_owners[old_index]
                    if old_owner_id == str(owner_id):
                        continue

                    possible_received = await self.possible_items_received(owner_id, time_occured)
                    possible_sent = await self.possible_items_received(old_owner_id, time_occured)

                    if not (possible_received and possible_sent):
                        continue

                    items_received = await self.deep_check_items_received(possible_received, owner_id, old_owner_id)
                    items_sent = await self.deep_check_items_received(possible_sent, old_owner_id, owner_id)

                    if items_received and items_sent:
                        trade_id = str(uuid.uuid4())
                        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
                        
                        await self.db.insert_trade(trade_id, str(owner_id), str(old_owner_id), timestamp)

                        for item_id, uaid in items_received:
                            await self.db.insert_trade_item(trade_id, str(owner_id), item_id, uaid, True)

                        for item_id, uaid in items_sent:
                            await self.db.insert_trade_item(trade_id, str(old_owner_id), item_id, uaid, False)

            except Exception as e:
                print(f"Error processing item {item_id}: {e}")

        if self.last_iteration_time:
            self.check_after_time = max(self.last_iteration_time)

    async def __call__(self):
        while True:
            try:
                items = await self.get_limited_ids()
                assert not isinstance(items, errors.Request.Failed)
                item_ids = list(items)
                chunk_size = max(1, len(item_ids) // 10)
                tasks = []

                for i in range(0, len(item_ids), chunk_size):
                    chunk = item_ids[i:i + chunk_size]
                    tasks.append(asyncio.create_task(self.process_items_batch(chunk)))

                await asyncio.gather(*tasks)

            except Exception as e:
                print(f"Main loop error: {e}")

            finally:
                if self.last_iteration_time:
                    earliest = min(self.last_iteration_time)
                    if earliest > self.check_after_time:
                        self.check_after_time = earliest
                        self.last_iteration_time = []
