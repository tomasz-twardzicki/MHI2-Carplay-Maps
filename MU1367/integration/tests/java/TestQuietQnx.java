/* Exact factory J9 probe, never installed. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

/** Message-scoped rejection, delta reuse and evidence on the factory VM. */
public final class TestQuietQnx {
    static int checks;
    static void check(boolean yes,String why)throws Exception{checks++;if(!yes)throw new Exception(why);}
    static byte[] join(byte[] a,byte[] b){byte[] c=new byte[a.length+b.length];System.arraycopy(a,0,c,0,a.length);System.arraycopy(b,0,c,a.length,b.length);return c;}
    static byte[] tlv(int id,byte[] b){byte[] out=new byte[b.length+4];out[0]=(byte)(out.length>>8);out[1]=(byte)out.length;out[2]=(byte)(id>>8);out[3]=(byte)id;System.arraycopy(b,0,out,4,b.length);return out;}
    static byte[] u16(int n){return new byte[]{(byte)(n>>8),(byte)n};}
    static void le(byte[] b,int at,int n){for(int i=0;i<4;i++)b[at+i]=(byte)(n>>(8*i));}
    static byte[] route(int phase,int index,int meters){
        return join(join(tlv(0,u16(16)),tlv(1,new byte[]{(byte)phase})),join(tlv(13,u16(index)),tlv(10,new byte[]{0,0,(byte)(meters>>8),(byte)meters})));
    }
    static byte[] maneuver(int index,int type){return join(join(tlv(0,u16(16)),tlv(1,u16(index))),join(tlv(3,new byte[]{(byte)type}),tlv(9,new byte[]{0})));}
    static byte[][] events=new byte[16][];static int sequence;
    static void add(int id,byte[] payload){
        byte[] e=new byte[16+payload.length];le(e,0,++sequence);e[4]=(byte)id;e[5]=(byte)(id>>8);e[6]=(byte)payload.length;e[7]=(byte)(payload.length>>8);le(e,8,1);
        System.arraycopy(payload,0,e,16,payload.length);events[(sequence-1)&15]=e;
    }
    static byte[] window(){
        int count=sequence<16?sequence:16;byte[] b=new byte[64];le(b,0,0x31494752);le(b,4,1);le(b,8,33088);le(b,16,1);le(b,20,sequence);le(b,24,count);le(b,36,1);le(b,40,1);
        for(int s=sequence-count+1;s<=sequence;s++)b=join(b,events[(s-1)&15]);
        return b;
    }
    public static void main(String[] args)throws Exception{
        LiveModel model=new LiveModel();long before=GuidanceEvidence.rejected;
        add(0x5201,tlv(1,new byte[]{0}));
        LiveModel.Frame f=model.snapshot(window(),1000,false);
        check(!f.active&&GuidanceEvidence.rejected==before+1,"malformed first route message rejected alone");
        check(GuidanceEvidence.lastRejected.indexOf("id=5201 field=1")>=0&&GuidanceEvidence.lastRejected.indexOf("shape=1:1=00")>=0,"rejection shape");
        add(0x5201,route(1,5,300));add(0x5202,maneuver(5,2));add(0x5201,route(1,5,250));
        f=model.snapshot(window(),1100,false);
        check(f.active&&f.main==13&&f.direction==192&&f.meters==250,"valid deltas decode with the bad message still in the window");
        add(0x5201,route(1,5,120));f=model.snapshot(window(),61100,false);
        check(f.active&&f.main==13&&f.meters==120,"distance-only delta reuses cached maneuver");
        String s=GuidanceEvidence.snapshot();
        check(s.length()<4096&&s.indexOf("hold_ms=180000")>=0&&s.indexOf("2:1")>=0,"evidence snapshot");
        check(LiveModel.HOLD_MS==180000L,"hold constant");
        // A captured reroute, on the factory VM.
        add(0x5201,join(tlv(0,u16(16)),tlv(1,new byte[]{5})));f=model.snapshot(window(),61200,false);
        check(f.active&&f.main==9&&f.direction==0&&f.meters==120,"rerouting keeps the counter");
        add(0x5201,join(tlv(0,u16(16)),tlv(1,new byte[]{0})));f=model.snapshot(window(),61300,false);
        check(f.active&&f.main==9&&f.meters==120,"stop inside a reroute is provisional");
        add(0x5201,join(tlv(0,u16(16)),tlv(1,new byte[]{3})));add(0x5202,maneuver(0,11));add(0x5201,route(1,0,0));f=model.snapshot(window(),61400,false);
        check(f.active&&f.main==9&&f.meters==120,"start maneuver at 0 m keeps the counter");
        add(0x5202,maneuver(1,2));add(0x5201,route(1,1,90));f=model.snapshot(window(),61500,false);
        check(f.active&&f.main==13&&f.direction==192&&f.meters==90,"real distance resumes guidance");
        System.out.println(new StringBuffer("QUIET_FACTORY_J9_PASS checks=").append(checks).toString());
    }
}
