import aiohttp

from typing import Dict, Union, Optional
from rolimons.models import item, user
from rolimons.data_types import item_types, user_types
from helpers import pass_session
from rolimons import helpers
import errors

@pass_session
async def generic_item_info(session: Optional[aiohttp.ClientSession] = None) -> Union[Dict[str, item.ItemDetails], errors.Request.Failed]:        
    assert session
    async with session.get(item.BASE_GENERIC_ITEM_URL) as response:
        if response.status == 200:
            response_text = await response.text()
            extracted_variable: Dict[str, helpers.JSVariable] = helpers.JSVariableExtractor(response_text).extract()

            data = {}
            for item_id, data in extracted_variable[item.BASE_GENERIC_ITEM_VAR_NAME].value.items():
                extracted_variable[item.BASE_GENERIC_ITEM_VAR_NAME].value[item_id] = tuple(data)
            
            data_items: item_types.ItemDetails = extracted_variable[item.BASE_GENERIC_ITEM_VAR_NAME].value
            data = {
                item_id: item.ItemDetails(
                    item_name=raw[0],
                    acronym=raw[15],
                    asset_type_id=raw[1],
                    original_price=raw[2],
                    best_price=raw[5],
                    rap=raw[8],
                    value=raw[16],
                    created=raw[3],
                    first_timestamp=raw[4],
                    owners=raw[9],
                    bc_owners=raw[10],
                    copies = raw[11],
                    deleted_copies = raw[12],
                    bc_copies = raw[13],
                    num_sellers=raw[7],
                    hoarded_copies=raw[14],
                    favorited=raw[6],
                    demand=raw[17],
                    trend=raw[18],
                    projected=raw[19],
                    hyped=raw[20],
                    rare=raw[21],
                    thumbnail_url_lg=raw[23],
                )
                for item_id, raw in data_items.items()
            }
            return data
        else:
            raise errors.Request.Failed(f"URL: {item.BASE_GENERIC_ITEM_URL}, STATUS: {response.status}")
        
@pass_session
async def item_info(item_id: str, session: Optional[aiohttp.ClientSession] = None) -> Union[errors.Request.Failed, item.ItemDetails]:
    assert session
    url = item.BASE_ITEM_URL.replace("{ITEMID}", item_id)
    async with session.get(url) as response:
        if response.status == 200:            
            response_text = await response.text()
            extracted_variable = helpers.JSVariableExtractor(response_text).extract()
            del extracted_variable[item.BASE_ITEM_DETAILS_VAR_NAME].value["item_id"]
            del extracted_variable[item.BASE_ITEM_DETAILS_VAR_NAME].value["valuation_method"]
            for index in range(len(extracted_variable[item.BASE_VALUE_CHANGES_VAR_NAME].value)):
                extracted_variable[item.BASE_VALUE_CHANGES_VAR_NAME].value[index] = tuple(extracted_variable[item.BASE_VALUE_CHANGES_VAR_NAME].value[index])
            
            item_details: item_types.ItemDetailsData = extracted_variable[item.BASE_ITEM_DETAILS_VAR_NAME].value
            history_data: item_types.HistoryData = extracted_variable[item.BASE_HISTORY_DATA_VAR_NAME].value
            sales_data: item_types.SalesData = extracted_variable[item.BASE_SALES_DATA_VAR_NAME].value
            ownership_data: item_types.OwnershipData = extracted_variable[item.BASE_OWNERSHIP_DATA_VAR_NAME].value
            hoards_data: item_types.HoardsData = extracted_variable[item.BASE_HOARDS_DATA_VAR_NAME].value
            bc_copies_data: item_types.BCCopiesData = extracted_variable[item.BASE_BC_COPIES_VAR_NAME].value
            all_copies_data: item_types.AllCopiesData = extracted_variable[item.BASE_ALL_COPIES_VAR_NAME].value
            value_changes:  item_types.ValueChanges = extracted_variable[item.BASE_VALUE_CHANGES_VAR_NAME].value
            
            
            return item.ItemDetails(
                **item_details,
                history_data = helpers.Parse.Item.history_data(history_data),
                sales_data = helpers.Parse.Item.sales_data(sales_data),
                ownerships_data = helpers.Parse.Item.ownership_data(ownership_data),
                hoards_data = helpers.Parse.Item.hoards_data(hoards_data),
                bc_copies_data = helpers.Parse.Item.bc_copies_data(bc_copies_data),
                all_copies_data = helpers.Parse.Item.all_copies_data(all_copies_data),
                value_changes = helpers.Parse.Item.value_changes(value_changes)
            )
        else:
            raise errors.Request.Failed(f"URL: {url}, STATUS: {response.status}")

@pass_session
async def user_info(user_id: str, session: Optional[aiohttp.ClientSession] = None) -> Union[errors.Request.Failed, user.PlayerInfo]:
    assert session
    url = user.BASE_PLAYER_INFO_URL.replace("{ITEMID}", user_id)
    async with session.get(url) as response:
        if response.status == 200:
            response_text = await response.text()
            extracted_variable = helpers.JSVariableExtractor(response_text).extract()
            for item_id, data in extracted_variable[user.BASE_SCANNED_ASSETS_VAR_NAME].value.items():
                extracted_variable[user.BASE_PLAYER_DETAILS_VAR_NAME].value[item_id] = [
                    tuple(item_data) for item_data in data
                ]
                
            player_details_data: user_types.PlayerDetailsData = extracted_variable[user.BASE_PLAYER_DETAILS_VAR_NAME].value
            scanned_player_assets: user_types.ScannedPlayerAssets = extracted_variable[user.BASE_SCANNED_ASSETS_VAR_NAME].value
            chart_data: user_types.ChartData = extracted_variable[user.BASE_CHART_DATA_VAR_NAME].value
            
            return user.PlayerInfo(
                player_id = player_details_data["player_id"],
                player_name = player_details_data["player_name"],
                thumb_url_lg = player_details_data["thumb_url_lg"],
                bc_type = player_details_data["bc_type"],
                last_roblox_activity_ts = player_details_data["last_roblox_activity_ts"],
                trade_ad_count = player_details_data["trade_ad_count"],
                rank = player_details_data["rank"],
                staff_role = player_details_data["staff_role"],
                dev_staff_role = player_details_data["dev_staff_role"],
                wishlist = helpers.Parse.User.wish_list(player_details_data["wishlist"]),
                nft_list = helpers.Parse.User.nft_list(player_details_data["nft_list"]),
                asking_list = helpers.Parse.User.asking_list(player_details_data["asking_list"]),
                scanned_player_assets = helpers.Parse.User.scanned_player_assets(scanned_player_assets),
                chart_data = helpers.Parse.User.chart_data(chart_data)
            )
            
        else:
            raise errors.Request.Failed(f"URL: {url}, STATUS: {response.status}")