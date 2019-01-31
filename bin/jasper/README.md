### How to Update `jasper.proto` or the `curator` binary.

When updating to a newer version of `jasper.proto` or `curator`, the
following places need to be changed.
1. `jasper.proto` in DSI (this repository) should be replaced with the new protobuf file.
2. The `curator` binary that we download onto the DSI machines. As of 11/2018 the
   code to download `curator` lives in [`/terraform/remote-scripts/system-setup.sh`](https://github.com/10gen/dsi/blob/master/terraform/remote-scripts/system-setup.sh)
3. `jasper.proto` in the [Genny](https://github.com/mongodb/genny) repository should be replaced with
   the new proto file; the generated source files should be updated to correspond to the newer
   profo file as well. There are more instructions in the README file next to `jasper.proto` in
   the Genny repository on how to do this.

### Find current version of `curator` or `jasper.proto`
The curator Git hash is printed in all DSI task logs after curator is downloaded.
Searching for "curator version" in the task log will show the version.

There is no automated way to pin a `japser.proto` version to the curator version at the moment.
We rely on each upgrade following the steps described above. The only way right now to find the
accurate proto file version is by manually inspecting the git history of the file in the
[Jasper repository](https://github.com/mongodb/jasper/blob/master/jasper.proto)
(Link valid as of 11/2018)
