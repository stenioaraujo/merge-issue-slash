"""API to use with slack slash commands

Use the GitLab API
https://git.lsd.ufcg.edu.br/help/api/README.md
https://git.lsd.ufcg.edu.br/help/api/groups.md#list-a-groups-projects
https://git.lsd.ufcg.edu.br/help/api/merge_requests.md#list-project-merge-requests
https://git.lsd.ufcg.edu.br/help/api/groups.md#search-for-group -- search=ztp will match ztp and ztp-interno
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import threading
import time
from collections import namedtuple
from datetime import datetime

from flask import request
from flask_api import FlaskAPI, status
import requests

app = FlaskAPI(__name__)

ALLOWED_CHANNELS_IDS = os.environ.get("ALLOWED_CHANNELS_IDS")
GITLAB_PERSONAL_TOKEN = os.environ.get('GITLAB_PERSONAL_TOKEN')
SECRET_ACCESS_KEY = os.environ.get('SECRET_ACCESS_KEY')
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

GROUPS_PATH = "https://git.lsd.ufcg.edu.br/api/v4/groups"
GROUP_PROJECTS = GROUPS_PATH + "/{}/projects"
PROJECTS_PATH = "https://git.lsd.ufcg.edu.br/api/v4/projects"
PROJECT_OPENED_ISSUES = PROJECTS_PATH + "/{}/issues?state=opened"
PROJECT_OPENED_MERGE_REQUESTS = (
    PROJECTS_PATH + "/{}/merge_requests?state=opened")

ACCEPT_MR_KEYWORDS = ["merges", "merge_requests", "mergerequests",
    "merge requests", "merge-requests"]
ACCEPT_ISSUES_KEYWORDS = ["issue", "issues"]

groups_name_to_id = {}

# This is a hack to share the request with sub threads
HackyRequest = namedtuple("HackyRequest",
                          ["data", "get_data", "headers", "args"])
hacky_shared_request = {}

class HackyThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.parent = threading.current_thread()
        threading.Thread.__init__(self, *args, **kwargs)


@app.route("/")
def index():
    return {"status":"ok"}


@app.route("/slash", methods=['POST'])
def slash():
    _save_hacky_request()
    hacky_request = _get_hacky_request()

    if not _validate_request():
        channel_id = hacky_request.data.get('channel_id')
        return ("Desculpa, _teoricamente_ esse comando só pode ser executado "
            "em canais específicos. Este canal (%s) não é um deles. "
            ":white_frowning_face:" % channel_id)

    command = hacky_request.data.get("command")
    command_text = hacky_request.data.get("text", '').lower()
    response_url = hacky_request.data.get("response_url")

    if command_text in ACCEPT_MR_KEYWORDS:
        t = HackyThread(
            target=_send_delayed_slackish_items,
            args=(open_merge_requests, "Merge Requests", response_url))
        t.start()
    elif command_text in ACCEPT_ISSUES_KEYWORDS:
        t = HackyThread(
            target=_send_delayed_slackish_items,
            args=(open_issues, "Issues", response_url))
        t.start()
    else:
        return slackish_help(command)

    response = {
        "response_type": "ephemeral",
        "text": "Recolhendo a informação, já já ela chega! :smile:"
    }

    return response


def _save_hacky_request():
    _free_hacky_request()
    current_thread_id = threading.current_thread().ident
    hacky_shared_request[current_thread_id] = HackyRequest(
        get_data=lambda: request.get_data(),
        data=request.data,
        args=request.args,
        headers=request.headers)


def _get_hacky_request():
    current_thread = threading.current_thread()
    if hasattr(current_thread, "parent"):
        return hacky_shared_request.get(current_thread.parent.ident)
    else:
        return request


def _free_hacky_request():
    alive_threads = []
    for thread in threading.enumerate():
        if thread and thread.is_alive():
            alive_threads.append(thread.ident)

    hacky_thread_ids_to_remove = []
    for hacky_thread_id in hacky_shared_request.keys():
        if hacky_thread_id not in alive_threads:
            hacky_thread_ids_to_remove.append(hacky_thread_id)

    for hacky_thread_id in hacky_thread_ids_to_remove:
        del hacky_shared_request[hacky_thread_id]


def _send_delayed_slackish_items(get_items_method, type_item, response_url):
    try:
        items_by_group = get_items_method()
        hacky_request = _get_hacky_request()
        msg_lines = [
            "<@%s>: %s %s" % (
                hacky_request.data.get("user_id"),
                hacky_request.data.get("command"),
                hacky_request.data.get("text")),
            "Open *%s*\n" % type_item
        ]
        for group, items in items_by_group.items():
            msg_lines.append("*%s*:" % group)
            if not items:
                msg_lines.append("    Esse grupo não tem nenhum item aberto!")
            for item in items:
                item_msg = (
                    "    :thumbsup: {item[upvotes]}  "
                    ":thumbsdown: {item[downvotes]}  {item[title]} "
                    "- {item[web_url]} "
                    "Criado à *{item[days_created]}* dia(s)")
                msg_lines.append(item_msg.format(item=item))

        response = json.dumps({
            "response_type": "in_channel",
            "text": '\n'.join(msg_lines)
        })
    except:
        response = json.dumps({
            "response_type": "ephemeral",
            "text": "Não consegui a informação. Sorry :slightly_frowning_face:"
        })

    headers = {"Content-Type": "application/json"}
    requests.post(response_url, data=response)


def slackish_help(command):
    msg = "*Merge Requests*:"
    for command_text in ACCEPT_MR_KEYWORDS:
        msg += "\n    %s %s" % (command, command_text)

    msg += "\n*Issues*:"
    for command_text in ACCEPT_ISSUES_KEYWORDS:
        msg += "\n    %s %s" % (command, command_text)

    response = {
        "response_type": "ephemeral",
        "text": msg
    }

    return response


def _validate_request():
    hacky_request = _get_hacky_request()
    body = hacky_request.get_data()
    timestamp = int(hacky_request.headers.get('X-Slack-Request-Timestamp', 0))
    slack_signature = hacky_request.headers.get('X-Slack-Signature', '')
    allowed_channel_ids = ALLOWED_CHANNELS_IDS.split(',')

    if abs(time.time() - timestamp) > 60 * 5:
        return False

    sig_basestring = b'v0:%b:%b' % (str(timestamp).encode(), body)
    digest = hmac.new(SLACK_SIGNING_SECRET.encode(), msg=sig_basestring,
        digestmod=hashlib.sha256).hexdigest()
    my_signature = 'v0=%s' % digest

    if not hmac.compare_digest(slack_signature, my_signature):
        return False

    channel_id = hacky_request.data.get('channel_id')
    if channel_id not in allowed_channel_ids:
        return False

    return True


def open_issues():
    try:
        hacky_request = _get_hacky_request()
        groups_names_param = hacky_request.args.get('groups_names')
        groups_ids = _get_groups_ids_for_names(groups_names_param.split(','))
    except:
        groups_ids = []

    issues = {}
    for group_id in groups_ids:
        projects_ids = (project['id'] for project in _get_projects([group_id]))
        issues[_groups_id_to_name(group_id)] = _get_opened_issues(projects_ids)
    return issues


def open_merge_requests():
    try:
        hacky_request = _get_hacky_request()
        groups_names_param = hacky_request.args.get('groups_names')
        groups_ids = _get_groups_ids_for_names(groups_names_param.split(','))
    except:
        groups_ids = []

    merge_requests = {}
    for group_id in groups_ids:
        projects_ids = (project['id'] for project in _get_projects([group_id]))
        merge_requests[_groups_id_to_name(group_id)] = (
            _get_opened_merge_requests(projects_ids))
    return merge_requests


def _groups_id_to_name(target_group_id):
    for group_name, group_id in groups_name_to_id.items():
        if group_id == target_group_id:
            return group_name


def _get_groups_ids_for_names(names):
    groups_ids = set()

    all_cached = True
    for name in names:
        group_id = groups_name_to_id.get(name)
        if group_id:
            groups_ids.add(str(group_id))
        else:
            all_cached = False
            break

    skip_groups = ""
    if groups_ids:
        skip_groups = "&skip_groups[]=" + '&skip_groups[]='.join(groups_ids)

    if not all_cached:
        for name in names:
            path =  GROUPS_PATH + "?search={}".format(name) + skip_groups
            groups = _get(path)
            for group in groups:
                group_name = group.get('name')
                group_id = str(group.get('id'))
                for name in names:
                    if group_name == name:
                        groups_name_to_id[name] = group_id
                        groups_ids.add(group_id)
                        break

    return groups_ids


def _get_projects(groups_ids):
    projects = []
    for group_id in groups_ids:
        projects_for_group = _get(GROUP_PROJECTS.format(group_id))
        projects += projects_for_group

    return projects


def _get_opened_merge_requests(projects_ids):
    return _get_open(projects_ids, PROJECT_OPENED_MERGE_REQUESTS)


def _get_opened_issues(projects_ids):
    return _get_open(projects_ids, PROJECT_OPENED_ISSUES)


def _get_open(projects_ids, path):
    things = []
    for project_id in projects_ids:
        things_for_project = _get(path.format(project_id))
        things += things_for_project

    for thing in things:
        date_template = "%Y-%m-%dT%H:%M:%S.%fZ"
        created_at_datetime = datetime.strptime(thing["created_at"], date_template)
        days_created = (datetime.utcnow() - created_at_datetime).days
        thing["days_created"] = days_created

    ordered_things = sorted(things, key=lambda t: t.get("days_created"), reverse=True)
    return ordered_things


def _get(url):
    hacky_request = _get_hacky_request()
    token = hacky_request.args.get("token")
    token = token or hacky_request.headers.get("Private-Token")

    # The thing bellow is really bad programming
    # At least it only allows a user to get information about the Merge
    # Requests and Issues
    gitlab_personal_token = None
    if token == SECRET_ACCESS_KEY:
        gitlab_personal_token = GITLAB_PERSONAL_TOKEN

    headers = {
        "Content-Type": "application/json",
        "Private-Token": gitlab_personal_token
    }
    return requests.get(url, headers=headers).json()


if __name__ == "__main__":
    envs = {
        "ALLOWED_CHANNELS_IDS": ALLOWED_CHANNELS_IDS,
        "GITLAB_PERSONAL_TOKEN": GITLAB_PERSONAL_TOKEN,
        "SECRET_ACCESS_KEY": SECRET_ACCESS_KEY,
        "SLACK_SIGNING_SECRET": SLACK_SIGNING_SECRET
    }
    if not all(envs.values()):
        msg = ("All the Environment Variables %s are needed, "
               "define them before starting the app." % envs.keys())
        raise Exception(msg)

    listen_ip, listen_port = "0.0.0.0", "8080"
    if len(sys.argv) > 1:
        if ':' in sys.argv[1]:
            listen_ip, listen_port = sys.argv[1].strip().split(':')
        else:
            listen_port = sys.argv[1]

    app.run(debug=True, use_reloader=True, host=listen_ip, port=listen_port)
