#!/bin/bash

source setting.sh

## make stderr red
exec 9>&2
exec 8> >(
    while IFS='' read -r line || [ -n "$line" ]; do
       echo -e "\033[31m${line}\033[0m"
    done
)
function undirect(){ exec 2>&9; }
STDERR_COLOR_EXCEPTIONS="echo:bash:set:wget:scp:gnuplot:let:for:export:readonly:[:[[:printDescription:+"
function redirect(){
        local IFS=":"; local cmd;
        local PRG="${BASH_COMMAND%% *}"
        PRG=$(basename "$PRG")
        for cmd in $STDERR_COLOR_EXCEPTIONS; do
            [[ "$cmd" == "$PRG" ]] && return 1;
        done
        echo ""
        echo  -e "------>  \033[4m\033[34m${PRG}\033[0m\033[24m"
        exec 2>&8
}

trap "redirect;" DEBUG
readonly PROMPT_COMMAND='undirect;'

function printDescription() {
    echo  -e "    \033[32m${*}\033[0m"
}

## end of make stderr red

# set -x

# set debug flag, empty for no debug
readonly DEBUG=""

# parameters
readonly MY_ROOT="/home/ec2-user"
readonly USER="ec2-user"
readonly SSHKEY="-i ${PEMFILE}"
