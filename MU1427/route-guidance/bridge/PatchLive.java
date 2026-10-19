/* SPDX-License-Identifier: GPL-3.0-or-later. Host build tool, never installed. */
import java.nio.file.*;
import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class PatchLive implements Opcodes {
    static final String BASE="de/vw/mib/bap/mqbab2/navsd/functions/";
    static final String HELPER="com/cpmap/rgi/LiveBridge";
    static final String FUNCTION="de/vw/mib/bap/mqbab2/common/api/stages/Function";
    static void check(boolean ok) { if (!ok) throw new IllegalStateException("Unexpected factory bytecode"); }
    static MethodNode method(ClassNode c,String name) {
        MethodNode result=null;
        for (MethodNode m:c.methods) if (m.name.equals(name)) { check(result==null); result=m; }
        check(result!=null); return result;
    }
    public static void main(String[] args) throws Exception {
        Path stock=Paths.get(args[0]), helpers=Paths.get(args[1]), output=Paths.get(args[2]);
        String[] classes={"ManeuverDescriptor","DistanceToNextManeuver","RGStatus","LaneGuidance","DistanceToDestination","TimeToDestination"};
        String[] methods={"fillManeuverDescriptor","setDistanceToNextManeuverStatusData","setRouteGuidanceStatus","computeFullLaneGuidanceList","setDistanceAndUnit","setTimeInfo"};
        String[] hooks={"descriptor","distance","route","lanes","destinationDistance","destinationTime"};
        for (int i=0;i<classes.length;i++) {
            String name=BASE+classes[i]; ClassNode c=new ClassNode();
            new ClassReader(Files.readAllBytes(stock.resolve(name+".class"))).accept(c,ClassReader.SKIP_FRAMES);
            check(c.version==V1_5); // pinned converter output; NOT the unit VM target
            c.version=V1_2; // firmware J9 rejects version 49; installed NAI uses 46
            MethodNode fill=method(c,methods[i]); check(fill.desc.endsWith(")V") && (fill.access&ACC_PRIVATE)!=0);
            InsnList hook=new InsnList(); LabelNode original=new LabelNode();
            hook.add(new VarInsnNode(ALOAD,1)); hook.add(new MethodInsnNode(INVOKESTATIC,HELPER,hooks[i],fill.desc.replace(")V",")Z"),false));
            hook.add(new JumpInsnNode(IFEQ,original)); hook.add(new InsnNode(RETURN)); hook.add(original);
            fill.instructions.insert(hook);
            if (i==4) {
                MethodNode validity=method(c,"setValidityInformation");
                InsnList guard=new InsnList(); LabelNode normal=new LabelNode();
                guard.add(new VarInsnNode(ALOAD,1));
                guard.add(new MethodInsnNode(INVOKESTATIC,HELPER,"destinationValidity",validity.desc.replace(")V",")Z"),false));
                guard.add(new JumpInsnNode(IFEQ,normal)); guard.add(new InsnNode(RETURN)); guard.add(normal);
                validity.instructions.insert(guard);
            }
            MethodNode init=method(c,"init"); int returns=0;
            for (AbstractInsnNode n:init.instructions.toArray()) if (n.getOpcode()==ARETURN) {
                InsnList register=new InsnList(); register.add(new VarInsnNode(ALOAD,0));
                register.add(new MethodInsnNode(INVOKESTATIC,HELPER,"attach","(L"+FUNCTION+";)V",false));
                init.instructions.insertBefore(n,register); returns++;
            }
            check(returns==1);
            if (i==0) {
                int gates=0;
                for (AbstractInsnNode n:method(c,"computeManeuverDescriptorStatus").instructions.toArray()) if (n instanceof MethodInsnNode) {
                    MethodInsnNode call=(MethodInsnNode)n;
                    if (call.name.equals("getRouteGuidanceState")) {
                        check(call.owner.equals("de/vw/mib/bap/mqbab2/common/api/navigation/NavigationService"));
                        call.setOpcode(INVOKESTATIC); call.owner=HELPER; call.name="descriptorRouteState";
                        call.desc="(Lde/vw/mib/bap/mqbab2/common/api/navigation/NavigationService;)I"; call.itf=false; gates++;
                    }
                }
                check(gates==1);
            }
            MethodNode uninit=method(c,"uninitialize"); InsnList detach=new InsnList();
            detach.add(new VarInsnNode(ALOAD,0)); detach.add(new MethodInsnNode(INVOKESTATIC,HELPER,"detach","(L"+FUNCTION+";)V",false));
            uninit.instructions.insert(detach);
            int accepts=0;
            for (MethodNode m:c.methods) for (AbstractInsnNode n:m.instructions.toArray()) if (n instanceof MethodInsnNode) {
                MethodInsnNode call=(MethodInsnNode)n;
                if (call.owner.equals("de/vw/mib/bap/functions/PropertyListener") && call.name.equals("statusProperty")) {
                    check(i!=3 && call.desc.equals("(Lde/vw/mib/bap/datatypes/BAPEntity;Lde/vw/mib/bap/functions/Property;)Z"));
                    InsnList accept=new InsnList(); accept.add(new VarInsnNode(ALOAD,0));
                    accept.add(new MethodInsnNode(INVOKESTATIC,HELPER,"accepted","(ZL"+FUNCTION+";)Z",false));
                    m.instructions.insert(call,accept); accepts++;
                }
            }
            check(accepts==(i!=3?1:0)); write(c,output);
        }
        // Java 1.2 / CDC compatible bytecode. Reject silently introduced newer
        // language/runtime dependencies instead of just changing class version.
        final ArrayList<Path> files=new ArrayList<Path>();
        Files.walk(helpers).filter(p->p.toString().endsWith(".class")).forEach(files::add);
        for (Path p:files) {
            ClassNode c=new ClassNode(); new ClassReader(Files.readAllBytes(p)).accept(c,ClassReader.SKIP_FRAMES);
            check(c.name.startsWith("com/cpmap/rgi/")); c.version=V1_2;
            for (MethodNode m:c.methods) {
                m.localVariables=null;
                for (AbstractInsnNode n:m.instructions.toArray()) {
                    check(!(n instanceof InvokeDynamicInsnNode));
                    if (n instanceof LdcInsnNode) check(!(((LdcInsnNode)n).cst instanceof Type));
                    if (n instanceof MethodInsnNode) {
                        MethodInsnNode call=(MethodInsnNode)n;
                        check(!call.owner.equals("java/lang/StringBuilder") && !call.owner.startsWith("java/nio/"));
                    }
                }
            }
            write(c,output);
        }
        System.out.println("D3: all six replacements and all helpers target class 46");
    }
    static void write(ClassNode c,Path output) throws Exception {
        check(c.version==V1_2);
        ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS); c.accept(writer);
        Path p=output.resolve(c.name+".class"); Files.createDirectories(p.getParent()); Files.write(p,writer.toByteArray());
    }
}
