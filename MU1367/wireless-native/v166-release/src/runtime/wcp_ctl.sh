#!/bin/sh
# Wireless CarPlay Maps. Maintainer: omonob. Source date: 2026-08-29.
# wcp_ctl.sh —— 在车机上起停 wcp_receiver + wcp_video(台架测试用;推到 /dev/shmem 后 sh 执行)
#
#   sh /dev/shmem/wcp_ctl.sh start [nomfi]   起 wcp_video(解码上屏,后台)再起接收端(后台)
#                                            日志 /dev/shmem/wcp.log、/dev/shmem/wcp_video.log
#   sh /dev/shmem/wcp_ctl.sh selftest        本机 pairtest 跑一遍(需要 /dev/shmem/wcp_pairtest)
#   sh /dev/shmem/wcp_ctl.sh selftest session  同上,再走 SETUP/info/RECORD/屏幕流(扮演手机,经 lo0,不受 pf 影响)
#                                            设 WCP_TEST_H264=/dev/shmem/x.h264 时发真实码流(画面能上屏),
#                                            WCP_TEST_FRAMES 帧数(默认 300)
#   sh /dev/shmem/wcp_ctl.sh status          进程 / 监听 / 日志尾
#   sh /dev/shmem/wcp_ctl.sh stop            按 pid 文件结束(只 kill 自己起的 pid;wcp_video 收到 TERM 会先还原主屏)
#   sh /dev/shmem/wcp_ctl.sh demo [文件]     不用手机:硬件解码一段 Annex-B 测试流(默认 /dev/shmem/test800.h264)
#                                            自动切主屏、放完还原 —— 用来目视确认"画面能上屏"
#   sh /dev/shmem/wcp_ctl.sh restore         主屏上下文手动还原(dmdt sc 0 $WCP_VIDEO_RESTORE_CTX,默认 0)
#
# 车机限制(见 docs/operations.md、MEMORY):
#   · 绝不按名字 slay/kill —— slay -f sh 会杀掉 sshd 子进程,整机重启;这里只按 pid 文件。
#   · ksh:不认 set -u、不认 CRLF;没有 date/wc/awk/find/printf/env/tr/cmp。
#   · /dev/shmem 不支持子目录,数据目录不能放那里。
#
# 环境变量(可选):
#   WCP_DATA  数据目录,默认 /mnt/persist/wcp(持久:手机记住的配对身份在这里,丢了要重新配对)
#   WCP_PORT  默认 5000(必须等于 btwcp 0x4301 参数 2)
#   WCP_LOG   追加 SDK 日志配置,例如 "?Pairing:level=trace"
#   WCP_BTMAC       车机蓝牙地址,写进 /info 的 bluetoothIDs(见 btwcp 日志 "本机 BD_ADDR=")
#   WCP_H264_DUMP   屏幕流转成 Annex-B 写到这个文件(例 /dev/shmem/wcp.h264);WCP_H264_MAX 上限字节,默认 8 MB
#   WCP_REQUESTUI=1 会话开始后主动请手机显示 CarPlay(默认不发)
#   2B(上屏,详见 src/wcp_video.c 文件头):
#   WCP_VIDEO=0           不起 wcp_video、接收端不转发(回到 2A 只计数)
#   WCP_VIDEO_DMDT=1      第一帧解出后自动 dmdt dc 95 59 + sc 0 95 把主屏切给 CarPlay 图层,流结束 sc 0 0 还原
#                         (默认不切:图层在,但 HMI 当前上下文里没有 59,看不见)
#   WCP_VIDEO_RESTORE_CTX 还原时切回的上下文,默认 0(HMI 停在非地图界面时就是 0)
#   WCP_VIDEO_RECT=x,y,w,h  主屏上的目标矩形;默认按宽高比居中铺满 1280x640
#   WCP_VIDEO_TS=now      帧时间戳送"送入时刻"(旧行为,对照用);默认送 0,NvSS 不做迟到丢帧(见 src/wcp_video.c「时间戳」)

BIN=/dev/shmem/wcp_receiver
VBIN=/dev/shmem/wcp_video
PT=/dev/shmem/wcp_pairtest
PIDF=/dev/shmem/wcp_receiver.pid
VPIDF=/dev/shmem/wcp_video.pid
LOG=/dev/shmem/wcp.log
VLOG=/dev/shmem/wcp_video.log
: ${WCP_DATA:=/mnt/persist/wcp}
: ${WCP_PORT:=5000}
: ${WCP_VIDEO_RESTORE_CTX:=0}
export WCP_DATA WCP_PORT WCP_VIDEO_RESTORE_CTX
# NvSS / KD 在 /mnt/app/armle/lib、/lib(同 smartphone_integrator.json 里 carplay 子进程的路径)
VLD=/mnt/app/root/lib-target:/eso/lib:/mnt/app/usr/lib:/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib:/lib:/usr/lib

