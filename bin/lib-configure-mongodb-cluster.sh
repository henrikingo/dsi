BINDIR=$(dirname $0)

# From $ALL_HOST[@] array, extrapolate public and private hostnames
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


#############################################################################
### Do remote commands over SSH
#############################################################################

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
    until [[ -z $(runSSHCommand $ssh_url "/sbin/pidof $name" ) ]]; do
        printDescription "Calling killall -9 $name on $ssh_url"
        runSSHCommand $ssh_url "killall -9 $name"
        sleep 1
    done
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

#############################################################################
### Start and configure replica set
#############################################################################

readonly ENABLE_TEST_CMDS="--setParameter enableTestCommands=1"

startReplicaMember() {
    local ver=$1; shift
    local ssh_url=$1; shift
    local storageEngine=$1; shift
    local rs=$1

    # The standalone variant is now launched here
    # It's the same as a 1-node replica set, just without the oplog
    # If $rs is empty, then we configure mongod without oplog
    if [ "$rs" ]
    then
        local replSetOpt="--replSet $rs"
    else
        local replSetOpt=""
    fi

    killAllProcess $ssh_url "mongod"
    sleep 1

    # Delete old files, setup new directories
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/mongos.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "rm -rf /media/ephemeral1/journal"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p /media/ephemeral1/journal"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"
    runSSHCommand $ssh_url "cd $MY_ROOT/data/dbs; ln -s /media/ephemeral1/journal journal"
    runSSHCommand $ssh_url "ls -la; cd $MY_ROOT/data/dbs; ls -la"

    # Launch mongod
    runSSHCommand $ssh_url "ulimit -n 3000 -c unlimited; $MY_ROOT/$ver/bin/mongod --storageEngine $storageEngine --dbpath $MY_ROOT/data/dbs --fork --logpath $MY_ROOT/data/logs/mongod.log $replSetOpt $DEBUG $ENABLE_TEST_CMDS"
}

