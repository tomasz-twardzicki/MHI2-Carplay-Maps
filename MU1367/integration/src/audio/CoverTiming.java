/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;

/** Last eight ready images, numeric times only. All disk I/O stays on the worker. */
final class CoverTiming {
    static final long[][] rows=new long[8][];
    static int next;
    static long delay(long begin,long end){return begin>=0&&end>=begin?end-begin:-1;}
    static synchronized void ready(int handle,long seen,long matched,long ready,long process,int attempts,long text){
        rows[next]=new long[]{handle,seen,matched,ready,process,attempts,text,-1,-1};next=(next+1)%rows.length;
    }
    static synchronized void accepted(int handle,long time){for(int i=0;i<rows.length;i++)if(rows[i]!=null&&rows[i][0]==handle&&rows[i][7]<0)rows[i][7]=time;}
    static synchronized void pushed(int handle,long time){for(int i=0;i<rows.length;i++)if(rows[i]!=null&&rows[i][0]==handle&&rows[i][8]<0)rows[i][8]=time;}
    static synchronized void fetched(int handle,long[] report){
        if(report==null)return;
        for(int i=0;i<rows.length;i++)if(rows[i]!=null&&rows[i][0]==handle){
            long[] extended=new long[16];System.arraycopy(rows[i],0,extended,0,9);System.arraycopy(report,0,extended,9,7);rows[i]=extended;return;
        }
    }
    static synchronized String status(){
        StringBuffer s=new StringBuffer(2048);s.append("format=1 timings=1 units=ms rows_max=8\n");
        for(int n=0;n<rows.length;n++){
            long[] r=rows[(next+n)%rows.length];if(r==null)continue;
            s.append("handle=").append(r[0]).append(" attempts=").append(r[5]);
            s.append(" text_to_ready_ms=").append(delay(r[6],r[3])).append(" pps_to_match_ms=").append(delay(r[1],r[2]));
            s.append(" pps_to_ready_ms=").append(delay(r[1],r[3])).append(" match_to_ready_ms=").append(delay(r[2],r[3]));
            s.append(" last_fetch_process_ms=").append(r[4]).append(" ready_to_handle_ms=").append(delay(r[3],r[7]));
            s.append(" ready_to_push_ms=").append(delay(r[3],r[8]));
            if(r.length==16){
                s.append(" native_read_ms=").append(r[9]).append(" decode_write_ms=").append(r[10]).append(" native_recheck_ms=").append(r[11]);
                s.append(" png_bytes=").append(r[12]).append(" input_bytes=").append(r[13]).append(" input_width=").append(r[14]).append(" input_height=").append(r[15]);
            }
            s.append('\n');
        }
        return s.toString();
    }
}
