# phtorg

`phtorg` is a CLI tool that organizes photos and videos into a clean, deterministic folder structure based on their original creation datetime (from EXIF and MediaInfo metadata) and a short hash (Git-style SHA-1 digest). It also helps detect duplicates by comparing timestamps, making it easier to clean up messy exports from iOS or Google Photos.

Originally designed for handling iOS exports where every file is generically named (e.g. `IMG_1234.JPG`), phtorg renames and relocates each file into a more meaningful and unique structure. For example:

```
IMG_1234.JPG → Camera_Roll/2024/IMG_20241231_131415_a1b2c3d.jpg
```

Each file gets a unique, timestamp-based name for long-term organization.
