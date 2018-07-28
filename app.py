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
import os
import sys
import time

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


@app.route("/")
def index():
    return {"o":"k"}


@app.route("/slash", methods=['POST'])
def slash():
    if not _validate_request():
        return ("Desculpa, _teoricamente_ esse comando só pode ser executado "
            "em grupos específicos. :white_frowning_face:")

    print(request.data)

    command = request.data.get("command")
    command_text = request.data.get("text", '').lower()

    if command_text in ACCEPT_MR_KEYWORDS:
        return slackish_merge_requests()
    elif command_text in ACCEPT_ISSUES_KEYWORDS:
        return slackish_issues()
    else:
        return slackish_help(command)


def slackish_merge_requests():
    return "*Merge Requests*"


def slackish_issues():
    return "*Issues*"


def slackish_help(command):
    msg = "*Merge Requests*:"
    for command_text in ACCEPT_MR_KEYWORDS:
        print(command_text)
        msg += "\n    %s %s" % (command, command_text)

    msg += "\n*Issues*:"
    for command_text in ACCEPT_ISSUES_KEYWORDS:
        msg += "\n    %s %s" % (command, command_text)

    return msg


def _validate_request():
    body = request.get_data()
    timestamp = int(request.headers.get('X-Slack-Request-Timestamp', 0))
    slack_signature = request.headers.get('X-Slack-Signature', '')
    allowed_channel_ids = ALLOWED_CHANNELS_IDS.split(',')

    if abs(time.time() - timestamp) > 60 * 5:
        return False

    sig_basestring = b'v0:%b:%b' % (str(timestamp).encode(), body)
    digest = hmac.new(SLACK_SIGNING_SECRET.encode(), msg=sig_basestring,
        digestmod=hashlib.sha256).hexdigest()
    my_signature = 'v0=%s' % digest

    if not hmac.compare_digest(slack_signature, my_signature):
        return False

    channel_id = request.data.get('channel_id')
    if channel_id not in allowed_channel_ids:
        return False

    return True


@app.route("/issues")
def open_issues():
    try:
        groups_names_param = request.args.get('groups_names')
        groups_ids = _get_groups_ids_for_names(groups_names_param.split(','))
    except:
        groups_ids = []

    issues = {}
    for group_id in groups_ids:
        projects_ids = (project['id'] for project in _get_projects([group_id]))
        issues[_groups_id_to_name(group_id)] = _get_opened_issues(projects_ids)
    return issues


@app.route("/merge_requests")
def open_merge_requests():
    try:
        groups_names_param = request.args.get('groups_names')
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

    return things


def _get(url):
    token = request.args.get("token")
    token = token or request.headers.get("Private-Token")

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
