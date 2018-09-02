import os
import logging
import distutils.spawn
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.SmallResultItem import SmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.RunScriptAction import RunScriptAction

logging.basicConfig()
logger = logging.getLogger(__name__)

# Initialize items cache and Remmina profiles path
remmina_bin = ''
# Locate Remmina profiles and binary
remmina_profiles_path = "{}/.local/share/remmina".format(os.environ.get('HOME'))
remmina_bin = distutils.spawn.find_executable('remmina')
# This extension is useless without remmina
if remmina_bin is None or remmina_bin == '':
    logger.error('Remmina executable path could not be determined')
    exit()
# Check if Remmina profiles directory exists
if not os.path.isdir(remmina_profiles_path):
    logger.error("Remmina profiles directory doesn't exist ({})".format(remmina_profiles_path))
    exit()


class RemminaExtension(Extension):
    def __init__(self):

        super(RemminaExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

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
            print('Failed getting profile files')

        for p in profiles:
            base = os.path.basename(p)
            title = os.path.splitext(base)[0]
            desc, proto = profile_details(p)
            # Search for query inside filename and profile description
            # Multiple strings can be used to search in description
            # all() is used to achieve a AND search (include all keywords)
            keywords = query.split(" ")
            # if (query in base.lower()) or (query in desc.lower()):
            if (query in base.lower()) or all(x in desc for x in keywords):
                items_cache.append(create_item(title, proto, p, desc, p))

        return items_cache


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        # Get query
        term = (event.get_argument() or '').lower()
        # Display all items when query empty
        profiles_list = extension.list_profiles(term)

        return RenderResultListAction(profiles_list)


def create_item(name, icon, keyword, description, on_enter):
    return ExtensionResultItem(
            name=name,
            description=description,
            icon='images/{}.svg'.format(icon),
            on_enter=RunScriptAction('#!/usr/bin/env bash\n{} -c {}\n'.format(remmina_bin, on_enter), None)
    )


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
            desc = "{name} | {server} {group}".format(name=name,
                                                      server=server,
                                                      group=group)
            return desc, proto
    else:
        # Default values
        return "", "rdp"


if __name__ == '__main__':
    RemminaExtension().run()
