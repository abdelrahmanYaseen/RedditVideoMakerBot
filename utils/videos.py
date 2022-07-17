import json
import time
from typing import Dict

from praw.models import Submission

from utils import settings
from utils.console import print_step


def get_part_num(subreddit) -> int:
    with open("./video_creation/data/stories.json", "r", encoding="utf-8") as raw_vids:
        all_done_vids = json.load(raw_vids)
        subreddit_done_vids = all_done_vids[subreddit] if subreddit in all_done_vids.keys() else {}
        latest_part = subreddit_done_vids['latest_part'] if 'latest_part' in subreddit_done_vids.keys() else 0
        return latest_part


def isdone(post_id) -> bool:
    """
    checks if a post has been present in any previous video.
    """
    with open("./video_creation/data/stories.json", "r", encoding="utf-8") as done_stories_raw:
        done_stories = json.load(done_stories_raw)

    done_ids_groups = [[v['ids'].split('+') for v in a['items']]  for a in done_stories.values()]
    flat_list = [x for xs in done_ids_groups for x in xs]
    # flat_list = [x for xs in flat_list for x in xs]

    return any([post_id in done_ids_group for done_ids_group in flat_list])


def check_done(
    redditobj: Submission,
) -> Submission:
    # don't set this to be run anyplace that isn't subreddit.py bc of inspect stack
    """Checks if the chosen post has already been generated

    Args:
        redditobj (Submission): Reddit object gotten from reddit/subreddit.py

    Returns:
        Submission|None: Reddit object in args
    """
    with open("./video_creation/data/videos.json", "r", encoding="utf-8") as done_vids_raw:
        done_videos = json.load(done_vids_raw)
    done_ids = [a['id'] for a in done_videos]
    if str(redditobj) in done_ids:
        if settings.config["reddit"]["thread"]["post_id"]:
            print_step(
                "You already have done this video but since it was declared specifically in the config file the program will continue"
            )
            return redditobj
        print_step("Getting new post as the current one has already been done")
        return None
    # return redditobj


    # for video in done_videos:
    #     if video["id"] == str(redditobj):
    #         if settings.config["reddit"]["thread"]["post_id"]:
    #             print_step(
    #                 "You already have done this video but since it was declared specifically in the config file the program will continue"
    #             )
    #             return redditobj
    #         print_step("Getting new post as the current one has already been done")
    #         return None
    return redditobj


def save_data_v2(subreddit: str, filename: str, reddit_title: str, threads_ids: str, credit: str):
    """Saves the videos that have already been generated to a JSON file in video_creation/data/videos.json

    Args:
        filename (str): The finished video title name
        @param subreddit:
        @param filename:
        @param threads_ids:
        @param reddit_title:
    """
    with open("./video_creation/data/stories.json", "r+", encoding="utf-8") as raw_vids:
        all_done_vids = json.load(raw_vids)
        all_done_vids[subreddit] = all_done_vids[subreddit] if subreddit in all_done_vids.keys() else {}
        all_done_vids[subreddit]['latest_part'] = all_done_vids[subreddit]['latest_part'] + 1 if 'latest_part' in all_done_vids[subreddit].keys() else 1
        all_done_vids[subreddit]['items'] = [] if 'items' not in all_done_vids[subreddit].keys() else all_done_vids[subreddit]['items']
        all_done_vids[subreddit]['items'].append({
            "subreddit": subreddit,
            "ids": "+".join(threads_ids),
            "time": str(int(time.time())),
            "background_credit": credit,
            "reddit_title": reddit_title,
            "filename": filename,
            "part": all_done_vids[subreddit]['latest_part']
        })
        raw_vids.seek(0)
        json.dump(all_done_vids, raw_vids, ensure_ascii=False, indent=4)


def save_data(subreddit: str, filename: str, reddit_title: str, reddit_id: str, credit: str):
    """Saves the videos that have already been generated to a JSON file in video_creation/data/videos.json

    Args:
        filename (str): The finished video title name
        @param subreddit:
        @param filename:
        @param reddit_id:
        @param reddit_title:
    """
    with open("./video_creation/data/videos.json", "r+", encoding="utf-8") as raw_vids:
        done_vids = json.load(raw_vids)
        if reddit_id in [video["id"] for video in done_vids]:
            return  # video already done but was specified to continue anyway in the config file
        payload = {
            "subreddit": subreddit,
            "id": reddit_id,
            "time": str(int(time.time())),
            "background_credit": credit,
            "reddit_title": reddit_title,
            "filename": filename,
        }
        done_vids.append(payload)
        raw_vids.seek(0)
        json.dump(done_vids, raw_vids, ensure_ascii=False, indent=4)
