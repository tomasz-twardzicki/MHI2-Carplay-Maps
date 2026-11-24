/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.PlayPosition_Status;
import de.vw.mib.bap.stream.BitStreamTransformer;

/** Counters at the real factory DSI boundary; an asynchronous return is not a bus acknowledgement. */
public final class AudioDiagnostics {
    static volatile long nativeCalls,nativeReturns,acks,errors,indications,asyncErrors;
    static volatile int nativePosition=-1,nativeTotal=-1,lastOpcode=-1,lastAck=-1,lastError=-1,lastIndication=-1;
    static volatile int lastAsyncError=-1,lastAsyncRequest=-1;
    static boolean ours(int lcu,int function){return lcu==49&&function==52;}
    public static void nativeCall(int lcu,int function,int opcode,byte[] bytes){
        if(!ours(lcu,function))return;
        nativeCalls++;lastOpcode=opcode;
        if(bytes!=null&&bytes.length==6)try{
            PlayPosition_Status s=new PlayPosition_Status(BitStreamTransformer.newBitStreamForValue(bytes));
            nativePosition=s.timePosition;nativeTotal=s.totalPlayTime;
        }catch(Throwable ignored){}
    }
    public static void nativeReturn(int lcu,int function,int opcode){if(ours(lcu,function))nativeReturns++;}
    public static void ack(int lcu,int function,int type){if(ours(lcu,function)){acks++;lastAck=type;}}
    public static void error(int lcu,int function,int error){if(ours(lcu,function)){errors++;lastError=error;}}
    public static void indication(int lcu,int function,int type){if(ours(lcu,function)){indications++;lastIndication=type;}}
    // asyncException has no LCU/function identity. Never attribute it to progress.
    public static void async(int error,int request){asyncErrors++;lastAsyncError=error;lastAsyncRequest=request;}
    static void append(StringBuffer s){
        s.append(" progress_native_calls=").append(nativeCalls).append(" progress_native_returns=").append(nativeReturns);
        s.append(" progress_native_position_s=").append(nativePosition).append(" progress_native_total_s=").append(nativeTotal);
        s.append(" progress_native_opcode=").append(lastOpcode).append(" progress_native_acks=").append(acks).append(" progress_native_ack_type=").append(lastAck);
        s.append(" progress_native_errors=").append(errors).append(" progress_native_error_code=").append(lastError);
        s.append(" progress_native_indications=").append(indications).append(" progress_native_indication_type=").append(lastIndication);
        s.append(" bap_async_errors_global=").append(asyncErrors).append(" bap_async_last_error=").append(lastAsyncError).append(" bap_async_last_request=").append(lastAsyncRequest);
    }
}
