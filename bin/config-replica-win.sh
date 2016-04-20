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

readonly SSHKEY="-i $PEMFILE"
readonly USER="ec2-user"
readonly mongos="$ms"

readonly DB_PATH_WIN="/cygdrive/y"
readonly DB_PATH_LINUX="/media/ephemeral0"
readonly JOURNAL_PATH_WIN="/cygdrive/z"
readonly JOURNAL_PATH_LINUX="/media/ephemeral1"

readonly WINDOWS_PLATFORM_STRING="WINDOWS"

# default to Linux
JOURNAL_PATH=$JOURNAL_PATH_LINUX
DB_PATH=$DB_PATH_LINUX

echo  -e "------>  \033[4m\033[34msetup global variables\033[0m\033[24m"
export N=0
export I=1
for i in "${ALL_HOST[@]}"
do
    let "SHARD=$N / 3"
    let "MEMBER=$N % 3"
    export private_ip=i$I
    # echo "    DEBUG -> private_ip: $private_ip"
    export PUB_${SHARD}_$MEMBER=${!i}
    export PRIVATE_${SHARD}_$MEMBER=${!private_ip}
    printDescription "define PUB_${SHARD}_${MEMBER}=${!i}   & PRIVATE_${SHARD}_$MEMBER=${!private_ip}"
    export HOST_$SHARD\_$MEMBER=ip-`echo ${!private_ip} | tr . -`
    let "N=$N + 1"
    let "I=$N + 1"
done
echo ""

# >>>>

# to kill a process with name
# input:
#    ssh_url
#    name
#
#    this is Linux only function.
killAllProcess() {
    local ssh_url=$1; shift
    local name=$1;

    printDescription "kill all $name processes on $ssh_url"
    echo ""

    # kill if the process is running
    if [[ -n $(runSSHCommand "$ssh_url" "/sbin/pidof $name" ) ]]; then
        T=$USER
        USER=$USER_LINUX

        runSSHCommand "$ssh_url" "killall -9 $name"

        USER=$T
    fi
}

# to run a remote command
# input:
#    ssh_url
#    $@ : command
runSSHCommand() {
    local ssh_url=$1; shift
    local cmd=$*

    # ssh command here
    # /usr/bin/ssh -i /Users/rui/bin/rui-aws-cap.pem "$ssh_url" $cmd
    /usr/bin/ssh -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url $cmd
}

# to stop a Windows service
# input:
#   ssh_url
#   service_name
#
#   for Windows only
stopWindowsService() {
    local ssh_url=$1; shift
    local service_name=$1; shift

    /usr/bin/ssh -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url "sc stop $service_name"
    /usr/bin/ssh -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url "sc delete $service_name"
}

stopWindowsFirewall() {
    local ssh_url=$1; shift

    /usr/bin/ssh -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url "NetSh Advfirewall set allprofiles state off"
}

