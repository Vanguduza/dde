#!/bin/sh
set -eu
git config core.hooksPath .githooks
echo 'Project Truth hooks enabled.'
