import os
import json
import logging
import distutils.spawn
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.SmallResultItem import SmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction

logging.basicConfig()
logger = logging.getLogger(__name__)

global usage_cache
usage_cache = {}

# Usage tracking
script_directory = os.path.dirname(os.path.realpath(__file__))
usage_db = os.path.join(script_directory, "usage.json")
if os.path.exists(usage_db):
    with open(usage_db, 'r') as db:
        # Read JSON string
        raw = db.read()
        # JSON to dict
        usage_cache = json.loads(raw)

# Initialize items cache and Remmina profiles path
remmina_bin = ""
# Locate Remmina profiles and binary
default_paths = ["{}/.local/share/remmina".format(os.environ.get('HOME')),
                 "{}/.remmina".format(os.environ.get('HOME'))]
# remmina_profiles_path = "{}/.local/share/remmina".format(os.environ.get('HOME'))
# remmina_profiles_path_alt = "{}/.remmina".format(os.environ.get('HOME'))
remmina_bin = distutils.spawn.find_executable('remmina')
# This extension is useless without remmina
if remmina_bin is None or remmina_bin == "":
    logger.error("Remmina executable path could not be determined")
    exit()
# Check if Remmina profiles directory exists
remmina_profiles_path = None
# Check default paths first
for p in default_paths:
    if os.path.isdir(p):
        remmina_profiles_path = p


class RemminaExtension(Extension):
    def __init__(self):

        super(RemminaExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())

    def list_profiles(self, query):
        profiles = []
        items_cache = []
        try:
            # Get list of profile files from Remmina directory
            for profile in os.listdir(remmina_profiles_path):
                if profile.endswith(".remmina"):
                    profiles.append(os.path.join(remmina_profiles_path, profile))
            # Get sorted list of profiles
            temp = profiles
            profiles = sorted(temp)
        except Exception as e:
            logger.error("Failed getting Remmina profile files")
        for p in profiles:
            base = os.path.basename(p)
            title, desc, proto = profile_details(p)
            # Search for query inside filename and profile description
            # Multiple strings can be used to search in description
            # all() is used to achieve a AND search (include all keywords)
            keywords = query.split(" ")
            # if (query in base.lower()) or (query in desc.lower()):
            if (query.lower() in base.lower()) or \
               (query.lower() in title.lower()) or \
               all(x.lower() in desc.lower() for x in keywords):
                items_cache.append(create_item(title, proto, p, desc, p))

        items_cache = sorted(items_cache, key=sort_by_usage, reverse=True)
        return items_cache


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        global remmina_profiles_path
        if extension.preferences["profiles"] is not "" \
           or not remmina_profiles_path:
            # Tilde (~) won't work alone, need expanduser()
            remmina_profiles_path = os.path.expanduser(extension.preferences["profiles"])
        # pref_profiles_path = extension.preferences['profiles']
        logger.debug("Remmina profiles path: {}".format(remmina_profiles_path))
        # Get query
        term = (event.get_argument() or "").lower()
        # Display all items when query empty
        profiles_list = extension.list_profiles(term)
        return RenderResultListAction(profiles_list[:8])


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        global usage_cache
        # Get query
        data = event.get_data()
        on_enter = data["id"]
        # The profile file name is the ID
        base = os.path.basename(on_enter)
        b = os.path.splitext(base)[0]
        # Check usage and increment
        if b in usage_cache:
            usage_cache[b] = usage_cache[b]+1
        else:
            usage_cache[b] = 1
        # Update usage JSON
        with open(usage_db, 'w') as db:
            db.write(json.dumps(usage_cache, indent=2))
        return RunScriptAction('#!/usr/bin/env bash\n{} -c {}\n'.format(remmina_bin, on_enter), None).run()


def create_item(name, icon, keyword, description, on_enter):
    return ExtensionResultItem(
            name=name,
            description=description,
            keyword=keyword,
            icon="images/{}.svg".format(icon),
            on_enter=ExtensionCustomAction(
                 {"id": on_enter})
            )


def sort_by_usage(i):
    global usage_cache
    # Convert item name to ID format
    # j = i._name.lower()
    base = os.path.basename(i._keyword.lower())
    j = os.path.splitext(base)[0]
    # Return score according to usage
    if j in usage_cache:
        return usage_cache[j]
    # Default is 0 (no usage rank / unused)
    return 0


def profile_details(profile_path):
    if os.path.isfile(profile_path):
        with open(profile_path, "r") as f:
            # Read profile file lines
            lines = f.read().split("\n")
            # Initialize strings
            desc = name = username = group = proto = ""
            # Parse lines for relevant details
            for line in lines:
                # Profile name
                if line.startswith("name="):
                    elem = line.split("name=")
                    if len(elem[1]) > 0:
                        name = elem[1]
                # Profile username (optional)
                if "username=" in line:
                    elem = line.split("username=")
                    # if len(elem) > 1:
                    if len(elem[0]) == 0 and len(elem[1]) > 0:
                        username = elem[1]
                    elif len(elem[0]) > 0 and len(elem[1]) > 0:
                        username = elem[1]
                # Profile server and port
                if line.startswith("server="):
                    elem = line.split("server=")
                    if len(elem[1]) > 0:
                        server = elem[1]
                # Profile group name
                if line.startswith("group="):
                    elem = line.split("group=")
                    if len(elem[1]) > 0:
                        group = elem[1]
                # Profile protocol (for different icons)
                if line.startswith("protocol="):
                    elem = line.split("protocol=")
                    if len(elem[1]) > 0:
                        proto = elem[1].strip().lower()
                else:
                    pass
            if len(username) > 0:
                server = "{username}@{server}".format(username=username,
                                                      server=server)
            if len(proto) > 0:
                server = "{proto}://{server}".format(proto=proto,
                                                     server=server)
            if len(group) > 0:
                group = " | {group}".format(group=group)
            # Final description string
            desc = "{server} {group}".format(server=server,
                                             group=group)
            return name, desc, proto
    else:
        # Default values
        return "", "", "rdp"


if __name__ == "__main__":
    RemminaExtension().run()
