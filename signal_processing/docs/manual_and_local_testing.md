
## Manual / Local Testing detect_changes or detect_outliers

__Note:__ The following steps use detect_changes as an example, but they also apply to detect_outliers.

__Note:__ The following steps test a main waterfall task. In order to test a patch task, download a
patch diagnostic archive or add an ```is_patch:true``` flag to runtime.yml.


1. Pip install locally from your dsi repo:

    $ cd <dsi repo location>
    $ pip install -e .

1. Get a dump of the Atlas cluster:

    $ mongodump --uri="mongodb+srv://signal_processing:${password:?not set}@performancedata-g6tsc.mongodb.net/perf" --archive=perf.gz --gzip

1. Restore to a local database:

    $ mongorestore --archive=perf.gz --gzip --drop 

1. Download the diagnostic archive from any task. For example [bestbuy_agg on Linux Standalone](https://evergreen.mongodb.com/task/sys_perf_linux_standalone_bestbuy_agg_bb9114dc71bfcf42422471f7789eca00881b8864_19_01_03_20_13_57) is [dsi-artifacts-bestbuy_agg-sys_perf_linux_standalone_bb9114dc71bfcf42422471f7789eca00881b8864_19_01_03_20_13_57-0.tgz](https://s3.amazonaws.com/mciuploads/dsi/linux-standalone/bb9114dc71bfcf42422471f7789eca00881b8864/sys_perf_linux_standalone_bestbuy_agg_bb9114dc71bfcf42422471f7789eca00881b8864_19_01_03_20_13_57/sys_perf_bb9114dc71bfcf42422471f7789eca00881b8864/logs/dsi-artifacts-bestbuy_agg-sys_perf_linux_standalone_bb9114dc71bfcf42422471f7789eca00881b8864_19_01_03_20_13_57-0.tgz)
1. Extract the archive to a local directory

    $ mkdir -pv ~/tmp/test_detect_changes && tar -zxvf dsi-artifacts-bestbuy_agg-sys_perf_linux_standalone_bb9114dc71bfcf42422471f7789eca00881b8864_19_01_03_20_13_57-0.tgz -C ~/tmp/test_detect_changes
    $ cd ~/tmp/test_detect_changes/

1. Edit analysis.yml and change mongo-uri to local database:

    $ sed -i.bak "s/^mongo_uri:.*$/mongo_uri: 'mongodb:\/\/localhost\/perf'/" analysis.yml

1. Run detect_changes from ~/tmp/test_detect_changes directory:

    $ cd ~/tmp/test_detect_changes && detect-changes
    
    
# ETL Scripts
 
There are two ETL scripts for transforming data, etl-jira-mongo and etl-evg-mongo. 
 
### Troubleshooting
 
#### MacOS
 
The etl-evg-mongo script may hit the following error on Macs:

```
objc[11135]: +[__NSPlaceholderDate initialize] may have been in progress in another thread when fork() was called.
objc[11134]: +[__NSPlaceholderDate initialize] may have been in progress in another thread when fork() was called.
```

This can be worked around by adding the `OBJC_DISABLE_INITALIZE_FORK_SAFETY=yes` to the environment the scripts is executing in.

```
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES etl-evg-mongo --mongo-uri mongodb://localhost/perf -d --project sys-perf
```
