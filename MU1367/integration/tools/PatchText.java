/* SPDX-License-Identifier: GPL-3.0-or-later. Host-only ASM tool. */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class PatchText implements Opcodes {
    static final String HELPER="com/cpmap/audio/TextBridge";
    static final String FUNCTION="de/vw/mib/bap/mqbab2/common/api/stages/Function";
    static void require(boolean ok) { if(!ok) throw new IllegalStateException("Factory audio shape differs"); }
    static MethodNode method(ClassNode c,String name) {
        MethodNode found=null;
        for(MethodNode m:c.methods) if(m.name.equals(name)) { require(found==null); found=m; }
        require(found!=null); return found;
    }
    static InsnList stageHook(String name) {
        InsnList n=new InsnList(); n.add(new VarInsnNode(ALOAD,0));
        n.add(new MethodInsnNode(INVOKESTATIC,HELPER,name,"(L"+FUNCTION+";)V",false)); return n;
    }
    public static void main(String[] args) throws Exception {
        ClassNode c=new ClassNode();
        new ClassReader(Files.readAllBytes(Paths.get(args[0]))).accept(c,ClassReader.SKIP_FRAMES);
        require(c.version==V1_5 && c.name.equals("de/vw/mib/bap/mqbab2/audiosd/functions/CurrentStationInfo"));
        c.version=V1_2;
        MethodNode fill=method(c,"setStationInfoForMirrorLink");
        require(fill.desc.equals("(Lde/vw/mib/bap/mqbab2/generated/audiosd/serializer/CurrentStationInfo_Status;)V"));
        InsnList guard=new InsnList(); LabelNode stock=new LabelNode();
        guard.add(new VarInsnNode(ALOAD,1));
        guard.add(new MethodInsnNode(INVOKESTATIC,HELPER,"fill",fill.desc.replace(")V",")Z"),false));
        guard.add(new JumpInsnNode(IFEQ,stock)); guard.add(new InsnNode(RETURN)); guard.add(stock);
        fill.instructions.insert(guard);
        int attaches=0;
        for(AbstractInsnNode n:method(c,"init").instructions.toArray()) if(n.getOpcode()==ARETURN) {
            method(c,"init").instructions.insertBefore(n,stageHook("attach")); attaches++;
        }
        require(attaches==1);
        method(c,"uninitialize").instructions.insert(stageHook("detach"));
        MethodNode phone=method(c,"updateSmartphoneIntegrationData");
        InsnList notify=new InsnList(); notify.add(new VarInsnNode(ALOAD,1));
        notify.add(new MethodInsnNode(INVOKESTATIC,HELPER,"connection","(Lde/vw/mib/bap/mqbab2/common/api/smartphoneintegration/SmartphoneIntegrationService;)V",false));
        phone.instructions.insert(notify);
        int sends=0;
        for(MethodNode m:c.methods) for(AbstractInsnNode n:m.instructions.toArray()) if(n instanceof MethodInsnNode) {
            MethodInsnNode call=(MethodInsnNode)n;
            if(call.owner.equals("de/vw/mib/bap/functions/PropertyListener") && call.name.equals("statusProperty")) {
                InsnList accept=new InsnList(); accept.add(new VarInsnNode(ALOAD,0));
                accept.add(new MethodInsnNode(INVOKESTATIC,HELPER,"accepted","(ZL"+FUNCTION+";)Z",false));
                m.instructions.insert(n,accept); sends++;
            }
        }
        require(sends==1);
        ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS); c.accept(writer);
        Path dest=Paths.get(args[1]).resolve(c.name+".class"); Files.createDirectories(dest.getParent());
        Files.write(dest,writer.toByteArray());
    }
}
