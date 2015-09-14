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

# for debug
# set -x

# set debug flag, empty for no debug
readonly DEBUG=""
readonly numShard=$3

# parameters
readonly ChunkSize="--chunkSize=64"
readonly MY_ROOT="/home/ec2-user"
readonly SSHKEY="-i ${PEMFILE}"
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

# input
#    version
#    mongos_ssh_url
#    shard_count
#    config_count
startMongos() {
    # to start mongos
    local ver=$1; shift
    local ssh_url=$1; shift
    # local shard_count=$1; shift
    # local config_count=$1

    killAllProcess $ssh_url "mongos"

    # now start mongos
    
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/mongos.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"

    runSSHCommand $ssh_url "ulimit -n 3000 -c unlimited ; $MY_ROOT/$ver/bin/mongos --fork --configdb $IPconfig1:27017,$IPconfig2:27017,$IPconfig3:27017 --logpath=$MY_ROOT/data/logs/mongos.log $DEBUG $ChunkSize" 
}

startConfigServer() {
    # to start mongo config server
    local ver=$1; shift
    local ssh_url=$1; shift
    local storageEngine=$1; shift

    killAllProcess $ssh_url "mongod"

    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/mongos.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"

    if [ "$USE_CSRS" = true ]; then 
        echo "Using CSRS"
        runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod --port 27017 --replSet configSvrRS --dbpath $MY_ROOT/data/dbs --configsvr --fork --logpath $MY_ROOT/data/logs/mongod.log $DEBUG $storageEngine" 
    else 
        echo "Using Legacy ConfigSvr mode"
        runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod --port 27017 --dbpath $MY_ROOT/data/dbs --configsvr --fork --logpath $MY_ROOT/data/logs/mongod.log $DEBUG $storageEngine" 
    fi
}

startShard() {
    # to start mongos
    local ver=$1; shift
    local ssh_url=$1; shift
    local storageEngine=$1

    killAllProcess $ssh_url "mongod"
    sleep 1

    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/mongos.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"

	runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod $storageEngine --dbpath $MY_ROOT/data/dbs --fork --logpath $MY_ROOT/data/logs/mongod.log $DEBUG"
}

startReplicaMember() {
    # to start mongos
    local ver=$1; shift
    local ssh_url=$1; shift
    local rs=$1; shift
    local storageEngine=$1

    killAllProcess $ssh_url "mongod"
    sleep 1

    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/mongos.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "rm -rf /media/ephemeral1/journal"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"
    runSSHCommand $ssh_url "mkdir -p /media/ephemeral1/journal"
    runSSHCommand $ssh_url "cd $MY_ROOT/data/dbs; ln -s /media/ephemeral1/journal journal"

	runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod $storageEngine --dbpath $MY_ROOT/data/dbs --fork --logpath $MY_ROOT/data/logs/mongod.log --replSet $rs $DEBUG"
}

## config repolica
# 
configReplica() {
    local ver=$1; shift
    local shard=$1; shift
    local rs=rs$shard

    printDescription "configure replica set for shard: $shard"

    local S0=PUB_$shard\_0
    local H0=PRIVATE_$shard\_0
    local H1=PRIVATE_$shard\_1
    local H2=PRIVATE_$shard\_2

    printDescription "IPs: $S0 $H0 $H1 $H2"
    printDescription "IPs: ${!S0} ${!H0} ${!H1} ${!H2}"
    echo ""

    runSSHCommand ${!S0} "$MY_ROOT/$ver/bin/mongo --port 27017 --verbose \
		--eval \"rs.initiate();\
		sleep(2000);\
		cfg = rs.conf();\
		printjson(cfg);\
		cfg.members[0].priority = 1.0;\
		rs.reconfig(cfg);\
		while ( ! rs.isMaster().ismaster ) { sleep(1000); print(\\\"wait\\n\\\");} \
		rs.slaveOk();\
		t = rs.add(\\\"${!H1}:27017\\\");\
		t = rs.add(\\\"${!H2}:27017\\\");\
		printjson(t); \
		cfg = rs.conf();\
		printjson(cfg);\
		cfg.members[0].priority = 1.0;\
		cfg.members[1].priority = 0.5;\
		cfg.members[2].priority = 0.5;\
		rs.reconfig(cfg);\
		sleep(5000);\
		printjson(rs.status())\""
}
## config shard
# 
configShard() {
    local ver=$1; shift
    local ssh_url=$1;

    runSSHCommand $ssh_url "$MY_ROOT/$ver/bin/mongo --port 27017 \
    	--verbose \
    	--eval \"\
    	t = sh.addShard(\\\"$HOSTshard1:27017\\\");\
		printjson(t);\
    	t = sh.addShard(\\\"$HOSTshard2:27017\\\");\
		printjson(t);\
    	t = sh.addShard(\\\"$HOSTshard3:27017\\\");\
		printjson(t);\
    	sh.enableSharding(\\\"sbtest\\\");\
		for(i=0; i <= 16; i++) {\
		print(\\\"shard collection sbtest.sbtest\\\"+i); \
		$configShardKey\
	    }\
    	sh.status();\""

		# sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: \\\"hashed\\\" } );}\
		# sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: 1} );}\
}

