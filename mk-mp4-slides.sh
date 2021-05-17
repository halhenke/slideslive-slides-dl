#! /usr/bin/env zsh

ffmpeg -f concat -i ffmpeg_concat.txt -vsync vfr -pix_fmt yuv420p slides-video.mp4
