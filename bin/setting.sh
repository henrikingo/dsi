BINDIR=$(dirname $0)

$(python ${BINDIR}/setting.py)
source ips.sh
export ALL=( "${ALL_HOST[@]}" )
