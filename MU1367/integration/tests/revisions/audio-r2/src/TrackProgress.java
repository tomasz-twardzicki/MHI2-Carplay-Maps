/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;

import de.vw.mib.bap.datatypes.BAPEntity;
import de.vw.mib.bap.functions.*;
import de.vw.mib.bap.mqbab2.common.api.stages.*;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.PlayPosition_Status;

/** AudioSD function 0x34. Uses the factory pool, listener, cache and marshaller. */
public final class TrackProgress extends Function implements Property {
    static TrackProgress stage;
    static long sends,failures;
    static volatile long indicationErrors,gets,ackRequests;
    static volatile int lastIndicationError=-1;
    long retryAt=-1;
    int lastPosition=-1,lastTotal=-1;
    public int getFunctionId(){return 52;}
    public BAPEntity init(BAPStageInitializer ignored){stage=this;return value();}
    public void initialize(boolean ignored){lastPosition=lastTotal=-1;retryAt=-1;}
    public void uninitialize(){if(stage==this)stage=null;}
    public void setFunctionData(BAPStage from,Object data){}
    PlayPosition_Status value(){
        PlayPosition_Status out=(PlayPosition_Status)context.dequeueBAPEntity(this,ClassForStatus());
        out.reset();
        long now=TextBridge.now(),last=TextBridge.INSTANCE.lastTick;
        if(TextBridge.INSTANCE.connected&&TextBridge.eligible()&&last>=0&&now>=last&&now-last<1500){
            synchronized(TextBridge.MODEL){
                TextModel.Frame f=TextBridge.MODEL.frame();
                out.timePosition=ProgressModel.seconds(f);out.totalPlayTime=ProgressModel.total(f);
            }
        }
        return out;
    }
    // Explicit lookup is compatible with factory J9/class major 46.
    static Class ClassForStatus(){try{return Class.forName("de.vw.mib.bap.mqbab2.generated.audiosd.serializer.PlayPosition_Status");}
        catch(ClassNotFoundException e){throw new NoClassDefFoundError(e.getMessage());}}
    static void tick(long now){
        if(stage!=null)try{stage.process(-1);}catch(Throwable t){failures++;}
    }
    public void process(int ignored){
        long now=TextBridge.now();
        if(retryAt>=0&&now<retryAt&&retryAt-now<=1000)return;
        PlayPosition_Status out=value();
        if(out.timePosition==lastPosition&&out.totalPlayTime==lastTotal)return;
        // Cache equality may return false after dispatch; remember processed values.
        getDelegate().getPropertyListener(this).statusProperty(out,this);
        lastPosition=out.timePosition;lastTotal=out.totalPlayTime;sends++;
    }
    public void getProperty(BAPEntity ignored,PropertyListener listener){gets++;listener.statusProperty(value(),this);}
    public void setGetProperty(BAPEntity ignored,PropertyListener listener){listener.requestError(65,this);}
    public void ackProperty(BAPEntity ignored,PropertyListener listener){listener.requestError(65,this);}
    public void requestAcknowledge(){ackRequests++;lastPosition=lastTotal=-1;process(-1);}
    public void errorAcknowledge(){}
    public void indicationError(int error,BAPFunctionListener listener){
        indicationErrors++;lastIndicationError=error;lastPosition=lastTotal=-1;
        // 66 means not implemented OR temporarily unavailable. Do not infer
        // permanent lack of support or suppress recovery from that callback.
        retryAt=TextBridge.now()+1000;
    }
}
