from typing import Dict, List, Tuple, Optional, TypedDict, Literal, Union

BASE_PLAYER_DETAILS_URL = "https://www.rolimons.com/player/{USERID}"
BASE_PLAYER_DETAILS_VAR_NAME = "scanned_player_assets"

BASE_PLAYER_DETAILS_API_URL = "https://api.rolimons.com/players/v1/playerassets/{USERID}"

ScannedPlayerAssets = Dict[str, 
    List[Tuple[
        int,           # uaid
        Optional[int], # serial
        int,           # created since
        int,           # owned since        
    ]]
]

class Badges(TypedDict, total=False):
    value_20m: int
    value_10m: int
    value_5m: int
    value_1m: int
    value_500k: int
    value_100k: int

    roli_award_winner: int
    roli_award_nominee: int
    own_lucky_cat_uaid: int

    own_1_serial_1: int
    own_1_serial_1337: int
    own_1_sequential_serial: int
    own_1_serial_1_to_9: int

    own_1_big_dominus: int
    own_1_dominus: int
    own_1_stf: int
    own_1_valued_federation_item: int
    own_1_immortal_sword: int
    own_epic_katana_set: int
    own_1_kotn_item: int

    own_15_noob: int
    own_5_noob: int
    own_10_rares: int
    own_3_rares: int
    own_1_rare: int

    create_10000_trade_ads: int
    create_1000_trade_ads: int
    create_100_trade_ads: int
    create_10_trade_ads: int

    own_all_asset_types: int
    own_50_pct_of_1_item: int
    own_25_pct_of_1_item: int
    own_10_pct_of_1_item: int

    own_100_of_1_item: int
    own_50_of_1_item: int
    own_10_of_1_item: int

    own_1000_items: int
    own_100_items: int
    own_10_items: int

    contributor: int
    sword_fighting_champion: int
    event_winner: int
    game_night_winner: int

    booster: int
    verified: int
    roligang: int

class PlayerDetails(TypedDict):
    success: bool
    playerTerminated: bool  
    playerPrivacyEnabled: bool
    playerVerified: bool
    playerId: int
    chartNominalScanTime: int
    playerAssets: Dict[str, List[int]]
    isOnline: bool
    presenceType: int
    lastOnline: Literal[None]
    lastLocation: Union[Literal["Website"], str]
    lastPlaceId: Literal[None]
    locationGameIsTracked: Literal[False]
    premium: bool
    badges: Badges
    holds: List[int]
    