# Divoom Playlist

Experimental separate Home Assistant integration for playing GIFs from a folder
through the existing `hass-divoom` integration.

## Status

This is a work in progress, not an installable release. Only the standalone
playlist logic has been tested; the Home Assistant integration, Bluetooth
transfer, installation and live media-folder access have not been verified.

The intended behaviour is to play direct GIF children of a directory in
alphabetical or random order, at a configurable duration, and rescan the
directory at the beginning of each repeating cycle. The intended root directory
is `/config/pixelart`, matching the default Divoom configuration. The user must
arrange for this directory and the Nextcloud media folder to refer to the same
content before testing in Home Assistant.

Event priorities, motion detection and ringing are outside this prototype.
