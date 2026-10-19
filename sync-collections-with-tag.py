#!/usr/bin/env python3

import argparse
import os
import sys

import requests


# ============================================================
# SCRIPT DEFAULTS
# ============================================================
#
# You can manually configure these values here.
#
# Any corresponding command-line argument overrides the value
# configured here.
#
# API_KEY is intentionally NOT configurable here. It must come
# from the JELLYFIN_API_KEY environment variable.
# ============================================================

DEFAULT_JELLYFIN_URL = "https://jellyfin.howeho.me"

DEFAULT_USER_ID = None
# Example:
# DEFAULT_USER_ID = "0123456789abcdef0123456789abcdef"

DEFAULT_COLLECTION = "James Movies"

DEFAULT_TAG = "James"

DEFAULT_CLIENT_NAME = "CollectionToTag"
DEFAULT_DEVICE_NAME = "NUC"
DEFAULT_DEVICE_ID = "jellyfin-collection-to-tag"
DEFAULT_CLIENT_VERSION = "1.0.0"


# ============================================================
# JELLYFIN API
# ============================================================

class Jellyfin:
    def __init__(
        self,
        url,
        api_key,
        user_id,
        client_name,
        device_name,
        device_id,
        client_version,
    ):
        self.url = url.rstrip("/")
        self.user_id = user_id

        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": (
                f'MediaBrowser '
                f'Client="{client_name}", '
                f'Device="{device_name}", '
                f'DeviceId="{device_id}", '
                f'Version="{client_version}", '
                f'Token="{api_key}"'
            ),
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def request(self, method, endpoint, **kwargs):
        url = f"{self.url}{endpoint}"

        try:
            response = self.session.request(
                method,
                url,
                timeout=30,
                **kwargs,
            )

        except requests.RequestException as exc:
            raise RuntimeError(
                f"Unable to communicate with Jellyfin: {exc}"
            ) from exc

        if not response.ok:
            raise RuntimeError(
                f"{method} {endpoint} returned "
                f"HTTP {response.status_code}: "
                f"{response.text}"
            )

        return response

    def test_connection(self):
        return self.request(
            "GET",
            "/System/Info",
        ).json()

    def get_items(self, **params):
        params.setdefault(
            "Limit",
            10000,
        )

        params.setdefault(
            "EnableTotalRecordCount",
            "true",
        )

        return self.request(
            "GET",
            "/Items",
            params=params,
        ).json().get("Items", [])

    def get_item(self, item_id):
        """
        Retrieve the full item metadata.

        Jellyfin 12 requires user context for this operation
        when using an API key.
        """

        return self.request(
            "GET",
            f"/Items/{item_id}",
            params={
                "userId": self.user_id,
            },
        ).json()

    def update_item(self, item):
        """
        Update an item's metadata.

        The complete item object is sent back to Jellyfin.
        """

        self.request(
            "POST",
            f"/Items/{item['Id']}",
            json=item,
        )


# ============================================================
# COLLECTION HANDLING
# ============================================================

def find_collection(jf, collection_name):
    print(
        f"Looking for collection: {collection_name}"
    )

    collections = jf.get_items(
        Recursive="true",
        IncludeItemTypes="BoxSet",
    )

    matches = [
        item
        for item in collections
        if item.get(
            "Name",
            "",
        ).casefold() == collection_name.casefold()
    ]

    if not matches:
        print(
            f'\nERROR: Collection "{collection_name}" '
            f"was not found.",
            file=sys.stderr,
        )

        if collections:
            print(
                "\nCollections returned by Jellyfin:",
                file=sys.stderr,
            )

            for collection in sorted(
                collections,
                key=lambda x: x.get("Name", ""),
            ):
                print(
                    f'  - {collection.get("Name", "Unnamed")}',
                    file=sys.stderr,
                )

        sys.exit(1)

    if len(matches) > 1:
        print(
            f'\nERROR: Multiple collections named '
            f'"{collection_name}" were found.',
            file=sys.stderr,
        )

        for item in matches:
            print(
                f'  {item.get("Name")} '
                f'({item.get("Id")})',
                file=sys.stderr,
            )

        sys.exit(1)

    collection = matches[0]

    print(
        f'Found collection: {collection["Name"]}'
    )

    print(
        f'Collection ID:    {collection["Id"]}'
    )

    return collection


