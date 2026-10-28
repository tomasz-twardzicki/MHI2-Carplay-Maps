/* Host-only ASM tools. SPDX-License-Identifier: GPL-3.0-or-later */
import java.nio.file.*;
import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class PatchSettings implements Opcodes {
    static void require(boolean b){if(!b)throw new IllegalStateException("Unexpected firmware/settings bytecode");}
    static ClassNode read(Path file)throws Exception {ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(file)).accept(c,ClassReader.SKIP_FRAMES);return c;}
    static void write(ClassNode c,Path root)throws Exception {
        c.version=V1_2;
        for(MethodNode m:c.methods){m.localVariables=null;
            for(AbstractInsnNode n:m.instructions){
                require(!(n instanceof InvokeDynamicInsnNode));
                if(n instanceof LdcInsnNode)require(!(((LdcInsnNode)n).cst instanceof Type));
                if(n instanceof MethodInsnNode){String owner=((MethodInsnNode)n).owner;
                    require(!owner.equals("java/lang/StringBuilder")&&!owner.startsWith("java/nio/")&&!owner.startsWith("java/util/concurrent/"));}
            }
        }
        ClassWriter w=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(w);Path out=root.resolve(c.name+".class");Files.createDirectories(out.getParent());Files.write(out,w.toByteArray());
    }
    public static void main(String[] args)throws Exception {
        Path input=Paths.get(args[1]),out=Paths.get(args[2]);
        if(args[0].equals("helpers")||args[0].equals("legacy")){
            try(java.util.stream.Stream<Path> paths=Files.walk(input)){
                for(Path p:(Iterable<Path>)paths.filter(v->v.toString().endsWith(".class"))::iterator){ClassNode c=read(p);require(args[0].equals("legacy")||c.name.startsWith("org/omonob/cpmap/ui/"));write(c,out);}
            }
        }else if(args[0].equals("menu")){
            ClassNode c=read(input);String target="de/vw/mib/view/internal/AbstractViewHandler";
            require(c.name.equals(target)&&c.version==V1_5);int count=0;
            for(MethodNode m:c.methods){
                String hook=m.name.equals("setup")?"attach":m.name.equals("activate")?"refresh":m.name.equals("deinit")||m.name.equals("destroy")?"detach":null;
                if(hook!=null&&m.desc.equals("()V")){int returns=0;
                    for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()==RETURN){
                        InsnList ins=new InsnList();ins.add(new VarInsnNode(ALOAD,0));ins.add(new MethodInsnNode(INVOKESTATIC,"org/omonob/cpmap/ui/IndependentMenuViewBridge",hook,"(L"+target+";)V",false));m.instructions.insertBefore(n,ins);returns++;
                    }
                    require(returns>0);count++;
                }
            }
            require(count==4);write(c,out);
        }else if(args[0].equals("controls")){
            ClassNode c=read(input);require(c.name.equals("de/vw/mib/carplay/clustercontrol/Mhi2ClusterControlBridge"));int commands=0,ports=0;
            for(MethodNode m:c.methods)for(AbstractInsnNode n:m.instructions.toArray()){
                if(m.name.equals("commandLoop")&&n instanceof IntInsnNode&&n.getOpcode()==SIPUSH&&((IntInsnNode)n).operand==7032){m.instructions.set(n,new MethodInsnNode(INVOKESTATIC,"org/omonob/cpmap/ui/ClusterCommandRouter","port","()I",false));ports++;}
                if(m.name.equals("commandFor")&&m.desc.equals("(I)Ljava/lang/String;")&&n.getOpcode()==ARETURN){m.instructions.insertBefore(n,new MethodInsnNode(INVOKESTATIC,"org/omonob/cpmap/ui/ClusterCommandRouter","command","(Ljava/lang/String;)Ljava/lang/String;",false));commands++;}
            }
            require(commands==4&&ports==1);write(c,out);
        }else throw new IllegalArgumentException("Unknown tool operation");
    }
}