# 只认"pid 文件里的 pid 还活着、而且进程名确实对"——
# 进程崩了之后 pid 可能被别的进程复用,不核对名字就 kill 可能杀错(车机上杀错 = 可能整机重启)。
alive() {   # $1 = pid 文件, $2 = 进程名
    [ -f $1 ] || return 1
    P=`cat $1`
    case "$P" in ''|*[!0-9]*|0|1) return 1;; esac
    kill -0 $P 2>/dev/null || return 1
    # Factory pidin defaults to an 18-character, truncated process name.
    # This full-name format is exercised with the MU1367 firmware binary.
    # exec keeps the tracked PID through preflight. Match complete known paths
    # for both roles: the video wrapper execs wcp_video_tap, not wcp_video.
    # An unrelated process with the same basename never owns this receipt.
    case "$2" in
    wcp_receiver)
        pidin -p $P -F '%256n' 2>/dev/null | grep -q -E '^/*(dev/shmem/wcp_receiver|mnt/app/carplaymaps/wireless-receiver-exec) *$' ;;
    wcp_video)
        pidin -p $P -F '%256n' 2>/dev/null | grep -q -E '^/*(dev/shmem/wcp_video|mnt/app/carplaymaps/wcp_video_tap|mnt/app/carplaymaps/wireless-video-exec) *$' ;;
    *) return 1 ;;
    esac
}
running() { alive $PIDF wcp_receiver; }
launch_stamp() {
    if [ -x /mnt/app/carplaymaps/wireless-receiver-exec ];then
        /mnt/app/carplaymaps/wireless-receiver-exec --launch-stamp "$1" "$2" >/dev/null 2>&1
    fi
    return 0
}

stop_one() {   # $1 = pid 文件, $2 = 进程名
    if alive $1 $2; then
        P=`cat $1`
        kill $P; sleep 2
        kill -0 $P 2>/dev/null && { echo "$2 pid=$P 未退出,发 KILL"; kill -9 $P; }
        echo "已停止 $2 pid=$P"
    else
        echo "$2 未运行"
    fi
    rm -f $1
}

case "$1" in
start)
    if running; then echo "已在运行 pid=`cat $PIDF`"; exit 0; fi
    # The receiver registers Bonjour during startup. Do not advertise it until
    # the AP and the complete, validated PF overlay are ready.
    /bin/sh /mnt/ota/wcp_pf.sh on || { echo WCP_PF_NOT_READY;exit 1; }
    [ -x $BIN ] || { echo "缺 $BIN"; exit 1; }
    if [ "$2" = "nomfi" ]; then WCP_NOMFI=1; export WCP_NOMFI; fi
    if [ "$WCP_VIDEO" != "0" ] && [ -x $VBIN ] && ! alive $VPIDF wcp_video; then
        launch_stamp video-before 0
        VIDEO_ENTRY=$VBIN
        if [ -x /mnt/app/carplaymaps/wireless-video-exec ]; then
            VIDEO_ENTRY=/mnt/app/carplaymaps/wireless-video-exec
            CPMAP_PRIMARY_30FPS=1 LD_LIBRARY_PATH=$VLD $VIDEO_ENTRY </dev/null > $VLOG 2>&1 &
        else
            CPMAP_PRIMARY_30FPS=1 LD_PRELOAD=/mnt/app/carplaymaps/libcpvc-mirror-tap.so LD_LIBRARY_PATH=$VLD $VBIN </dev/null > $VLOG 2>&1 &
        fi
        CHILD_PID=$!
        echo $CHILD_PID > $VPIDF
        launch_stamp video-after "$CHILD_PID"
        sleep 1
        alive $VPIDF wcp_video && echo "wcp_video 已启动 pid=`cat $VPIDF`" || { echo "wcp_video 启动失败:"; cat $VLOG; }
    fi
    # Own preflight/exec retains the PID expected by the original controller.
    # All accepted phone/BT/video/identity logic remains in the same receiver.
    [ -x /mnt/app/carplaymaps/wireless-receiver-exec ] || { echo "V75 receiver bootstrap missing"; exit 1; }
    launch_stamp receiver-before 0
    LD_LIBRARY_PATH=$VLD /mnt/app/carplaymaps/wireless-receiver-exec </dev/null > $LOG 2>&1 &
    CHILD_PID=$!
    echo $CHILD_PID > $PIDF
    launch_stamp receiver-after "$CHILD_PID"
    sleep 2
    if running; then
        echo "已启动 pid=`cat $PIDF` data=$WCP_DATA port=$WCP_PORT"
        netstat -an | grep "\.$WCP_PORT "
        # Pairing identity remains in the per-unit store; do not print it.
    else
        echo "启动失败,日志:"; cat $LOG; rm -f $PIDF; exit 1
    fi
    ;;
