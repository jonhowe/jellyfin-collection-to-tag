# Jellyfin Collection to Tag

Synchronize a Jellyfin collection to a Jellyfin metadata tag.

This utility takes all media contained in a Jellyfin collection and applies a specified tag to those items. For TV content, it can recursively apply the tag to the series, seasons, and episodes.

The primary use case is creating curated media access for Jellyfin users without moving or duplicating media files.

For example:

```text
James Movies collection
├── Anastasia
├── Inside Out
├── Moana
├── Ratatouille
└── Toy Story
        │
        ▼
sync-collections-with-tag.py
        │
        ▼
Jellyfin metadata
├── Anastasia       [James]
├── Inside Out      [James]
├── Moana           [James]
├── Ratatouille     [James]
└── Toy Story       [James]
```

The `James` tag can then be used with Jellyfin's parental controls to restrict a user to approved content.

## Features

- Uses a Jellyfin collection as the source of approved media
- Applies a configurable Jellyfin tag
- Supports movies
- Supports TV series, seasons, and episodes
- Recursively expands TV series into their child content
- Preserves existing tags
- Does not remove existing tags
- Does not modify or move media files
- Supports dry-run mode
- Supports limiting the number of processed items for testing
- Supports command-line configuration
- Supports defaults configured directly in the script
- Reads the Jellyfin API key from an environment variable
- Compatible with Jellyfin 12.x API authentication
- Stops processing on API/update errors rather than continuing blindly
- Safe to run repeatedly

## Requirements

- Python 3
- `requests`
- Jellyfin server
- Jellyfin API key
- Jellyfin user ID with sufficient access to the media

The script has been tested against:

```text
Jellyfin 12.2.0
```

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd jellyfin-collection-to-tag
```

Install the Python dependency:

```bash
python3 -m pip install requests
```

On systems where `requests` is provided by the OS package manager, it may already be installed.

For Ubuntu/Debian:

```bash
sudo apt install python3-requests
```

## Jellyfin API Key

Create an API key in Jellyfin:

```text
Dashboard
  → Advanced
  → API Keys
  → +
```

Give it a recognizable name such as:

```text
CollectionToTag
```

The API key is intentionally **not stored in the script**.

Set it using the `JELLYFIN_API_KEY` environment variable:

```bash
export JELLYFIN_API_KEY='your-api-key'
```

Verify that the variable exists without displaying the key:

```bash
[ -n "$JELLYFIN_API_KEY" ] && echo "API key is set" || echo "API key is NOT set"
```

The environment variable only exists for the current shell session unless you configure it persistently.

## Jellyfin User ID

Jellyfin 12 requires user context when retrieving individual media items through the API.

You therefore need the ID of a Jellyfin user with access to the media being managed.

You can retrieve the available users with:

```bash
curl -s \
  -H "Authorization: MediaBrowser Client=\"CollectionToTag\", Device=\"NUC\", DeviceId=\"jellyfin-collection-to-tag\", Version=\"1.0.0\", Token=\"$JELLYFIN_API_KEY\"" \
  'https://YOUR-JELLYFIN-SERVER/Users' \
  | python3 -c 'import sys,json; users=json.load(sys.stdin); [(print(u["Name"], u["Id"], "admin=" + str(u.get("Policy", {}).get("IsAdministrator", False)))) for u in users]'
```

A Jellyfin user ID should look similar to:

```text
0123456789abcdef0123456789abcdef
```

It should contain 32 characters.

You can either configure the user ID directly in the script:

```python
DEFAULT_USER_ID = "0123456789abcdef0123456789abcdef"
```

or provide it on the command line:

```bash
python3 sync-collections-with-tag.py \
  --user-id "0123456789abcdef0123456789abcdef"
```

You can also store it in an environment variable for convenience:

```bash
export JELLYFIN_USER_ID='0123456789abcdef0123456789abcdef'
```

and then use:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID"
```

Unlike the API key, the user ID is not an authentication secret.

## Configuration

Defaults can be configured near the top of the script:

```python
DEFAULT_JELLYFIN_URL = "https://jellyfin.example.com"

DEFAULT_USER_ID = None

DEFAULT_COLLECTION = "James Movies"

DEFAULT_TAG = "James"

DEFAULT_CLIENT_NAME = "CollectionToTag"
DEFAULT_DEVICE_NAME = "NUC"
DEFAULT_DEVICE_ID = "jellyfin-collection-to-tag"
DEFAULT_CLIENT_VERSION = "1.0.0"
```

Most settings can also be overridden on the command line.

