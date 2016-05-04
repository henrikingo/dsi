# dsi
dsi - distributed system test infrastructure

This repo is the core for the DSI Evergreen integration. 

# folders
- **clusters**: define topologies    
  - **single**: a cluster with single mongod instance, used to test standalone and single member replica set
  - **shard**: a cluster with 3 shard, each with 3 member replica set
  - **longevity**: a cluster with 3 shard, each with 3 member replica set, used for longevity test
- **utls**: shell utils
- **bin**: supporting shell script

# MongoDB Setup Dependencies
pip install argparse mock paramiko

