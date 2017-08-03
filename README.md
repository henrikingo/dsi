# DSI: distributed system test infrastructure
Please consult the full documentation available at http://bit.ly/2ufjQ0R for more information about
installing required binaries and dependencies. To set up your environment for locally running 
performance tests, please see configurations/bootstrap/bootstrap.example.yml and follow the inline documentation.

## dependencies
```
pip install -r requirements-dev.txt
```

## testing
The repo's tests are all packaged into `/testscripts/runtests.sh`, which must be run from the repo
root and requires a `/config.yml` file (see `/example_config.yml`).

  - *Evergreen credentials*: found in your local `~/.evergreen.yml` file. 
(Instructions [here](http://evergreen.mongodb.com/settings) if you are missing this file.)
  - *Github authentication token*:
`curl -i -u <USERNAME> -H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>' -d '{"scopes": ["repo"], "note": 
"get full git hash"}' https://api.github.com/authorizations`
    - (You only need `-H 'X-GitHub-OTP: <2FA 6-DIGIT CODE>` if you have 2-factor authentication on.) 
