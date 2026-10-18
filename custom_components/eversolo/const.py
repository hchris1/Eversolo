"""Constants for eversolo."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "Eversolo"
DOMAIN = "eversolo"
ATTRIBUTION = ""

DEFAULT_PORT = 9529
DEFAULT_UPDATE_INTERVAL = 2
SETTINGS_UPDATE_INTERVAL = 30
# A streamer busy decoding can miss a two-second poll; keep the last state for
# a few of them instead of flapping the entities and logging an error.
TOLERATED_FAILED_POLLS = 3

DEFAULT_POWER_BEHAVIOR = "poweroff"
POWER_BEHAVIOR_STANDBY = "standby"
POWER_BEHAVIORS = (DEFAULT_POWER_BEHAVIOR, POWER_BEHAVIOR_STANDBY)
CONF_POWER_BEHAVIOR = "power_behavior"

WOL_PORTS = (9517, 9)

CONF_NET_MAC = "net_mac"
CONF_MODEL = "model"
CONF_FIRMWARE = "firmware"
CONF_ABLE_REMOTE_BOOT = "able_remote_boot"
CONF_ABLE_REMOTE_SLEEP = "able_remote_sleep"
CONF_ABLE_REMOTE_SHUTDOWN = "able_remote_shutdown"
CONF_ABLE_REMOTE_REBOOT = "able_remote_reboot"