selftest)
    running || { echo "接收端没在运行"; exit 1; }
    [ -x $PT ] || { echo "缺 $PT"; exit 1; }
    mkdir -p /var/tmp/wcp_pairtest
    # 第 2 个参数 session:配对后继续走会话 + 发屏幕流,接收端日志里应出现 [wcp][screen] SPS 分辨率
    if [ -n "$WCP_TEST_H264" ]; then
        WCP_DATA=/var/tmp/wcp_pairtest $PT 127.0.0.1 $WCP_PORT 3939 $2 800 480 ${WCP_TEST_FRAMES:-300}
    else
        WCP_DATA=/var/tmp/wcp_pairtest $PT 127.0.0.1 $WCP_PORT 3939 $2
    fi
    R=$?
    rm -rf /var/tmp/wcp_pairtest
    echo "selftest rc=$R(0=通过)"
    exit $R
    ;;
status)
    if running; then echo "运行中 pid=`cat $PIDF`"; else echo "未运行"; fi
    if alive $VPIDF wcp_video; then echo "wcp_video 运行中 pid=`cat $VPIDF`"; else echo "wcp_video 未运行"; fi
    # 控制端口 + 会话固定端口(见 src/wcp_session_wrap.c;会话建立后才会出现)+ wcp_video 7101
    netstat -an | grep -e "\.$WCP_PORT " -e "\.5001 " -e "\.5020 " -e "\.600[0-4] " -e "\.6011 " -e "\.6020 " -e "\.6030 " -e "\.7101 "
    echo "--- $LOG(尾)"; tail -20 $LOG 2>/dev/null
    echo "--- $VLOG(尾)"; tail -10 $VLOG 2>/dev/null
    [ -f /dev/shmem/wcp_touch_fg ] && echo "触摸当前归 CarPlay:`cat /dev/shmem/wcp_touch_fg`"
    ;;
stop)
    stop_one $PIDF wcp_receiver
    stop_one $VPIDF wcp_video
    ;;
demo)
    # 不用手机看效果:wcp_video 直接读 Annex-B 文件硬件解码,自动切主屏(dc 95 59 / sc 0 95),放完 sc 0 0 还原。
    # 放的时候**别碰屏幕**:触摸仍然交给(被盖住的)HMI 当前界面。
    F=${2:-/dev/shmem/test800.h264}
    [ -x $VBIN ] || { echo "缺 $VBIN"; exit 1; }
    [ -f $F ] || { echo "缺 $F"; exit 1; }
    alive $VPIDF wcp_video && echo "注意:服务模式的 wcp_video 也在跑(没有会话时它不占解码器,可以继续)"
    echo "放 $F(约 20 秒),主屏应出现测试图案,放完自动还原"
    WCP_VIDEO_DMDT=1 LD_LIBRARY_PATH=$VLD $VBIN --file $F 30 1 2 2>&1 | grep -v -e "^Query" -e "^Created" -e "^nvss_decode"
    ;;
restore)
    IPL_CONFIG_DIR=/etc/eso/production LD_LIBRARY_PATH=/mnt/app/eso/lib:/eso/lib:/mnt/app/armle/lib:/armle/lib \
        /mnt/app/eso/bin/apps/dmdt sc 0 $WCP_VIDEO_RESTORE_CTX
    rm -f /dev/shmem/wcp_touch_fg       # 2C:触摸还给 HMI(wcp_video 被 kill -9 时它不会自己删;不删 3 秒后 HMI 也会自动不认)
    echo "已执行 dmdt sc 0 $WCP_VIDEO_RESTORE_CTX,触摸已还给 HMI"
    ;;
*)
    echo "用法: sh $0 start [nomfi] | selftest [session] | status | stop | demo [文件] | restore"
    exit 1
    ;;
esac
