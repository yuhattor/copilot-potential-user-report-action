#!/bin/bash
if [ -z "PAT" ]
then
  echo "No PAT environment variable supplied"
  exit 1
fi
if [ -z "SLUGTYPE" ]
then
  echo "No SLUGTYPE environment variable supplied"
  exit 1
fi
if [ -z "SLUGNAME" ]
then
  echo "No SLUGNAME environment variable supplied"
  exit 1
fi

cd /app
python main.py

delimiter="$(openssl rand -hex 8)"
echo "summary<<${delimiter}" >> "${GITHUB_OUTPUT}"
echo "$(cat summary.md)" >> "${GITHUB_OUTPUT}"
echo "${delimiter}" >> "${GITHUB_OUTPUT}"