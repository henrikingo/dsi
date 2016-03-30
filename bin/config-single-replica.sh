#!/bin/bash 

BINDIR=$(dirname $0)
source ${BINDIR}/setting.sh


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
readonly mongos=$ms

# configShardKey="sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: 1} );"
readonly configShardKey="sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: \\\"hashed\\\" } );"
readonly balanerState="sh.stopBalancer();"
# readonly balanerState=""

               #sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: 1} );}\

# Public address
readonly MONGOS=$ms
readonly PRIVATE_MONGOS=$ms_private_ip

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
    # /usr/bin/ssh -i /Users/rui/bin/rui-aws-cap.pem $ssh_url $cmd
    /usr/bin/ssh -oStrictHostKeyChecking=no $SSHKEY $USER@$ssh_url $cmd
}

# input
#    ssh_url
configUlimit() {
    local ssh_url=$1; shift
	runSSHCommand $ssh_url "ulimit -f unlimited"
	runSSHCommand $ssh_url "ulimit -t unlimited"
	runSSHCommand $ssh_url "ulimit -v unlimited"
	runSSHCommand $ssh_url "ulimit -m unlimited"
	runSSHCommand $ssh_url "ulimit -n 64000"
	runSSHCommand $ssh_url "ulimit -u 64000"
	runSSHCommand $ssh_url "ulimit -a"
}


startReplicaMember() {
    # to start mongos
    local ver=$1; shift
    local ssh_url=$1; shift
    local rs=$1; shift
    local storageEngine=$1

    killAllProcess $ssh_url "mongod"
    sleep 1

    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/*.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "rm -rf /media/ephemeral1/journal"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p /media/ephemeral1/journal"
    runSSHCommand $ssh_url "cd $MY_ROOT/data/dbs; ln -s /media/ephemeral1/journal journal"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"

	runSSHCommand $ssh_url "ulimit -n 3000 -c unlimited; $MY_ROOT/$ver/bin/mongod $storageEngine --dbpath $MY_ROOT/data/dbs --fork --logpath $MY_ROOT/data/logs/mongod.log --replSet $rs $DEBUG"
}

## config repolica
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


## all shards
ssh-keygen -R $mc
killAllProcess $mc "mongod"
killAllProcess $mc "java"
for i in "${ALL_HOST[@]}"
do
    ssh-keygen -R ${!i}
    killAllProcess ${!i} "mongod"
done

sleep 2

startReplicaSet $version 0 $_storageEngine

