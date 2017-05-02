RAW_ANSWER=`dig +short -t SRV _kerberos._tcp.intgdc.com | sort -n | head -n 1`
echo $RAW_ANSWER | sed -e 's/.* \(\w\+[0-9]\+.\(prod\|int\|dev\)gdc.com\)\./\1/'
