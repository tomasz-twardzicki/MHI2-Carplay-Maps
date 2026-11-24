/* SPDX-License-Identifier: GPL-3.0-or-later. Exact pinned wireless CP adapter. */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
public final class PatchWirelessCp implements Opcodes {
    static final String OWNER="de/vw/mib/asl/internal/wcpcp/WcpCp",STATE="de/vw/mib/asl/internal/wcpcp/BorrowedScreen";
    public static void main(String[] args)throws Exception {
        ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(Paths.get(args[0]))).accept(c,ClassReader.SKIP_FRAMES);
        if(!c.name.equals(OWNER))throw new IllegalStateException("wireless CP class");int track=0,loop=0,down=0,left=0;
        for(MethodNode m:c.methods) {
            if(m.name.equals("trackScreen")&&m.desc.equals("([Ljava/lang/Object;)V")) {
                InsnList hook=new InsnList();hook.add(new VarInsnNode(ALOAD,0));hook.add(new FieldInsnNode(GETSTATIC,OWNER,"fgCarplay","Z"));
                hook.add(new MethodInsnNode(INVOKESTATIC,STATE,"track","([Ljava/lang/Object;Z)V",false));m.instructions.insert(hook);track++;
            }
            if(m.name.equals("loop")&&m.desc.equals("()V")) {
                // Insert inside the existing loop's back-edge label, so this
                // runs every iteration rather than only on worker startup.
                for(AbstractInsnNode n:m.instructions.toArray())if(n instanceof MethodInsnNode && ((MethodInsnNode)n).name.equals("drainQueue")) {
                    m.instructions.insertBefore(n,new MethodInsnNode(INVOKESTATIC,OWNER,"cpmapRestoreBorrowedScreen","()V",false));loop++;
                }
            }
            if(m.name.equals("onSessionDown")&&m.desc.equals("()V")) {m.instructions.insert(new MethodInsnNode(INVOKESTATIC,STATE,"cancel","()V",false));down++;}
            if(m.name.equals("onObserverEvent"))for(AbstractInsnNode n:m.instructions.toArray())if(n instanceof FieldInsnNode && n.getOpcode()==PUTSTATIC && ((FieldInsnNode)n).name.equals("fgCarplay") && n.getPrevious().getOpcode()==ICONST_0) {
                m.instructions.insert(n,new MethodInsnNode(INVOKESTATIC,STATE,"cancel","()V",false));left++;
            }
        }
        if(track!=1||loop!=1||down!=1||left!=1)throw new IllegalStateException("wireless CP shape "+track+":"+loop+":"+down+":"+left);
        MethodNode restore=new MethodNode(ACC_PRIVATE|ACC_STATIC,"cpmapRestoreBorrowedScreen","()V",null,null);
        LabelNode done=new LabelNode();InsnList b=restore.instructions;
        b.add(new MethodInsnNode(INVOKESTATIC,STATE,"consume","()Z",false));b.add(new JumpInsnNode(IFEQ,done));
        b.add(new MethodInsnNode(INVOKESTATIC,OWNER,"sessionFresh","()Z",false));b.add(new JumpInsnNode(IFEQ,done));
        b.add(new FieldInsnNode(GETSTATIC,OWNER,"weRegistered","Z"));b.add(new JumpInsnNode(IFEQ,done));
        b.add(new FieldInsnNode(GETSTATIC,OWNER,"stage","I"));b.add(new InsnNode(ICONST_3));b.add(new JumpInsnNode(IF_ICMPLT,done));
        b.add(new LdcInsnNode(Integer.valueOf(2910012)));b.add(new MethodInsnNode(INVOKESTATIC,OWNER,"submitHmiEvent","(I)Z",false));b.add(new JumpInsnNode(IFEQ,done));
        b.add(new InsnNode(ICONST_1));b.add(new FieldInsnNode(PUTSTATIC,OWNER,"confirmScreen","Z"));
        b.add(new LdcInsnNode("ui 0"));b.add(new MethodInsnNode(INVOKESTATIC,OWNER,"enqueue","(Ljava/lang/String;)V",false));
        b.add(new LdcInsnNode("screen return"));b.add(new LdcInsnNode("restore pre-borrow CarPlay via HMI event 2910012"));
        b.add(new MethodInsnNode(INVOKESTATIC,OWNER,"log2","(Ljava/lang/String;Ljava/lang/String;)V",false));
        b.add(done);b.add(new InsnNode(RETURN));c.methods.add(restore);c.version=V1_2;
        ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(writer);Files.write(Paths.get(args[1]),writer.toByteArray());
    }
}
