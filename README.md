# phtorg

`phtorg` is a CLI tool that organizes photos and videos into a clean, deterministic folder structure based on their original creation datetime (from EXIF and MediaInfo metadata) and a short hash (Git-style SHA-1 digest). It also helps detect duplicates by comparing timestamps, making it easier to clean up messy exports from iOS or Google Photos.

Originally designed for handling iOS exports where every file is generically named (e.g. `IMG_1234.JPG`), `phtorg` renames and relocates each file into a more meaningful and unique structure. For example:

```
IMG_1234.JPG → Camera_Roll/2024/IMG_20241231_131415_a1b2c3d.jpg
```

Each file gets a unique, timestamp-based name for long-term organization.

## Example Use Case: Monthly iPhone Export

Alice regularly exports photos and videos from her iPhone into a folder like `2025-03.import`. She uses `phtorg` to organize and clean up the export in two steps:

1. **Move files with reliable creation dates**

   First, she organizes the photos and videos that have valid EXIF or MediaInfo timestamps into the main `Camera_Roll` archive:

   ```bash
   phtorg organize 2025-03.import -d Camera_Roll
   ```

   This step renames and relocates files into `Camera_Roll` folder.

2. **Handle remaining files with no reliable datetime**

   Some files are left behind — usually screenshots or media saved from messaging apps whose EXIF/MediaInfo are not available. To organize those using the file's modification time (mtime) as a fallback, she runs:

   ```bash
   phtorg organize --allow-mtime 2025-03.import -d Misc_Media
   ```

   This step renames and relocates files into `Misc_Media` folder.

   After this step, the import folder is empty, and all media has been organized into appropriate folders.
