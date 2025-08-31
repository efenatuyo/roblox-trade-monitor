from typing import TypedDict, Literal, Optional, Tuple, Dict, List, Union

BASE_GENERIC_ITEM_URL = "https://www.rolimons.com/catalog"
BASE_GENERIC_ITEM_VAR_NAME = "item_details"

BASE_GENERIC_ITEM_INFO_URL = "https://www.rolimons.com/item/{ITEMID}"
BASE_GENERIC_ITEM_INFO_VAR_NAME = "bc_copies_data"

BAE_GENERIC_UAID_INFO_URL = "https://www.rolimons.com/uaid/{ITEMID}"

DemandLevel = Literal[0, 1, 2, 3, 4]
TrendLevel = Literal[0, 1, 2, 3, 4]

class ItemDetailsData(TypedDict):
    item_name: str
    asset_type_id: int
    original_price: int
    created: int
    first_timestamp: int
    best_price: int
    favorited: int
    num_sellers: int
    rap: int
    owners: int
    bc_owners: int
    copies: int
    deleted_copies: int
    bc_copies: int
    hoarded_copies: int
    acronym: Optional[str]
    value: Optional[int]
    demand: Optional[DemandLevel]
    trend: Optional[TrendLevel]
    projected: Optional[Literal[1]]
    hyped: Optional[Literal[1]]
    rare: Optional[Literal[1]]
    thumbnail_url_lg: str


ItemTuple = Tuple[
    str,               # 0: item_name
    int,               # 1: asset_type_id
    int,               # 2: original_price
    int,               # 3: created (timestamp)
    int,               # 4: first_timestamp
    int,               # 5: best_price
    int,               # 6: favorited (count)
    int,               # 7: num_sellers
    int,               # 8: rap (recent average price)
    int,               # 9: owners (number of owners)
    int,               # 10: bc_owners (Builders Club owners)
    int,               # 11: copies (total copies)
    int,               # 12: deleted_copies (copies removed)
    int,               # 13: bc_copies (BC copies)
    int,               # 14: hoarded_copies
    Optional[str],     # 15: acronym (optional short code or tag)
    Optional[int],     # 16: value (optional price estimate)
    Optional[DemandLevel],  # 17: demand level (enum or custom type)
    Optional[TrendLevel],   # 18: trend level (enum or custom type)
    Optional[Literal[1]],   # 19: projected (flag, e.g., 1 if projected)
    Optional[Literal[1]],   # 20: hyped (flag, e.g., 1 if hyped)
    Optional[Literal[1]],   # 21: rare (flag, e.g., 1 if rare)
    int,               # 22: value if avaible else rap
    str                # 23: thumbnail_url_lg (URL to large thumbnail image)
]

ItemDetails = Dict[str, ItemTuple]

class BCCopiesData(TypedDict):
    num_bc_copies: int
    owner_ids: List[int]
    owner_names: List[str]
    quantities: List[int]
    owner_bc_levels: List[Literal[450]]
    bc_uaids: List[str]
    bc_serials: List[Optional[int]]
    bc_updated: List[int]
    bc_presence_update_time: List[int]
    bc_last_online: List[int]

ItemsReceived = List[Tuple[
    int, # item id
    int  # uaid
]]

NewItemOwners = List[Tuple[
    int,  # uaid
    int,  # owner id
    int   # time happened
]]