#!/usr/bin/env bash
# Create the network and the Always Free Ampere A1 VM from OCI Cloud Shell (OCI CLI is preconfigured):
#   curl -fsSL https://raw.githubusercontent.com/muhammad-talha04/scholarly-pattern-explorer/<branch>/deploy/oracle/launch.sh | bash
# Re-runnable: reuses spe-vcn / spe-subnet / spe-server when they exist.
set -euo pipefail
BRANCH=${BRANCH:-claude/fixes-and-oracle}
C=${OCI_TENANCY:?not in Cloud Shell?}
q() { "$@" --raw-output 2>/dev/null || true; }

[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -q -t ed25519 -N "" -f ~/.ssh/id_ed25519

VCN=$(q oci network vcn list -c "$C" --display-name spe-vcn --query 'data[0].id')
if [ -z "$VCN" ]; then
  VCN=$(oci network vcn create -c "$C" --cidr-blocks '["10.0.0.0/16"]' --display-name spe-vcn \
        --dns-label spevcn --wait-for-state AVAILABLE --query data.id --raw-output)
  IGW=$(oci network internet-gateway create -c "$C" --vcn-id "$VCN" --is-enabled true \
        --display-name spe-igw --wait-for-state AVAILABLE --query data.id --raw-output)
  RT=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-route-table-id"' --raw-output)
  oci network route-table update --rt-id "$RT" --force \
    --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"$IGW\"}]" >/dev/null
  SL=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-security-list-id"' --raw-output)
  rule() { echo "{\"source\":\"0.0.0.0/0\",\"protocol\":\"6\",\"tcpOptions\":{\"destinationPortRange\":{\"min\":$1,\"max\":$1}}}"; }
  oci network security-list update --security-list-id "$SL" --force \
    --ingress-security-rules "[$(rule 22),$(rule 80),$(rule 443)]" \
    --egress-security-rules '[{"destination":"0.0.0.0/0","protocol":"all"}]' >/dev/null
fi
echo "VCN ok"

SUB=$(q oci network subnet list -c "$C" --vcn-id "$VCN" --display-name spe-subnet --query 'data[0].id')
[ -n "$SUB" ] || SUB=$(oci network subnet create -c "$C" --vcn-id "$VCN" --cidr-block 10.0.0.0/24 \
  --display-name spe-subnet --dns-label spesub --wait-for-state AVAILABLE --query data.id --raw-output)
echo "subnet ok"

ID=$(q oci compute instance list -c "$C" --display-name spe-server --lifecycle-state RUNNING --query 'data[0].id')
if [ -z "$ID" ]; then
  IMG=$(oci compute image list -c "$C" --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
        --shape VM.Standard.A1.Flex --sort-by TIMECREATED --query 'data[0].id' --raw-output)
  curl -fsSL "https://raw.githubusercontent.com/muhammad-talha04/scholarly-pattern-explorer/$BRANCH/deploy/oracle/cloud-init.sh" > /tmp/spe-init.sh
  for AD in $(oci iam availability-domain list -c "$C" --query 'data[].name' --raw-output | tr -d '[]",'); do
    for try in 1 2 3; do
      echo "launching in $AD (try $try)"
      ID=$(oci compute instance launch -c "$C" --availability-domain "$AD" --shape VM.Standard.A1.Flex \
           --shape-config '{"ocpus":4,"memoryInGBs":24}' --image-id "$IMG" --subnet-id "$SUB" \
           --assign-public-ip true --display-name spe-server --boot-volume-size-in-gbs 150 \
           --ssh-authorized-keys-file ~/.ssh/id_ed25519.pub --user-data-file /tmp/spe-init.sh \
           --wait-for-state RUNNING --query data.id --raw-output 2>/tmp/spe-err.txt) && break 2
      grep -o '"message": "[^"]*"' /tmp/spe-err.txt | head -1; ID=""; sleep 30
    done
  done
fi
[ -n "$ID" ] || { echo "RESULT: FAILED (see /tmp/spe-err.txt)"; exit 1; }
IP=$(oci compute instance list-vnics --instance-id "$ID" --query 'data[0]."public-ip"' --raw-output)
echo "$IP" > ~/spe-ip
echo "RESULT: OK  ip=$IP  ssh ubuntu@$IP"