def get_collection_members(jf, collection):
    """
    Retrieve collection members.

    This behavior was verified against Jellyfin 12.2.0.
    Recursive=true is required for the BoxSet query to return
    the collection contents.
    """

    return jf.get_items(
        ParentId=collection["Id"],
        Recursive="true",
    )


# ============================================================
# TV RECURSION
# ============================================================

def get_descendants(jf, item):
    """
    Expand television hierarchy.

    Movie:
        Movie only

    Series:
        Series
        Seasons
        Episodes

    Season:
        Season
        Episodes
    """

    item_type = item.get("Type")

    if item_type == "Series":
        return jf.get_items(
            ParentId=item["Id"],
            Recursive="true",
            IncludeItemTypes="Season,Episode",
        )

    if item_type == "Season":
        return jf.get_items(
            ParentId=item["Id"],
            Recursive="true",
            IncludeItemTypes="Episode",
        )

    return []


def build_desired_items(jf, collection):
    """
    Build the complete unique set of items that should
    receive the tag.

    Jellyfin IDs are used as dictionary keys to eliminate
    duplicate items automatically.
    """

    collection_items = get_collection_members(
        jf,
        collection,
    )

    print(
        f"\nCollection contains "
        f"{len(collection_items)} item(s)."
    )

    desired = {}

    for item in collection_items:
        desired[item["Id"]] = item

        children = get_descendants(
            jf,
            item,
        )

        for child in children:
            desired[child["Id"]] = child

    return desired


# ============================================================
# TAG HANDLING
# ============================================================

def has_tag(tags, tag):
    return any(
        existing.casefold() == tag.casefold()
        for existing in tags
    )


def prepare_tag_update(jf, item, tag):
    """
    Retrieve the complete metadata object and add the tag
    in memory if necessary.

    Returns:

        False, full_item
            Item already has the tag.

        True, full_item
            Tag was added to the in-memory object.
    """

    full_item = jf.get_item(
        item["Id"]
    )

    tags = full_item.get("Tags") or []

    if has_tag(
        tags,
        tag,
    ):
        return False, full_item

    tags = list(tags)

    tags.append(tag)

    full_item["Tags"] = tags

    return True, full_item


# ============================================================
# DISPLAY
# ============================================================

def describe_item(item):
    item_type = item.get(
        "Type",
        "Unknown",
    )

    name = item.get(
        "Name",
        "Unnamed",
    )

    if item_type == "Episode":
        season = item.get(
            "ParentIndexNumber"
        )

        episode = item.get(
            "IndexNumber"
        )

        if (
            season is not None
            and episode is not None
        ):
            return (
                f"{name} "
                f"(S{season:02d}E{episode:02d})"
            )

    return name


def print_item_summary(desired, tag):
    counts = {}

    for item in desired.values():
        item_type = item.get(
            "Type",
            "Unknown",
        )

        counts[item_type] = (
            counts.get(
                item_type,
                0,
            )
            + 1
        )

    print(
        f'\nItems that should have tag "{tag}":'
    )

    for item_type in sorted(counts):
        print(
            f"  {item_type:<12} "
            f"{counts[item_type]}"
        )

    print(
        f"\nTotal items: {len(desired)}"
    )


# ============================================================
# CONFIGURATION
# ============================================================

