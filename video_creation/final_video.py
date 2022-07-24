#!/usr/bin/env python3
import multiprocessing
import os
import re
from os.path import exists
from typing import Tuple, Any
from moviepy.audio.AudioClip import concatenate_audioclips, CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip, TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from rich.console import Console

from utils.cleanup import cleanup
from utils.console import print_step, print_substep
from utils.videos import save_data, save_data_v2
from utils import settings
from utils.subreddit import shouldSkip

console = Console()
W, H = 1080, 1920


def name_normalize(name: str) -> str:
    name = re.sub(r'[?\\"%*:|<>]', "", name)
    name = re.sub(r"( [w,W]\s?\/\s?[o,O,0])", r" without", name)
    name = re.sub(r"( [w,W]\s?\/)", r" with", name)
    name = re.sub(r"(\d+)\s?\/\s?(\d+)", r"\1 of \2", name)
    name = re.sub(r"(\w+)\s?\/\s?(\w+)", r"\1 or \2", name)
    name = re.sub(r"\/", r"", name)

    lang = settings.config["reddit"]["thread"]["post_lang"]
    if lang:
        import translators as ts

        print_substep("Translating filename...")
        translated_name = ts.google(name, to_language=lang)
        return translated_name

    else:
        return name


def generate_intro_image(subreddit_name, part, left_margin=150):
    duration = 1
    bg_path = 'assets/backgrounds/subreddit-dark-backgound.png'
    fg_path = 'assets/temp/png/subreddit-icon.png'
    txt_path = 'assets/temp/png/introtext.png'
    bg = ImageClip(bg_path, duration=duration)
    fg = (ImageClip(fg_path)
          .set_duration(duration)
          .resize(height=bg.h * 0.5, width=bg.w / 2)  # if you need to resize...
          .margin(left=50, top=8, opacity=0)  # (optional) logo-border padding
          .set_pos((left_margin, "center")))

    TextClip(txt=f"{subreddit_name} - Part {part}", fontsize=40, color="white",
             font="Verdana").set_position(
        (left_margin + fg.w + 30, H / 2 - 20)).set_duration(duration).save_frame(txt_path)
    txt = ImageClip(txt_path, duration=1).set_position((left_margin + fg.w + 30, "center"))
    final = CompositeVideoClip([bg, fg, txt])
    final.save_frame('assets/temp/png/intro.png')


