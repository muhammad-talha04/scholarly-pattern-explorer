#!/bin/bash
# Paste this into "Show advanced options > Management > Initialization script" when creating
# the Oracle VM. It runs once at first boot; progress is in /var/log/spe-setup.log.
curl -fsSL https://raw.githubusercontent.com/muhammad-talha04/scholarly-pattern-explorer/claude/fixes-and-oracle/deploy/oracle/setup.sh \
  | BRANCH=claude/fixes-and-oracle bash