Command-line options take precedence over script defaults.

For example:

```python
DEFAULT_JELLYFIN_URL = "https://jellyfin.example.com"
```

can be overridden with:

```bash
python3 sync-collections-with-tag.py \
  --url "http://jellyfin.home.lan:8096"
```

## Usage

Display available options:

```bash
python3 sync-collections-with-tag.py --help
```

### Dry Run

Always start with a dry run:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

A dry run performs all Jellyfin reads and determines what would change, but does not modify metadata.

Example:

```text
Connecting to Jellyfin at https://jellyfin.example.com ...
Connected to: jellyfin.home.lan
Jellyfin version: 12.2.0

Looking for collection: James Movies
Found collection: James Movies
Collection ID:    4c23fa5f63391bca9e09cd2882290a16

Collection contains 35 item(s).

Items that should have tag "James":
  Movie        35

Total items: 35

========================================
 DRY RUN - NO CHANGES WILL BE MADE
========================================

[   1/35] WOULD TAG       Movie      Anastasia
[   2/35] WOULD TAG       Movie      A Charlie Brown Christmas
[   3/35] WOULD TAG       Movie      DuckTales: The Movie - Treasure of the Lost Lamp
...
[  22/35] already tagged  Movie      PAW Patrol: The Dino Movie
...
[  35/35] WOULD TAG       Movie      Wonka

========================================
 COMPLETE
========================================
Items processed:      35
Would tag:            34
Already tagged:       1

No changes were made.
```

## Apply Tags

After validating the dry-run output:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID"
```

The script will apply the configured tag to items that do not already have it.

Existing tags are preserved.

For example, an item containing:

```text
Animation
Disney
```

that receives the `James` tag will contain:

```text
Animation
Disney
James
```

## Testing with `--limit`

Before updating an entire collection, it is recommended to test a single item:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID" \
  --limit 1
```

This processes only the first item.

For example:

```text
LIMIT ENABLED: processing only 1 of 35 item(s).

[   1/1] TAGGED          Movie      Anastasia
```

You can then verify the result using another dry run:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

The item should now appear as:

```text
[   1/35] already tagged  Movie      Anastasia
```

This confirms that the complete read/write cycle is working before modifying the rest of the collection.

You can test multiple items with:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID" \
  --limit 5
```

## Override Jellyfin URL

The configured Jellyfin URL can be overridden using `--url`.

For example:

```bash
python3 sync-collections-with-tag.py \
  --url "http://192.168.1.100:8096" \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

or:

```bash
python3 sync-collections-with-tag.py \
  --url "http://jellyfin.home.lan:8096" \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

This is useful when the script is running on the same network as Jellyfin and you want to bypass a reverse proxy.

## Override Collection

The default collection can be overridden with:

```bash
python3 sync-collections-with-tag.py \
  --collection "James TV" \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

For example, the same script can manage:

```text
James Movies
James TV
```

without modifying the script.

## Override Tag

The tag can be overridden with:

```bash
python3 sync-collections-with-tag.py \
  --collection "Kids Movies" \
  --tag "Kids" \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

This makes the script usable for multiple curated groups.

For example:

```text
James Movies  → James
James TV      → James

Kids Movies   → Kids
Kids TV       → Kids
```

## Combining Options

All options can be combined.

For example:

```bash
python3 sync-collections-with-tag.py \
  --url "http://jellyfin.home.lan:8096" \
  --user-id "$JELLYFIN_USER_ID" \
  --collection "James Movies" \
  --tag "James" \
  --limit 5 \
  --dry-run
```

This will:

1. Connect to `http://jellyfin.home.lan:8096`
2. Use the specified Jellyfin user
3. Find the `James Movies` collection
4. Determine whether each item has the `James` tag
5. Process at most five items
6. Make no changes because `--dry-run` is enabled

## TV Series

TV collections require additional handling because Jellyfin parental-control tags may need to exist on child objects as well as the series itself.

If a collection contains:

```text
Bluey
```

the script expands it to:

```text
Bluey                     [James]
├── Season 1              [James]
│   ├── Episode 1         [James]
│   ├── Episode 2         [James]
│   └── ...
├── Season 2              [James]
│   ├── Episode 1         [James]
│   └── ...
└── Season 3              [James]
    └── ...
```

The script therefore handles:

```text
Series
  ↓
Seasons
  ↓
Episodes
```

automatically.

A collection containing dozens of TV shows can consequently result in hundreds or thousands of individual metadata objects being processed.

Always use `--dry-run` first.

## Jellyfin Parental Controls

