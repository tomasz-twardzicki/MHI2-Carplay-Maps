/* SPDX-License-Identifier: GPL-3.0-or-later. Host-only exact-factory patch. */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class PatchProgress implements Opcodes {
    static void require(boolean ok){if(!ok)throw new IllegalStateException("Unexpected factory progress shape");}
    public static void main(String[] args)throws Exception{
        ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(Paths.get(args[0]))).accept(c,ClassReader.SKIP_FRAMES);
        int hooks=0;
        if(c.name.equals("de/vw/mib/bap/mqbab2/generated/audiosd/BAPAudioSDDataPool")){
            require(c.version==V1_2);
            for(MethodNode m:c.methods)if(m.name.equals("initializeInternal"))for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()==RETURN){
                InsnList h=new InsnList();h.add(new VarInsnNode(ALOAD,0));
                h.add(new TypeInsnNode(NEW,"com/cpmap/audio/TrackProgress"));h.add(new InsnNode(DUP));
                h.add(new MethodInsnNode(INVOKESPECIAL,"com/cpmap/audio/TrackProgress","<init>","()V",false));
                h.add(new InsnNode(ICONST_3));h.add(new InsnNode(ICONST_1));h.add(new LdcInsnNode("PlayPosition"));
                h.add(new MethodInsnNode(INVOKEVIRTUAL,c.name,"addStage","(Lde/vw/mib/bap/mqbab2/common/api/stages/BAPStage;IILjava/lang/String;)V",false));
                m.instructions.insertBefore(n,h);hooks++;
            }
        }else if(c.name.equals("de/vw/mib/bap/mqbab2/common/marshalling/BAPServiceProxy")){
            require(c.version==V1_2);
            for(MethodNode m:c.methods)if(m.name.equals("requestByteSequence")&&m.desc.equals("(II[B)V")){
                m.instructions.insert(nativeHook(c,"nativeCall",true));
                for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()==RETURN){m.instructions.insertBefore(n,nativeHook(c,"nativeReturn",false));hooks++;}
            }
        }else if(c.name.equals("de/vw/mib/bap/internal/dispatcher/BAPDispatcherTarget")){
            require(c.version==V1_5);
            for(MethodNode m:c.methods){
                String hook=m.name.equals("acknowledge")?"ack":m.name.equals("indicationError")?"error":m.name.equals("indicationVoid")?"indication":null;
                if(hook!=null&&m.desc.equals("(III)V")){
                    InsnList h=new InsnList();for(int i=1;i<=3;i++)h.add(new VarInsnNode(ILOAD,i));
                    h.add(new MethodInsnNode(INVOKESTATIC,"com/cpmap/audio/AudioDiagnostics",hook,"(III)V",false));m.instructions.insert(h);hooks++;
                }else if(m.name.equals("asyncException")&&m.desc.equals("(ILjava/lang/String;I)V")){
                    InsnList h=new InsnList();h.add(new VarInsnNode(ILOAD,1));h.add(new VarInsnNode(ILOAD,3));
                    h.add(new MethodInsnNode(INVOKESTATIC,"com/cpmap/audio/AudioDiagnostics","async","(II)V",false));m.instructions.insert(h);hooks++;
                }
            }
        }else{
            require(c.version==V1_5);
            require(c.name.equals("de/vw/mib/bap/mqbab2/audiosd/functions/FunctionList"));
            for(MethodNode m:c.methods)if(m.name.equals("usedFunctionList"))for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()==ARETURN){
                InsnList h=new InsnList();h.add(new InsnNode(DUP));h.add(new InsnNode(ICONST_1));
                h.add(new FieldInsnNode(PUTFIELD,"de/vw/mib/bap/mqbab2/generated/audiosd/serializer/FunctionList_FctList","fctPlayPositionAvailable","Z"));
                m.instructions.insertBefore(n,h);hooks++;
            }
        }
        require(hooks==(c.name.endsWith("BAPDispatcherTarget")?4:1));c.version=V1_2;ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(writer);
        Path dest=Paths.get(args[1]).resolve(c.name+".class");Files.createDirectories(dest.getParent());Files.write(dest,writer.toByteArray());
    }
    static InsnList nativeHook(ClassNode c,String name,boolean bytes){
        InsnList h=new InsnList();h.add(new VarInsnNode(ALOAD,0));
        h.add(new MethodInsnNode(INVOKESPECIAL,c.name,"getLogicalControlUnit","()Lde/vw/mib/asl/api/bap/lcu/BAPLogicalControlUnit;",false));
        h.add(new MethodInsnNode(INVOKEINTERFACE,"de/vw/mib/asl/api/bap/lcu/BAPLogicalControlUnit","getLogicalControlUnitID","()I",true));
        h.add(new VarInsnNode(ILOAD,1));h.add(new VarInsnNode(ILOAD,2));if(bytes)h.add(new VarInsnNode(ALOAD,3));
        h.add(new MethodInsnNode(INVOKESTATIC,"com/cpmap/audio/AudioDiagnostics",name,bytes?"(III[B)V":"(III)V",false));return h;
    }
}
