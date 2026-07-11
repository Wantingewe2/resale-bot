from bot.platforms.depop import DepopPlatform
from bot.platforms.ebay import EbayPlatform
from bot.platforms.mercari import MercariPlatform
from bot.platforms.vinted import VintedPlatform

PLATFORM_REGISTRY = {
    "ebay": EbayPlatform,
    "mercari": MercariPlatform,
    "depop": DepopPlatform,
    "vinted": VintedPlatform,
}