startReplicaMember() {
    # to start mongos
    local ver=$1; shift
    local ssh_url=$1; shift
    local rs=$1; shift
    local storageEngine=$1

    if [ $PLATFORM = $WINDOWS_PLATFORM_STRING ]; then
        stopWindowsFirewall $ssh_url
        stopWindowsService "$ssh_url" "MongoDB"
    else
        killAllProcess "$ssh_url" "mongod"
    fi
    sleep 1

    runSSHCommand "$ssh_url" "rm -rf $MY_ROOT/data/logs/*.log"
    runSSHCommand "$ssh_url" "rm -rf $MY_ROOT/data/dbs/*"
    runSSHCommand "$ssh_url" "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand "$ssh_url" "rm -rf $JOURNAL_PATH/journal"
    runSSHCommand "$ssh_url" "mkdir -p $DB_PATH/dbs"
    runSSHCommand "$ssh_url" "mkdir -p $JOURNAL_PATH/journal"
    runSSHCommand "$ssh_url" "mkdir -p $MY_ROOT/data"
    runSSHCommand "$ssh_url" "cd $MY_ROOT/data; CYGWIN=winsymlinks:native ln -s $DB_PATH/dbs dbs"
    runSSHCommand "$ssh_url" "cd $MY_ROOT/data/dbs; CYGWIN=winsymlinks:native ln -s $JOURNAL_PATH/journal journal"
    runSSHCommand "$ssh_url" "mkdir -p $JOURNAL_PATH/logs"

    if [ "$PLATFORM" = "$WINDOWS_PLATFORM_STRING" ]; then
        # install windows service
        runSSHCommand "$ssh_url" 'sc.exe create MongoDB binPath= "C:\\Cygwin64\\home\\ec2-user\\mongodb\\bin\\mongod.exe --dbpath="Y:\\dbs" --logpath="Z:\\logs\\mongod.log" --replSet='"$rs $storageEngine"' --service " DisplayName= "MongoDB" start= "auto" '
        runSSHCommand "$ssh_url" "sc.exe start MongoDB"
    else
        runSSHCommand "$ssh_url" "ulimit -n 3000 -c unlimited; $MY_ROOT/$ver/bin/mongod $storageEngine --dbpath $MY_ROOT/data/dbs --fork --logpath $MY_ROOT/data/logs/mongod.log --replSet $rs $DEBUG"
    fi
}

## config replica
# 
configReplica() {
    local ver=$1; shift
    local shard=$1; shift
    local rs=rs$shard

    local S0=PUB_$shard\_0
    local H0=PRIVATE_$shard\_0

    runSSHCommand ${!S0} "$MY_ROOT/$ver/bin/mongo --port 27017 --verbose \
		--eval \"rs.initiate();\
		sleep(2000);\
		cfg = rs.conf();\
		printjson(cfg);\
		cfg.members[0].priority = 1.0;\
		rs.reconfig(cfg);\
		while ( ! rs.isMaster().ismaster ) { sleep(1000); print(\\\"wait\\n\\\");} \
		cfg = rs.conf();\
		printjson(cfg);\
		cfg.members[0].priority = 1.0;\
		rs.reconfig(cfg);\
		sleep(5000);\
		printjson(rs.status())\""
}

## start a new replica set
#
startReplicaSet() {
    local ver=$1; shift
    local shard=$1; shift
    local storageEngine=$1

    local H0=PUB_$shard\_0

    local rs=rs$shard
    printDescription "config replica set $rs for shard $shard"
    echo ""

	startReplicaMember $ver ${!H0} $rs $storageEngine

	# config
	configReplica $ver $shard
}

if [[ $# -lt 2 ]]; then
	echo "Must provide version and storageEngine"
	exit 1
fi

readonly version=$1

if [ "$2" != "mmapv0" ]; then
	export _storageEngine="--storageEngine=$2"
	printDescription "set storageEngine to $2"
else
	export _storageEngine=""
fi


# reset workload client instance
ssh-keygen -R "$mc"
killAllProcess "$mc" "mongod"
killAllProcess "$mc" "mongo"
killAllProcess "$mc" "java"

# FIXME: this will be removed when we merge Windows and Linux scripts together, hardcoded for now.
PLATFORM=$WINDOWS_PLATFORM_STRING

# if Windows, we reset some parameter
if [ $PLATFORM = $WINDOWS_PLATFORM_STRING ]; then
    JOURNAL_PATH=$JOURNAL_PATH_WIN
    DB_PATH=$DB_PATH_WIN
fi

for i in "${ALL_HOST[@]}"
do
    echo "Regenerate key for $i:${!i}"
    ssh-keygen -R "${!i}"
    if [ $PLATFORM = $WINDOWS_PLATFORM_STRING ]; then
        stopWindowsService "${!i}" "MongoDB"
        sleep 1
    else
        killAllProcess "${!i}" "mongod"
        sleep 1
    fi
done

sleep 2

startReplicaSet "$version" 0 $_storageEngine