def validate_configuration(
    api_key,
    jellyfin_url,
    user_id,
    collection_name,
    tag,
    limit,
):
    if not api_key:
        print(
            "ERROR: JELLYFIN_API_KEY environment "
            "variable is not set.",
            file=sys.stderr,
        )

        print(
            "\nSet it with:",
            file=sys.stderr,
        )

        print(
            "  export JELLYFIN_API_KEY='your-api-key'",
            file=sys.stderr,
        )

        sys.exit(1)

    if not jellyfin_url:
        print(
            "ERROR: Jellyfin URL is not configured.",
            file=sys.stderr,
        )

        sys.exit(1)

    if not user_id:
        print(
            "ERROR: Jellyfin user ID is not configured.",
            file=sys.stderr,
        )

        print(
            "\nEither set DEFAULT_USER_ID in the script "
            "or use:",
            file=sys.stderr,
        )

        print(
            "  --user-id <JELLYFIN_USER_ID>",
            file=sys.stderr,
        )

        sys.exit(1)

    if len(user_id) != 32:
        print(
            "ERROR: Jellyfin user ID must be a "
            "32-character ID.",
            file=sys.stderr,
        )

        print(
            f"Length received: {len(user_id)}",
            file=sys.stderr,
        )

        sys.exit(1)

    if not collection_name:
        print(
            "ERROR: Collection name is empty.",
            file=sys.stderr,
        )

        sys.exit(1)

    if not tag:
        print(
            "ERROR: Tag is empty.",
            file=sys.stderr,
        )

        sys.exit(1)

    if limit is not None and limit < 1:
        print(
            "ERROR: --limit must be 1 or greater.",
            file=sys.stderr,
        )

        sys.exit(1)


# ============================================================
# MAIN SYNC
# ============================================================

