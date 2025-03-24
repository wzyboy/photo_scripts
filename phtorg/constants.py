# These constants control how the deterministic filename is computed.
# Monkey-patch this module to get a different behaviour.

# By default, a deterministic filename is:
# {prefix}_{datetime}_{hash}{ext}
# For example:
# IMG_20250323_123456_a1b2c3d.jpg

DEFAULT_PREFIX = 'IMG_'
SCREENSHOT_PREFIX = 'Screenshot_'
DATETIME_FMT = '%Y%m%d_%H%M%S'
