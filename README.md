# DSI: distributed system test infrastructure

This repo is the core for the DSI Evergreen integration.

## folders
- **clusters**: define topologies    
  - **single**: a cluster with single mongod instance, used to test standalone and single member replica set
  - **shard**: a cluster with 3 shard, each with 3 member replica set
  - **longevity**: a cluster with 3 shard, each with 3 member replica set, used for longevity test
- **utls**: shell utils
- **bin**: supporting shell script

## dependencies
```
pip install -r requirements.txt
```

## testing
The repo's tests are all packaged into `/testscripts/runtests.sh`, which must be run from the repo
root and requires a `/config.yml` file (see `/example_config.yml`).

  - *Evergreen credentials*: found in your local `~/.evergreen.yml` file. (Instructions [here](http://evergreen.mongodb.com/settings) if you are missing this file.)
  - *Github authentication token*:
`curl -i -u <USERNAME> -H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>' -d '{"scopes": ["repo"], "note": "get full git hash"}' https://api.github.com/authorizations`
    - (You only need `-H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>` if you have 2-factor authentication on.)