def sync(
    jellyfin_url,
    api_key,
    user_id,
    collection_name,
    tag,
    client_name,
    device_name,
    device_id,
    client_version,
    dry_run=False,
    limit=None,
):
    validate_configuration(
        api_key,
        jellyfin_url,
        user_id,
        collection_name,
        tag,
        limit,
    )

    jf = Jellyfin(
        jellyfin_url,
        api_key,
        user_id,
        client_name,
        device_name,
        device_id,
        client_version,
    )

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    print(
        f"Connecting to Jellyfin at "
        f"{jellyfin_url} ..."
    )

    try:
        server = jf.test_connection()

    except Exception as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )

        sys.exit(1)

    print(
        f'Connected to: '
        f'{server.get("ServerName", "Unknown")}'
    )

    print(
        f'Jellyfin version: '
        f'{server.get("Version", "Unknown")}'
    )

    print()

    # --------------------------------------------------------
    # Collection
    # --------------------------------------------------------

    try:
        collection = find_collection(
            jf,
            collection_name,
        )

        desired = build_desired_items(
            jf,
            collection,
        )

    except Exception as exc:
        print(
            f"\nERROR while reading collection: "
            f"{exc}",
            file=sys.stderr,
        )

        sys.exit(1)

    if not desired:
        print(
            "\nThe collection contains no items. "
            "Nothing to do."
        )

        return

    print_item_summary(
        desired,
        tag,
    )

    # --------------------------------------------------------
    # Apply limit
    # --------------------------------------------------------

    items_to_process = list(
        desired.values()
    )

    total_available = len(
        items_to_process
    )

    if limit is not None:
        items_to_process = (
            items_to_process[:limit]
        )

        print(
            f"\nLIMIT ENABLED: processing only "
            f"{len(items_to_process)} of "
            f"{total_available} item(s)."
        )

    total = len(
        items_to_process
    )

    # --------------------------------------------------------
    # Dry run
    # --------------------------------------------------------

    if dry_run:
        print()
        print(
            "========================================"
        )
        print(
            " DRY RUN - NO CHANGES WILL BE MADE"
        )
        print(
            "========================================"
        )

    print()

    changed = 0
    unchanged = 0

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    for number, item in enumerate(
        items_to_process,
        start=1,
    ):
        item_type = item.get(
            "Type",
            "Unknown",
        )

        label = describe_item(
            item
        )

        # ----------------------------------------------------
        # Retrieve complete metadata
        # ----------------------------------------------------

        try:
            needs_tag, full_item = (
                prepare_tag_update(
                    jf,
                    item,
                    tag,
                )
            )

        except Exception as exc:
            print()
            print(
                "========================================"
            )
            print(
                " ERROR - PROCESSING STOPPED"
            )
            print(
                "========================================"
            )

            print(
                "\nFailed while retrieving:"
            )

            print(
                f"  Type: {item_type}"
            )

            print(
                f"  Name: {label}"
            )

            print(
                f"  ID:   {item.get('Id')}"
            )

            print(
                "\nError:"
            )

            print(
                f"  {exc}"
            )

            print(
                "\nNo additional items will be processed."
            )

            if dry_run:
                print(
                    "No changes were made by this run."
                )

            sys.exit(1)

        # ----------------------------------------------------
        # Already tagged
        # ----------------------------------------------------

        if not needs_tag:
            unchanged += 1

            print(
                f"[{number:4}/{total}] "
                f"{'already tagged':<15} "
                f"{item_type:<10} "
                f"{label}"
            )

            continue

        # ----------------------------------------------------
        # Dry run
        # ----------------------------------------------------

        if dry_run:
            changed += 1

            print(
                f"[{number:4}/{total}] "
                f"{'WOULD TAG':<15} "
                f"{item_type:<10} "
                f"{label}"
            )

            continue

        # ----------------------------------------------------
        # Write
        # ----------------------------------------------------

        try:
            jf.update_item(
                full_item
            )

        except Exception as exc:
            print()
            print(
                "========================================"
            )
            print(
                " ERROR - PROCESSING STOPPED"
            )
            print(
                "========================================"
            )

            print(
                "\nFailed while updating:"
            )

            print(
                f"  Type: {item_type}"
            )

            print(
                f"  Name: {label}"
            )

            print(
                f"  ID:   {item.get('Id')}"
            )

            print(
                "\nError:"
            )

            print(
                f"  {exc}"
            )

            print(
                "\nNo additional items will be processed."
            )

            print(
                f"\nSuccessfully tagged before failure: "
                f"{changed}"
            )

            sys.exit(1)

        changed += 1

        print(
            f"[{number:4}/{total}] "
            f"{'TAGGED':<15} "
            f"{item_type:<10} "
            f"{label}"
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print(
        "========================================"
    )
    print(
        " COMPLETE"
    )
    print(
        "========================================"
    )

    print(
        f"Items processed:      {total}"
    )

    if limit is not None:
        print(
            f"Items available:      {total_available}"
        )

    if dry_run:
        print(
            f"Would tag:            {changed}"
        )

    else:
        print(
            f"Tagged:               {changed}"
        )

    print(
        f"Already tagged:       {unchanged}"
    )

    if dry_run:
        print()
        print(
            "No changes were made."
        )


# ============================================================
# COMMAND-LINE ARGUMENTS
# ============================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Apply a Jellyfin tag recursively to media "
            "contained in a Jellyfin collection."
        )
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_JELLYFIN_URL,
        help=(
            "Jellyfin server URL. "
            f"Default: {DEFAULT_JELLYFIN_URL}"
        ),
    )

    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help=(
            "Jellyfin user ID used for item retrieval."
        ),
    )

    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=(
            "Jellyfin collection to process. "
            f'Default: "{DEFAULT_COLLECTION}"'
        ),
    )

    parser.add_argument(
        "--tag",
        default=DEFAULT_TAG,
        help=(
            "Tag to apply. "
            f'Default: "{DEFAULT_TAG}"'
        ),
    )

    parser.add_argument(
        "--client-name",
        default=DEFAULT_CLIENT_NAME,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--device-name",
        default=DEFAULT_DEVICE_NAME,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--device-id",
        default=DEFAULT_DEVICE_ID,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--client-version",
        default=DEFAULT_CLIENT_VERSION,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show what would happen without "
            "modifying Jellyfin."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Process at most N items. Useful for "
            "testing writes safely."
        ),
    )

    return parser.parse_args()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    args = parse_arguments()

    api_key = os.environ.get(
        "JELLYFIN_API_KEY"
    )

    sync(
        jellyfin_url=args.url,
        api_key=api_key,
        user_id=args.user_id,
        collection_name=args.collection,
        tag=args.tag,
        client_name=args.client_name,
        device_name=args.device_name,
        device_id=args.device_id,
        client_version=args.client_version,
        dry_run=args.dry_run,
        limit=args.limit,
    )
