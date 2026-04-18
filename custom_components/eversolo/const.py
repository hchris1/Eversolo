"""Constants for eversolo."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Eversolo"
DOMAIN = "eversolo"
ATTRIBUTION = ""

DEFAULT_PORT = 9529
DEFAULT_UPDATE_INTERVAL = 2

CONF_NET_MAC = "net_mac"
CONF_MODEL = "model"
CONF_FIRMWARE = "firmware"
CONF_ABLE_REMOTE_BOOT = "able_remote_boot"
CONF_SHUTDOWN_ACTION = "shutdown_action"

SHUTDOWN_ACTION_POWEROFF = "poweroff"
SHUTDOWN_ACTION_STANDBY = "standby"
SHUTDOWN_ACTION_OPTIONS = [SHUTDOWN_ACTION_POWEROFF, SHUTDOWN_ACTION_STANDBY]
DEFAULT_SHUTDOWN_ACTION = SHUTDOWN_ACTION_POWEROFF
