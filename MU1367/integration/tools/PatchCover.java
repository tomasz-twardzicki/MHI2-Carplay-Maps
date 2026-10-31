/* SPDX-License-Identifier: GPL-3.0-or-later. Host-only exact-shape patcher. */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
public final class PatchCover implements Opcodes {
    static final String H="com/cpmap/audio/CoverBridge", HANDLE="de/vw/mib/bap/mqbab2/audiosd/functions/CurrentStationHandle";
    static final String STATUS="Lde/vw/mib/bap/mqbab2/generated/audiosd/serializer/CurrentStation_Handle_Status;";
    static final String SERVER="Lorg/dsi/ifc/kombipictureserver/DSIKombiPictureServer;";
    static void require(boolean ok){if(!ok)throw new IllegalStateException("MU1367 picture-service shape");}
    static MethodNode method(ClassNode c,String name,String desc){
        MethodNode found=null;for(MethodNode m:c.methods)if(m.name.equals(name)&&m.desc.equals(desc)){require(found==null);found=m;}require(found!=null);return found;
    }
    static MethodInsnNode call(String name,String desc){return new MethodInsnNode(INVOKESTATIC,H,name,desc,false);}
    static void beforeReturn(MethodNode m,int opcode,InsnList hook){
        int count=0;for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()==opcode){count++;m.instructions.insertBefore(n,hook);}
        require(count==1);
    }
    static InsnList stage(String name){InsnList n=new InsnList();n.add(new VarInsnNode(ALOAD,0));n.add(call(name,"(L"+HANDLE+";)V"));return n;}
    static void guard(ClassNode c,MethodNode m,boolean transmit){
        InsnList n=new InsnList();LabelNode stock=new LabelNode();n.add(new VarInsnNode(ALOAD,0));
        n.add(new MethodInsnNode(INVOKESPECIAL,c.name,"getKombiPictureServer","()"+SERVER,false));
        n.add(new VarInsnNode(LLOAD,1));n.add(new VarInsnNode(ILOAD,3));n.add(new VarInsnNode(ILOAD,4));
        n.add(call("answer","("+SERVER+"JII)Z"));n.add(new JumpInsnNode(IFEQ,stock));n.add(new InsnNode(RETURN));n.add(stock);
        m.instructions.insert(n);
    }
    public static void main(String[] a)throws Exception{
        ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(Paths.get(a[0]))).accept(c,ClassReader.SKIP_FRAMES);require(c.version==V1_5);c.version=V1_2;
        if(c.name.equals(HANDLE)){
            InsnList fill=new InsnList();fill.add(new VarInsnNode(ALOAD,1));fill.add(call("fill","("+STATUS+")V"));
            beforeReturn(method(c,"setCurrentStationHandleData","("+STATUS+")V"),RETURN,fill);
            beforeReturn(method(c,"init","(Lde/vw/mib/bap/mqbab2/common/api/stages/BAPStageInitializer;)Lde/vw/mib/bap/datatypes/BAPEntity;"),ARETURN,stage("attach"));
            method(c,"uninitialize","()V").instructions.insert(stage("detach"));
            MethodNode send=method(c,"sendCurrentStationHandleStatus","("+STATUS+")V");int count=0;
            for(AbstractInsnNode n:send.instructions.toArray())if(n instanceof MethodInsnNode&&((MethodInsnNode)n).name.equals("statusProperty")){
                InsnList ok=new InsnList();ok.add(new VarInsnNode(ALOAD,1));ok.add(new VarInsnNode(ALOAD,0));ok.add(call("accepted","(Z"+STATUS+"L"+HANDLE+";)Z"));send.instructions.insert(n,ok);count++;
            }require(count==1);
        }else{
            require(c.name.equals("de/vw/mib/asl/internal/kombipictureserver/usecaces/CoverArt"));
            MethodNode get=method(c,"getKombiPictureServer","()"+SERVER);InsnList proxy=new InsnList();proxy.add(new InsnNode(DUP));proxy.add(call("server","("+SERVER+")V"));beforeReturn(get,ARETURN,proxy);
            guard(c,method(c,"dsiKombiPictureServerIndicationCoverArt","(JII)V"),false);
            guard(c,method(c,"_transmitCoverArt","(JIII Lorg/dsi/ifc/global/ResourceLocator;)V".replace(" ","")),true);
            InsnList stop=new InsnList();stop.add(new InsnNode(ACONST_NULL));stop.add(call("server","("+SERVER+")V"));method(c,"uninitialize","()V").instructions.insert(stop);
        }
        ClassWriter w=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(w);Path p=Paths.get(a[1]).resolve(c.name+".class");Files.createDirectories(p.getParent());Files.write(p,w.toByteArray());
    }
}
