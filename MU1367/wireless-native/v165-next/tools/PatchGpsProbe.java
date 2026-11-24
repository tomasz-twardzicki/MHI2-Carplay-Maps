/* SPDX-License-Identifier: GPL-3.0-or-later. Host only. */
import java.nio.file.*;
import java.security.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
public final class PatchGpsProbe implements Opcodes {
    static void check(boolean v){if(!v)throw new IllegalStateException("GPS probe factory contract");}
    static String hash(byte[] b)throws Exception{
        byte[] d=MessageDigest.getInstance("SHA-256").digest(b);StringBuilder s=new StringBuilder();
        for(byte v:d)s.append(String.format("%02x",v&255));return s.toString();
    }
    static void hook(ClassNode c,String name,String desc,String helper){
        int hits=0;
        for(MethodNode m:c.methods)if(m.name.equals(name)&&m.desc.equals(desc)){
            check((m.access&(ACC_STATIC|ACC_NATIVE|ACC_ABSTRACT))==0);
            InsnList code=new InsnList();code.add(new VarInsnNode(desc.charAt(1)=='L'?ALOAD:ILOAD,1));code.add(new VarInsnNode(ILOAD,2));
            code.add(new VarInsnNode(ALOAD,0));code.add(new FieldInsnNode(GETFIELD,"de/esolutions/fw/dsi/base/AbstractDispatcher","instance","I"));
            code.add(new MethodInsnNode(INVOKESTATIC,"com/cpmap/rgi/GpsProbe",helper,desc.substring(0,desc.length()-2)+"I)V",false));
            m.instructions.insert(code);hits++;
        }
        check(hits==1);
    }
    public static void main(String[] a)throws Exception{
        check(a.length==4);byte[] raw=Files.readAllBytes(Paths.get(a[0]));check(hash(raw).equals(a[2]));
        ClassNode c=new ClassNode();new ClassReader(raw).accept(c,0);check(c.version==V1_5);c.version=V1_2;
        if(a[3].equals("navigation")){
            check(c.name.equals("de/esolutions/fw/dsi/navigation/DSINavigationDispatcher"));
            hook(c,"updateSoPosPosition","(Lorg/dsi/ifc/navigation/PosPosition;I)V","position");
            hook(c,"updateEtcDemoModeState","(ZI)V","demo");
        }else{
            check(a[3].equals("clock")&&c.name.equals("de/esolutions/fw/dsi/cartimeunitslanguage/DSICarTimeUnitsLanguageDispatcher"));
            hook(c,"updateClockGPSSyncData","(Lorg/dsi/ifc/cartimeunitslanguage/ClockGPSSyncData;I)V","clock");
            hook(c,"updateClockSource","(II)V","source");
        }
        for(MethodNode m:c.methods)for(AbstractInsnNode n:m.instructions.toArray()){
            check(!(n instanceof InvokeDynamicInsnNode));
            if(n instanceof LdcInsnNode)check(!(((LdcInsnNode)n).cst instanceof Type));
            if(n instanceof MethodInsnNode)check(!((MethodInsnNode)n).owner.equals("java/lang/StringBuilder"));
        }
        ClassWriter w=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(w);Files.createDirectories(Paths.get(a[1]).getParent());Files.write(Paths.get(a[1]),w.toByteArray());
    }
}