def make_final_video(
        number_of_clips: int,
        length: int,
        reddit_obj: dict,
        background_config: Tuple[str, str, str, Any],
):
    """Gathers audio clips, gathers all screenshots, stitches them together and saves the final video to assets/temp
    Args:
        number_of_clips (int): Index to end at when going through the screenshots'
        length (int): Length of the video
        reddit_obj (dict): The reddit object that contains the posts to read.
        background_config (Tuple[str, str, str, Any]): The background config to use.
    """
    # try:  # if it isn't found (i.e you just updated and copied over config.toml) it will throw an error
    #    VOLUME_MULTIPLIER = settings.config["settings"]['background']["background_audio_volume"]
    # except (TypeError, KeyError):
    #    print('No background audio volume found in config.toml. Using default value of 1.')
    #    VOLUME_MULTIPLIER = 1
    print_step("Creating the final video 🎥")
    subreddit = settings.config["reddit"]["thread"]["subreddit"]

    VideoFileClip.reW = lambda clip: clip.resize(width=W)
    VideoFileClip.reH = lambda clip: clip.resize(width=H)
    opacity = settings.config["settings"]["opacity"]
    background_clip = (
        VideoFileClip("assets/temp/background.mp4")
            .without_audio()
            .resize(height=H)
            .crop(x1=1166.6, y1=0, x2=2246.6, y2=1920)
    )

    # Gather all audio clips
    audio_clips = []
    audio_clips.append(AudioFileClip("assets/temp/mp3/subreddit.mp3"))
    audio_clips.append(AudioFileClip("assets/temp/mp3/title.mp3"))
    audio_clips += [AudioFileClip(f"assets/temp/mp3/{i}.mp3") for i in range(number_of_clips)]
    audio_concat = concatenate_audioclips(audio_clips)
    audio_composite = CompositeAudioClip([audio_concat])

    console.log(f"[bold green] Video Will Be: {length} Seconds Long")
    # add title to video
    image_clips = []
    # Gather all images
    new_opacity = 1 if opacity is None or float(opacity) >= 1 else float(opacity)
    image_clips.insert(
        0,
        ImageClip("assets/temp/png/subreddit.png")
            .set_duration(audio_clips[0].duration)
            .resize(width=W + 100)
            .set_opacity(new_opacity),
    )
    image_clips.insert(
        1,
        ImageClip("assets/temp/png/title.png")
            .set_duration(audio_clips[1].duration)
            .resize(width=W - 100)
            .set_opacity(new_opacity),
    )

    for i in range(0, number_of_clips):
        image_clips.append(
            ImageClip(f"assets/temp/png/comment_{i}.png")
                .set_duration(audio_clips[i + 1].duration)
                .resize(width=W - 100)
                .set_opacity(new_opacity)
        )

    # if os.path.exists("assets/mp3/posttext.mp3"):
    #    image_clips.insert(
    #        0,
    #        ImageClip("assets/png/title.png")
    #        .set_duration(audio_clips[0].duration + audio_clips[1].duration)
    #        .set_position("center")
    #        .resize(width=W - 100)
    #        .set_opacity(float(opacity)),
    #    )
    # else: story mode stuff
    img_clip_pos = background_config[3]
    image_concat = concatenate_videoclips(image_clips).set_position(img_clip_pos)
    image_concat.audio = audio_composite
    final = CompositeVideoClip([background_clip, image_concat])
    # final = CompositeVideoClip([image_concat])
    title = re.sub(r"[^\w\s-]", "", reddit_obj["thread_title"])
    idx = re.sub(r"[^\w\s-]", "", reddit_obj["thread_id"])

    filename = f"{name_normalize(title)}.mp4"

    if not exists(f"./results/{subreddit}"):
        print_substep("The results folder didn't exist so I made it")
        os.makedirs(f"./results/{subreddit}")

    # if settings.config["settings"]['background']["background_audio"] and exists(f"assets/backgrounds/background.mp3"):
    #    audioclip = mpe.AudioFileClip(f"assets/backgrounds/background.mp3").set_duration(final.duration)
    #    audioclip = audioclip.fx( volumex, 0.2)
    #    final_audio = mpe.CompositeAudioClip([final.audio, audioclip])
    #    # lowered_audio = audio_background.multiply_volume( # todo get this to work
    #    #    VOLUME_MULTIPLIER)  # lower volume by background_audio_volume, use with fx
    #    final.set_audio(final_audio)

    final.write_videofile(
        "assets/temp/temp.mp4",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        verbose=False,
        threads=multiprocessing.cpu_count(),
    )
    ffmpeg_extract_subclip(
        "assets/temp/temp.mp4",
        0,
        final.duration,
        targetname=f"results/{subreddit}/{filename}",
    )
    save_data(subreddit, filename, title, idx, background_config[2])
    # print_step("Removing temporary files 🗑")
    # cleanups = cleanup()
    # print_substep(f"Removed {cleanups} temporary files 🗑")
    print_substep("See result in the results folder!")

    print_step(
        f'Reddit title: {reddit_obj["thread_title"]} \n Background Credit: {background_config[2]}'
    )


