export PEMFILE=../../keys/aws.pem
export SSHUSER_WIN=Administrator
export SSHUSER_LINUX=ec2-user
export SSHUSER=$SSHUSER_LINUX

source ips.sh

export ALL=( "${ALL_HOST[@]}" )