After tagging the approved content, create or edit the restricted Jellyfin user.

Navigate to:

```text
Dashboard
  → Users
  → <user>
  → Parental Control
```

Configure the account to allow media carrying the desired tag.

For example:

```text
James
```

The overall workflow becomes:

```text
                 Jellyfin

             James Movies
                  │
                  │
                  ▼
       sync-collections-with-tag.py
                  │
                  │
             tag = James
                  │
                  ▼
        ┌───────────────────┐
        │ Jellyfin metadata │
        └─────────┬─────────┘
                  │
                  ▼
         Parental Controls
                  │
            allow "James"
                  │
                  ▼
             James user
```

This allows the collection to act as the convenient human-managed list while tags provide the access-control mechanism.

## Recommended Workflow

The intended workflow is:

1. Add approved media to a Jellyfin collection.
2. Run the script in dry-run mode.
3. Review the proposed changes.
4. Run the script normally.
5. Jellyfin tags the approved media.
6. The restricted user gains access through Jellyfin parental controls.

For example:

```bash
python3 sync-collections-with-tag.py \
  --collection "James Movies" \
  --user-id "$JELLYFIN_USER_ID" \
  --dry-run
```

Review the results, then:

```bash
python3 sync-collections-with-tag.py \
  --collection "James Movies" \
  --user-id "$JELLYFIN_USER_ID"
```

## Safety Behavior

The script is intentionally conservative.

### Add Only

The script currently **adds tags only**.

It does not remove a tag if an item disappears from the collection.

For example:

```text
Toy Story

James collection: NO
James tag:        YES
```

The script leaves the `James` tag intact.

This prevents an accidental collection edit from immediately revoking access to large amounts of media.

### Existing Tags Are Preserved

The script retrieves the complete Jellyfin metadata object before modifying its tags.

Only the configured tag is added.

Existing tags are not replaced.

### Processing Stops on Errors

If an item cannot be retrieved or updated, processing stops.

For example:

```text
========================================
 ERROR - PROCESSING STOPPED
========================================

Failed while updating:

  Type: Movie
  Name: Toy Story
  ID:   ...

Error:
  ...

No additional items will be processed.
```

This prevents an unexpected API problem from being repeated across hundreds of items.

### Dry Run

`--dry-run` performs no metadata writes.

Use it liberally.

## Repeated Runs

The script is designed to be safely rerun.

If an item already has the configured tag:

```text
[   1/35] already tagged  Movie      Anastasia
```

no update is performed.

This means a normal workflow can be:

```text
Add something to collection
        ↓
Run script
        ↓
Only newly approved items are changed
```

## Command-Line Reference

```text
--url URL
```

Override the Jellyfin server URL.

Example:

```bash
--url "http://jellyfin.home.lan:8096"
```

---

```text
--user-id USER_ID
```

Specify the Jellyfin user ID used for item retrieval.

Example:

```bash
--user-id "$JELLYFIN_USER_ID"
```

---

```text
--collection NAME
```

Specify the Jellyfin collection.

Example:

```bash
--collection "James Movies"
```

---

```text
--tag TAG
```

Specify the tag to apply.

Example:

```bash
--tag "James"
```

---

```text
--dry-run
```

Perform all discovery and validation without modifying Jellyfin.

Example:

```bash
python3 sync-collections-with-tag.py --dry-run
```

---

```text
--limit N
```

Process at most `N` items.

Example:

```bash
python3 sync-collections-with-tag.py --limit 1
```

This is especially useful when validating write behavior.

## Example Commands

Use script defaults:

```bash
python3 sync-collections-with-tag.py
```

Dry run:

```bash
python3 sync-collections-with-tag.py --dry-run
```

Process one item:

```bash
python3 sync-collections-with-tag.py --limit 1
```

Override the server:

```bash
python3 sync-collections-with-tag.py \
  --url "http://jellyfin.home.lan:8096"
```

Process a different collection:

```bash
python3 sync-collections-with-tag.py \
  --collection "James TV"
```

Use a different tag:

```bash
python3 sync-collections-with-tag.py \
  --collection "Kids Movies" \
  --tag "Kids"
```

Specify the user ID:

```bash
python3 sync-collections-with-tag.py \
  --user-id "$JELLYFIN_USER_ID"
```

Full test:

```bash
python3 sync-collections-with-tag.py \
  --url "http://jellyfin.home.lan:8096" \
  --user-id "$JELLYFIN_USER_ID" \
  --collection "James Movies" \
  --tag "James" \
  --limit 1 \
  --dry-run
```

## Troubleshooting