startStandalone() {
    if [[ $# -gt 3 ]]
    then
        echo "Error: startStandalone only takes 3 arguments, $# given."
        exit -1
    fi
    startReplicaMember $@
}

## config replica
#
configReplica() {
    local ver=$1; shift
    local shard=$1; shift
    local nodes=$1 # Number of nodes

    printDescription "configure replica set for shard: $shard"

    local S0=PUB_$shard\_0
    local H0=PRIVATE_$shard\_0
    local H1=PRIVATE_$shard\_1
    local H2=PRIVATE_$shard\_2

    printDescription "IPs: $S0 $H0 $H1 $H2"
    printDescription "IPs: ${!S0} ${!H0} ${!H1} ${!H2}"
    echo ""

    local command="$MY_ROOT/$ver/bin/mongo --port 27017 --verbose \
		--eval \"rs.initiate();\
		sleep(2000);\
		cfg = rs.conf();\
		printjson(cfg);\
		cfg.members[0].priority = 1.0;\
		rs.reconfig(cfg);\
		while ( ! rs.isMaster().ismaster ) { sleep(1000); print(\\\"wait\\\n\\\");} \
		rs.slaveOk();"
    if [[ $nodes -gt 1 ]]; then
	command+="
                t = rs.add(\\\"${!H1}:27017\\\");printjson(t);";
    fi
    if [[ $nodes -gt 2 ]]; then
        command+="
                t = rs.add(\\\"${!H2}:27017\\\");printjson(t);";
    fi
    command+="
		cfg.members[0].priority = 1.0;\
		cfg = rs.conf();\
		printjson(cfg);";
    if [[ $nodes -gt 1 ]]; then
	command+="
		cfg.members[1].priority = 0.5;"
    fi
    if [[ $nodes -gt 2 ]]; then
        command+="
		cfg.members[2].priority = 0.5;";
    fi
    command+="
		rs.reconfig(cfg);\
		sleep(5000);\
		printjson(rs.status())\""


    printDescription $command
    runSSHCommand ${!S0} $command
}

## start a new replica set
#
startReplicaSet() {
    local ver=$1; shift
    local shard=$1; shift
    local storageEngine=$1; shift
    local nodes=$1;

    local H0=PUB_$shard\_0
    local H1=PUB_$shard\_1
    local H2=PUB_$shard\_2

    local rs=rs$shard
    printDescription "config replica set $rs for shard $shard"
    echo ""

    # For replica-2node, we must kill the whole replica set before initializing any new nodes
    killAllProcess ${!H0} "mongod"
    killAllProcess ${!H1} "mongod"
    killAllProcess ${!H2} "mongod"

    startReplicaMember $ver ${!H0} $storageEngine $rs
    startReplicaMember $ver ${!H1} $storageEngine $rs
    startReplicaMember $ver ${!H2} $storageEngine $rs

    # config
    configReplica $ver $shard $nodes
}


#############################################################################
### Sharded cluster configuration
#############################################################################

readonly mongos=$ms
readonly MONGOS=$ms
readonly PRIVATE_MONGOS=$ms_private_ip
readonly CSRS_REPL_NAME="configSvrRS"

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

    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/*.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"


    USE_CSRS=${USE_CSRS:-true}
    if [ "$USE_CSRS" = true ]; then
        echo "Using CSRS to start mongos"
        runSSHCommand $ssh_url "ulimit -n 3000 -c unlimited ; $MY_ROOT/$ver/bin/mongos --fork --configdb $CSRS_REPL_NAME/$IPconfig1:27017,$IPconfig2:27017,$IPconfig3:27017 --logpath=$MY_ROOT/data/logs/mongos.log $DEBUG $ChunkSize $ENABLE_TEST_CMDS"
    elif [ "$USE_CSRS" = false ]; then
        echo "Using Legacy ConfigSvr mode to start mongos"
        runSSHCommand $ssh_url "ulimit -n 3000 -c unlimited ; $MY_ROOT/$ver/bin/mongos --fork --configdb $IPconfig1:27017,$IPconfig2:27017,$IPconfig3:27017 --logpath=$MY_ROOT/data/logs/mongos.log $DEBUG $ChunkSize $ENABLE_TEST_CMDS"
    else
        echo "USE_CSRS must be either true or false, got $USE_CSRS"
        exit 1
    fi
}

startConfigServer() {
    # to start mongo config server
    local ver=$1; shift
    local ssh_url=$1; shift
    local storageEngine=$1; shift

    killAllProcess $ssh_url "mongod"

    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/logs/*.log"
    runSSHCommand $ssh_url "rm -rf $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/dbs"
    runSSHCommand $ssh_url "mkdir -p $MY_ROOT/data/logs"

    USE_CSRS=${USE_CSRS:-true}
    if [ "$USE_CSRS" = true ]; then
        echo "Using CSRS"
        runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod --port 27017 --replSet $CSRS_REPL_NAME --dbpath $MY_ROOT/data/dbs --configsvr --fork --logpath $MY_ROOT/data/logs/mongod.log $DEBUG --storageEngine=wiredTiger $ENABLE_TEST_CMDS"
    elif [ "$USE_CSRS" = false ]; then
        echo "Using Legacy ConfigSvr mode"
        runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod --port 27017 --dbpath $MY_ROOT/data/dbs --configsvr --fork --logpath $MY_ROOT/data/logs/mongod.log $DEBUG --storageEngine=$storageEngine $ENABLE_TEST_CMDS"
    else
        echo "USE_CSRS must be either true or false, got $USE_CSRS"
        exit 1
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

	runSSHCommand $ssh_url "ulimit -n 3000; $MY_ROOT/$ver/bin/mongod $storageEngine --dbpath $MY_ROOT/data/dbs --fork --logpath $MY_ROOT/data/logs/mongod.log $DEBUG $ENABLE_TEST_CMDS"
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

    # Connect to mongos and add the shards
    for i in `seq 1 $_numShard`;
    do
        let "ii=$i - 1"
        local Host=HOST_$ii\_0
        local IP1=PRIVATE_$ii\_1
        local IP2=PRIVATE_$ii\_2

        addShard $ver $_mongos "rs$ii/${!Host}:27017,${!IP1}:27017,${!IP2}:27017"
    done

    # Shard the ycsb collection, because ycsb doesn't know how to do it
    runSSHCommand $_mongos "$MY_ROOT/$ver/bin/mongo --port 27017 \
    	--verbose \
    	--eval \"\
    	sh.enableSharding(\\\"ycsb\\\");\
        sh.shardCollection( \\\"ycsb.usertable\\\", { _id: \\\"hashed\\\" } );\
        $balanerState\
    	sh.status();\""
}


configCSRS() {
    local ver=$1

    # Note: $config1,2,3 vars come directly from ips.sh settings file
    # You must kill all the server before re-config it, otherwise, it will fail 
    # due to inconsistent state of the replica set
    killAllProcess $config1 "mongod"
    killAllProcess $config2 "mongod"
    killAllProcess $config3 "mongod"

    startConfigServer $ver $config1 "wiredTiger"
    startConfigServer $ver $config2 "wiredTiger"
    startConfigServer $ver $config3 "wiredTiger"

    echo "Config CSRS replica set"
    HOST_CONFIG_RS_1=ip-`echo ${IPconfig1} | tr . -`
    runSSHCommand ${config1} "$MY_ROOT/$version/bin/mongo --port 27017 --verbose \
    --eval \"rs.initiate({_id: \\\"${CSRS_REPL_NAME}\\\", configsvr:true, members:[{_id: 0, host:\\\"${HOST_CONFIG_RS_1}:27017\\\"}]});\
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
}


startShardedCluster() {
    local version=$1; shift
    local shard=$1; shift
    local storageEngine=$1; shift
    local nodes=$1; shift
    local numShard=$1;

    # Create the config server replica set
    configCSRS $version

    # Create the shards as replica sets
    for i in `seq 1 $numShard`;
    do
        let "ii=$i - 1"
        startReplicaSet $version $ii $storageEngine 3
    done

    sleep 3
    # Start one mongos
    startMongos $version $mongos

    #
    sleep 3
    configShardWithReplica $version $mongos $numShard
}

#############################################################################
### Any other business
#############################################################################

## Remove old ssh keys from known_hosts, should there be any
for i in "${ALL_HOST[@]}"
do
    ssh-keygen -R ${!i}
done

# Really? Really??
sleep 2
