/* SPDX-License-Identifier: GPL-3.0-or-later. Host-only, exact stock class. */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
public final class PatchMedia implements Opcodes {
    public static void main(String[] args)throws Exception {
        ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(Paths.get(args[0]))).accept(c,ClassReader.SKIP_FRAMES);
        if(c.version!=V1_5||!c.name.equals("de/esolutions/fw/dsi/carplay/DSICarplayDispatcher"))throw new IllegalStateException("factory dispatcher shape");
        int changes=0;
        for(MethodNode m:c.methods)if(m.name.equals("<init>")&&m.desc.equals("(I)V"))for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()==RETURN) {
            InsnList hook=new InsnList();hook.add(new VarInsnNode(ALOAD,0));hook.add(new VarInsnNode(ILOAD,1));
            hook.add(new MethodInsnNode(INVOKESTATIC,"com/cpmap/audio/WirelessMedia","register","(Lde/esolutions/fw/dsi/carplay/DSICarplayDispatcher;I)V",false));
            m.instructions.insertBefore(n,hook);changes++;
        }
        if(changes!=1)throw new IllegalStateException("factory constructor shape");c.version=V1_2;
        ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(writer);Path out=Paths.get(args[1]).resolve(c.name+".class");Files.createDirectories(out.getParent());Files.write(out,writer.toByteArray());
    }
}
