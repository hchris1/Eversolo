"""Constants for eversolo."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Eversolo"
DOMAIN = "eversolo"
ATTRIBUTION = ""

DEFAULT_PORT = 9529
DEFAULT_UPDATE_INTERVAL = 1

CONF_NET_MAC = "net_mac"
CONF_MODEL = "model"
CONF_FIRMWARE = "firmware"
CONF_ABLE_REMOTE_BOOT = "able_remote_boot"