## add a shard
# 
addShard() {
    local ver=$1; shift
    local _mongos=$1; shift
    local shard=$1;

    runSSHCommand $_mongos "$MY_ROOT/$ver/bin/mongo --port 27017 \
    	--verbose \
    	--eval \"\
            t = sh.addShard(\\\"$shard\\\");\
            printjson(t);\
    	\""
}

## config shard with replcia
# 
configShardWithReplica() {
    local ver=$1; shift
    local _mongos=$1; shift
    local _numShard=$1;

    echo ""

    # TODO: make adapt to size of the cluster
    ### addShard $ver $_mongos "rs0/$HOST_0_0:27017,$PRIVATE_0_1:27017,$PRIVATE_0_2:27017"
    ### addShard $ver $_mongos "rs1/$HOST_1_0:27017,$PRIVATE_1_1:27017,$PRIVATE_1_2:27017"
    ### addShard $ver $_mongos "rs2/$HOST_2_0:27017,$PRIVATE_2_1:27017,$PRIVATE_2_2:27017"
    ### addShard $ver $_mongos "rs3/$HOST_3_0:27017,$PRIVATE_3_1:27017,$PRIVATE_3_2:27017"
    ### echo "HOW to add RS3 ----> "
    ### echo "rs3/$HOST_3_0:27017,$PRIVATE_3_1:27017,$PRIVATE_3_2:27017"

    for i in `seq 1 $_numShard`;
    do
        let "ii=$i - 1"
        local Host=HOST_$ii\_0
        local IP1=PRIVATE_$ii\_1
        local IP2=PRIVATE_$ii\_2

        addShard $ver $_mongos "rs$ii/${!Host}:27017,${!IP1}:27017,${!IP2}:27017"
    done   

    runSSHCommand $_mongos "$MY_ROOT/$ver/bin/mongo --port 27017 \
    	--verbose \
    	--eval \"\
    	sh.enableSharding(\\\"ycsb\\\");\
        sh.shardCollection( \\\"ycsb.usertable\\\", { _id: \\\"hashed\\\" } );\
        $balanerState\
    	sh.status();\""
		# sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: \\\"hashed\\\" } );}\
		# sh.shardCollection( \\\"sbtest.sbtest\\\"+i, { _id: 1} );}\

    	## sh.enableSharding(\\\"sbtest\\\");\
		## for(i=0; i <= 16; i++) {\
		## print(\\\"shard collection sbtest.sbtest\\\"+i); \
		## $configShardKey}\
}

## start a new replica set
#
startReplicaSet() {
    local ver=$1; shift
    local shard=$1; shift
    local storageEngine=$1

    local H0=PUB_$shard\_0
    local H1=PUB_$shard\_1
    local H2=PUB_$shard\_2

    local rs=rs$shard
    printDescription "config replica set $rs for shard $shard"
    echo ""

	startReplicaMember $ver ${!H0} $rs $storageEngine
	startReplicaMember $ver ${!H1} $rs $storageEngine
	startReplicaMember $ver ${!H2} $rs $storageEngine

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


# killall mongod & mongos
killAllProcess $MONGOS "mongos"

## all shards
for i in "${ALL_HOST[@]}"
do
    killAllProcess ${!i} "mongod"
done

## all configs

sleep 2

startConfigServer $version $config1 ${_storageEngine}
startConfigServer $version $config2 ${_storageEngine}
startConfigServer $version $config3 ${_storageEngine}

if [ "$USE_CSRS" = true ]; then 
    echo "Config CSRS"
    HOST_CONFIG_RS_1=ip-`echo ${IPconfig1} | tr . -`
    runSSHCommand ${config1} "$MY_ROOT/$ver/bin/mongo --port 27017 --verbose \
		--eval \"rs.initiate({_id: \\\"configSvrRS\\\", configsvr:true, members:[{_id: 0, host:\\\"${HOST_CONFIG_RS_1}:27017\\\"}]});\
		sleep(2000);\
		cfg = rs.conf();\
		rs.reconfig(cfg);\
		while ( ! rs.isMaster().ismaster ) { sleep(1000); print(\\\"wait\\n\\\");} \
		rs.slaveOk();\
		t = rs.add(\\\"${IPconfig2}:27017\\\");\
		t = rs.add(\\\"${IPconfig3}:27017\\\");\
		printjson(t); \
		cfg = rs.conf();\
		printjson(cfg);\
		rs.reconfig(cfg);\
		sleep(5000);\
		printjson(rs.status())\""
	echo "CSRS configuration done!"
fi 

if [ "$4" == "noreplica" ]; then
    for i in `seq 1 $numShard`;
    do
        let "ii=$i - 1"
        startShard $version $ii $_storageEngine
    done   

	sleep 3
	startMongos $version $mongos

	sleep 3
	configShard $version $mongos $numShard

else
    for i in `seq 1 $numShard`;
    do
        let "ii=$i - 1"
        startReplicaSet $version $ii $_storageEngine
    done   

	sleep 3
	startMongos $version $mongos

	sleep 3
	configShardWithReplica $version $mongos $numShard
fi

# done
echo 
echo 
echo 

