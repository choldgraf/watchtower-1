import os
import pandas as pd
from os.path import join
from datetime import datetime

from ._config import get_data_home, get_API_token, DATETIME_FORMAT
from . import _github_api
from .handlers_ import ProjectCommits


def load_commits(user, project=None, data_home=None,
                 use_handler=False, branch=None):
    """
    Reads the commits json files from the data folder.

    Parameters
    ----------
    user : string
        user or organization name, e.g. "matplotlib"
    project : string
        project name, e.g, "matplotlib". If None, user
        information will be loaded.
    data_home : string
        The path to the watchtower data. Defaults to ~/watchtower_data.
    use_handler : bool
        Whether to return data as one of the objects in
        `watchtower.handlers_`
    branch : string
        The branch fo the project to load.

    Returns
    -------
    commits : json | Handler object
        The commits for this user/project.
    """
    # XXX We need to sometime update that folder - how to do that?
    # XXX for some projects, that's going to get ugly…
    data_home = get_data_home(data_home)
    if project is None:
        filepath = join(data_home, 'users', user, "activity.json")
    elif branch is None:
        filepath = join(data_home, 'projects', user, project, "commits.json")
    else:
        filepath = join(data_home, 'projects', user, project,
                        'branches', branch, 'commits.json')
    try:
        commits = pd.read_json(filepath)
        commits['date'] = pd.to_datetime(commits['date'].values)\
            .tz_localize('UTC')\
            .tz_convert('US/Pacific')
        if len(commits) == 0:
            raise ValueError('No commits for this project')
    except ValueError as e:
        print(e)
        return None

    if use_handler is False:
        return commits
    else:
        return ProjectCommits(user, project, commits)


def update_commits(user, project=None, auth=None, since=None,
                   max_pages=100, per_page=100,
                   data_home=None, branch=None, **params):
    """Update the commit data for a repository.

    Parameters
    ----------
    user : string
        user or organization name, e.g. "matplotlib"
    project : string | None
        project name, e.g, "matplotlib". If None, user
        information will be loaded.
    auth : string (user:api_key)
        The username / API key for github, separated by a colon. If
        None, the key `GITHUB_API` will be searched for in `environ`.
    since : string
        Search for activity since this date
    max_pages : int
        The maximum number of pages to return in the GET request.
    per_page : int
        The number of commits to return per page.
    data_home : string
        The path to the watchtower data. Defaults to ~/watchtower_data.
    branch : string
        The branch fo the project to load.
    params : dict-like
        Will be passed to `get_frames`.

    Returns
    -------
    raw : json
        The raw json returned by the github API.
    """
    path = get_data_home(data_home=data_home)
    auth = get_API_token(auth) if auth is None else auth
    auth = _github_api.colon_seperated_pair(auth)
    api_root = 'https://api.github.com/'
    if project is None:
        url = api_root + 'users/{}/events'.format(user)
        filename = os.path.join(path, 'users', user, "activity.json")
    elif branch is None:
        url = api_root + 'repos/{}/{}/commits'.format(
            user, project)
        filename = os.path.join(path, 'projects', user,
                                project, "commits.json")
    else:
        url = api_root + 'repos/{}/{}/commits?sha={}'.format(
            user, project, branch)
        filename = os.path.join(path, 'projects', user, project,
                                'branches', branch, "commits.json")
    # Pull latest activity info
    raw = _github_api.get_frames(auth, url, since=since,
                                 max_pages=max_pages,
                                 per_page=per_page,
                                 **params)
    raw = pd.DataFrame(raw)

    if len(raw) == 0:
        print('No activity found')
        return None

    if project is None:
        raw = raw.rename(columns={'created_at': 'date'})
    else:
        dates = [ii['author']['date'] for ii in raw['commit'].values]
        raw['date'] = dates

    # Update pre-existing data
    old_raw = load_commits(user, project, branch=branch,
                           data_home=data_home)
    if old_raw is not None:
        raw = pd.concat([raw, old_raw], ignore_index=True)
        raw = raw.drop_duplicates(subset=['date'])
    try:
        os.makedirs(os.path.dirname(filename))
    except OSError:
        pass

    # Save + return
    raw.to_json(filename, date_format=DATETIME_FORMAT)
    return load_commits(user, project, data_home=data_home, branch=branch)


def find_word_in_string(string, queries=None):
    """Find one of a collection of query words in a string.

    Parameters
    ----------
    string : string
        The string in which we will search for words
    queries : string | list of strings | None
        The words to search for in string

    Returns
    -------
    in_strong : bool
        Whether or not one of the queries was found.
    """
    queries = 'doc' if queries is None else queries
    if isinstance(queries, str):
        queries = [queries]
    in_string = 0
    for word in queries:
        if word.lower() in string.lower():
            in_string += 1
    in_string = in_string > 0
    return in_string
