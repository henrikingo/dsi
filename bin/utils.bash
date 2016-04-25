#!/bin/bash 

BINDIR=$(dirname $0)
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

# parameters
readonly MY_ROOT="/home/ec2-user"
readonly SSHKEY="-i $PEMFILE"
readonly USER="ec2-user"
readonly mongos=$ms


# to kill a process with name
# input:
#    ssh_url
#    name
killAllProcess() {
    local ssh_url=$1; shift
    local name=$1;

    printDescription "kill all $name processes on $ssh_url"
    echo ""

    # kill if the process is running
    if [[ -n $(runSSHCommand $ssh_url "/sbin/pidof $name" ) ]]; then
        runSSHCommand $ssh_url "killall -9 $name"
    fi
}

# to run a remote command
# input:
#    ssh_url
#    $@ : command 
runSSHCommand() {
    local ssh_url=$1; shift
    local cmd=$@

    # ssh command here
    /usr/bin/ssh -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url $cmd
}

# to run a remote command
# input:
#    ssh_url
#    remote_file
#    local_file
scpFile() {
    local ssh_url=$1; shift
    local remote_file=$1; shift
    local local_file=$1 

    # ssh command here
    /usr/bin/scp -r -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url:$remote_file $local_file
}

