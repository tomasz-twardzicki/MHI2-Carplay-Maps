# SPDX-License-Identifier: GPL-3.0-or-later
# Data-only mutable preference, constrained to the upstream 1010x376 profile.
cfg_ok(){
 regular "$1" && awk -F= '
 BEGIN{split("width height fps maxfps safex safey safew safeh nsafex nsafey nsafew nsafeh alturl",keys," ")}
 {if(NF!=2||$1!=keys[NR]||NR>13)bad=1;v[$1]=$2;
  if(NR<13&&($2!~/^[0-9]+$/||sprintf("%d",$2+0)!=$2))bad=1}
 END{exit (bad||NR!=13||v["width"]!=1010||v["height"]!=376||v["fps"]!=60||v["maxfps"]!=60||
  v["safex"]<160||v["safey"]<0||v["safew"]<1||v["safeh"]<1||v["safex"]+v["safew"]>1010||v["safey"]+v["safeh"]>376||
  v["nsafex"]!=v["safex"]-160||v["nsafey"]!=v["safey"]||v["nsafew"]!=v["safew"]||v["nsafeh"]!=v["safeh"]||
  v["alturl"]!="maps:/car/instrumentcluster/map")}' "$1"
}