### HTTP 401 Unauthorized

Verify that `JELLYFIN_API_KEY` is set:

```bash
[ -n "$JELLYFIN_API_KEY" ] && echo "API key is set" || echo "API key is NOT set"
```

Test authentication:

```bash
curl -s \
  -H "Authorization: MediaBrowser Client=\"CollectionToTag\", Device=\"NUC\", DeviceId=\"jellyfin-collection-to-tag\", Version=\"1.0.0\", Token=\"$JELLYFIN_API_KEY\"" \
  'https://YOUR-JELLYFIN-SERVER/System/Info' \
  | python3 -m json.tool
```

A successful request should return Jellyfin server information.

### HTTP 400 When Retrieving an Item

Jellyfin 12 requires a valid user ID when retrieving an individual item with an API key.

Verify the user ID length:

```bash
echo -n "$JELLYFIN_USER_ID" | wc -c
```

It should return:

```text
32
```

Test an item directly:

```bash
curl -sS \
  -H "Authorization: MediaBrowser Client=\"CollectionToTag\", Device=\"NUC\", DeviceId=\"jellyfin-collection-to-tag\", Version=\"1.0.0\", Token=\"$JELLYFIN_API_KEY\"" \
  "https://YOUR-JELLYFIN-SERVER/Items/ITEM_ID?userId=$JELLYFIN_USER_ID" \
  | python3 -m json.tool
```

### Collection Is Found but Contains Zero Items

With Jellyfin 12.x, collection contents need to be queried recursively.

The script uses:

```text
/Items?ParentId=<COLLECTION_ID>&Recursive=true
```

You can test this manually:

```bash
curl -s \
  -H "Authorization: MediaBrowser Client=\"CollectionToTag\", Device=\"NUC\", DeviceId=\"jellyfin-collection-to-tag\", Version=\"1.0.0\", Token=\"$JELLYFIN_API_KEY\"" \
  'https://YOUR-JELLYFIN-SERVER/Items?ParentId=COLLECTION_ID&Recursive=true' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("Total:", d.get("TotalRecordCount")); [(print(i.get("Type"), "-", i.get("Name"))) for i in d.get("Items", [])]'
```

Example:

```text
Total: 35
Movie - Anastasia
Movie - A Charlie Brown Christmas
Movie - Inside Out
Movie - Moana
Movie - Toy Story
...
```

### Test Internal vs External Jellyfin URL

If Jellyfin is accessible directly on your LAN, you can bypass your reverse proxy:

```bash
python3 sync-collections-with-tag.py \
  --url "http://jellyfin.home.lan:8096" \
  --dry-run
```

This can help distinguish Jellyfin API problems from reverse-proxy problems.

## Security

Do not commit your Jellyfin API key to Git.

The script intentionally reads it from:

```text
JELLYFIN_API_KEY
```

If an API key is accidentally committed to a Git repository, revoke it in Jellyfin and generate a new key.

For interactive use:

```bash
export JELLYFIN_API_KEY='...'
```

For automated execution, consider using a protected environment file or secret-management mechanism instead of placing the API key directly in a shell script.

## Current Limitations

- Tags are added but not removed.
- One collection is processed per invocation.
- Jellyfin user context must currently be supplied manually.
- The script does not create collections.
- The script does not create Jellyfin users.
- The script does not configure parental controls.
- The script does not move or organize media files.
- Jellyfin API behavior may change between major Jellyfin releases.

## Future Improvements

Potential enhancements include:

- True synchronization mode that removes tags when media is removed from the collection
- Multiple collection-to-tag mappings in one execution
- Automatic Jellyfin user discovery
- Configuration file support
- Environment-variable support for additional settings
- systemd service/timer examples
- Docker image
- Logging
- `--remove` or `--sync` modes
- Verification after metadata writes
- More detailed TV-series reporting
- Automated scheduled synchronization

## Why Collections + Tags?

Jellyfin collections are convenient for humans to manage:

```text
Add to Collection
  → James Movies
```

Jellyfin parental controls, however, can use tags to determine what a restricted user is allowed to access.

This utility bridges those two mechanisms:

```text
Easy curation                  Access control

Collection                        Tag
    │                              ▲
    └──── collection-to-tag ───────┘
```

The result is a curated Jellyfin experience without:

- moving media
- duplicating files
- maintaining separate media directories
- manually tagging hundreds of episodes

For a TV series, adding one series to the collection can result in the appropriate tag being applied throughout the series hierarchy automatically.

## License

Choose an appropriate license for your repository, such as MIT, GPLv3, or another open-source license.