def make_final_video_v2(
        number_of_clips: int,
        length: int,
        reddit_obj: dict,
        background_config: Tuple[str, str, str, Any],
):
    """Gathers audio clips, gathers all screenshots, stitches them together and saves the final video to assets/temp
    Args:
        number_of_clips (int): Index to end at when going through the screenshots'
        length (int): Length of the video
        reddit_obj (dict): The reddit object that contains the posts to read.
        background_config (Tuple[str, str, str, Any]): The background config to use.
    """
    # try:  # if it isn't found (i.e you just updated and copied over config.toml) it will throw an error
    #    VOLUME_MULTIPLIER = settings.config["settings"]['background']["background_audio_volume"]
    # except (TypeError, KeyError):
    #    print('No background audio volume found in config.toml. Using default value of 1.')
    #    VOLUME_MULTIPLIER = 1
    if not 'type' in reddit_obj.keys():
        make_final_video(
            number_of_clips,
            length,
            reddit_obj,
            background_config,
        )
        return

    print_step("Creating the final video 🎥")

    subreddit = settings.config["reddit"]["thread"]["subreddit"]
    generate_intro_image(subreddit, reddit_obj['part'])

    VideoFileClip.reW = lambda clip: clip.resize(width=W)
    VideoFileClip.reH = lambda clip: clip.resize(width=H)
    opacity = settings.config["settings"]["opacity"]
    background_clip = (
        VideoFileClip("assets/temp/background.mp4")
            .without_audio()
            .resize(height=H)
            .crop(x1=1166.6, y1=0, x2=2246.6, y2=1920)
    )

    # Gather all audio clips
    audio_clips = []
    audio_clips.append(AudioFileClip("assets/temp/mp3/subreddit.mp3"))
    audio_clips += [AudioFileClip(f"assets/temp/mp3/title_{i}.mp3") for i in range(number_of_clips) if
                    not shouldSkip(reddit_obj['items'][i])]
    audio_concat = concatenate_audioclips(audio_clips)
    audio_composite = CompositeAudioClip([audio_concat])

    console.log(f"[bold green] Video Will Be: {length} Seconds Long")
    # add title to video
    image_clips = []
    # Gather all images
    new_opacity = 1 if opacity is None or float(opacity) >= 1 else float(opacity)
    image_clips.insert(
        0,
        ImageClip("assets/temp/png/intro.png")
            .set_duration(audio_clips[0].duration)
            .resize(width=W + 100)
            .set_opacity(new_opacity),
    )

    j=-1
    for i in range(0, number_of_clips):
        if shouldSkip(reddit_obj['items'][i]):
            continue
        j += 1
        image_clips.append(
            ImageClip(f"assets/temp/png/title_{i}.png")
                .set_duration(audio_clips[j + 1].duration)
                .resize(width=W - 100)
                .set_opacity(new_opacity)
        )

    # if os.path.exists("assets/mp3/posttext.mp3"):
    #    image_clips.insert(
    #        0,
    #        ImageClip("assets/png/title.png")
    #        .set_duration(audio_clips[0].duration + audio_clips[1].duration)
    #        .set_position("center")
    #        .resize(width=W - 100)
    #        .set_opacity(float(opacity)),
    #    )
    # else: story mode stuff
    img_clip_pos = background_config[3]
    image_concat = concatenate_videoclips(image_clips).set_position(img_clip_pos)
    image_concat.audio = audio_composite
    final = CompositeVideoClip([background_clip, image_concat])
    # final = CompositeVideoClip([image_concat])
    # title = re.sub(r"[^\w\s-]", "", reddit_obj["thread_title"])
    # idx = re.sub(r"[^\w\s-]", "", reddit_obj["thread_id"])

    filename = f"{name_normalize(reddit_obj['subreddit'])}.mp4"
    subreddit = settings.config["reddit"]["thread"]["subreddit"]

    if not exists(f"./results/{subreddit}"):
        print_substep("The results folder didn't exist so I made it")
        os.makedirs(f"./results/{subreddit}")

    # if settings.config["settings"]['background']["background_audio"] and exists(f"assets/backgrounds/background.mp3"):
    #    audioclip = mpe.AudioFileClip(f"assets/backgrounds/background.mp3").set_duration(final.duration)
    #    audioclip = audioclip.fx( volumex, 0.2)
    #    final_audio = mpe.CompositeAudioClip([final.audio, audioclip])
    #    # lowered_audio = audio_background.multiply_volume( # todo get this to work
    #    #    VOLUME_MULTIPLIER)  # lower volume by background_audio_volume, use with fx
    #    final.set_audio(final_audio)

    final.write_videofile(
        "assets/temp/temp.mp4",
        fps=30,
        audio_codec="aac",
        audio_bitrate="192k",
        verbose=False,
        threads=multiprocessing.cpu_count(),
    )
    ffmpeg_extract_subclip(
        "assets/temp/temp.mp4",
        0,
        final.duration,
        targetname=f"results/{subreddit}/{filename}",
    )
    ids = [a['thread_id'] for a in reddit_obj['items'][:number_of_clips]]
    save_data_v2(subreddit, filename, filename, ids, background_config[2])
    # print_step("Removing temporary files 🗑")
    cleanups = cleanup()
    print_substep(f"Removed {cleanups} temporary files 🗑")
    print_substep("See result in the results folder!")

    # print_step(
    #     f'Reddit title: {reddit_obj["thread_title"]} \n Background Credit: {background_config[2]}'
    # )
