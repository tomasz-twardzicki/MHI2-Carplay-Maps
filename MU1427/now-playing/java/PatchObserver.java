/* SPDX-License-Identifier: GPL-3.0-or-later. Host tool, never installed. */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class PatchObserver implements Opcodes {
    static final String TARGET = "de/vw/mib/asl/internal/carplay/target/HsmTarget";
    static final String HELPER = "com/cpmap/audio/NowPlayingObserver";
    static final String SERVICE = "Lorg/dsi/ifc/carplay/DSICarplay;";
    static void check(boolean value) { if (!value) throw new IllegalStateException("Unexpected factory bytecode"); }

    public static void main(String[] args) throws Exception {
        Path input = Paths.get(args[0]), helpers = Paths.get(args[1]), output = Paths.get(args[2]);
        ClassNode c = new ClassNode();
        new ClassReader(Files.readAllBytes(input)).accept(c, ClassReader.SKIP_FRAMES);
        check(c.name.equals(TARGET) && c.version == V1_5);
        int starts = 0, stops = 0;
        for (MethodNode m : c.methods) {
            if (m.name.equals("initializeDSI") && m.desc.equals("()V")) {
                for (AbstractInsnNode n : m.instructions.toArray()) if (n.getOpcode() == RETURN) {
                    m.instructions.insertBefore(n, hook(m, "start")); starts++;
                }
            }
            if (m.name.equals("deInitializeDSI") && m.desc.equals("()V")) {
                m.instructions.insert(hook(m, "stop")); stops++;
            }
        }
        check(starts == 1 && stops == 1);
        c.version = V1_2;
        write(c, output);
        try (java.util.stream.Stream<Path> paths = Files.walk(helpers)) {
            for (Path p : (Iterable<Path>) paths.filter(p -> p.toString().endsWith(".class"))::iterator) {
                ClassNode helper = new ClassNode();
                new ClassReader(Files.readAllBytes(p)).accept(helper, ClassReader.SKIP_FRAMES);
                check(helper.name.startsWith("com/cpmap/audio/"));
                helper.version = V1_2;
                for (MethodNode m : helper.methods) {
                    m.localVariables = null;
                    for (AbstractInsnNode n : m.instructions.toArray()) {
                        check(!(n instanceof InvokeDynamicInsnNode));
                        if (n instanceof LdcInsnNode) check(!(((LdcInsnNode) n).cst instanceof Type));
                        if (n instanceof MethodInsnNode) {
                            String owner = ((MethodInsnNode) n).owner;
                            check(!owner.equals("java/lang/StringBuilder") && !owner.startsWith("java/nio/"));
                        }
                    }
                }
                write(helper, output);
            }
        }
    }

    static InsnList hook(MethodNode method, String name) {
        InsnList hook = new InsnList();
        LabelNode begin = new LabelNode(), end = new LabelNode();
        LabelNode handler = new LabelNode(), resume = new LabelNode();
        hook.add(begin);
        hook.add(new VarInsnNode(ALOAD, 0));
        hook.add(new FieldInsnNode(GETFIELD, TARGET, "dsiCarplay", SERVICE));
        hook.add(new MethodInsnNode(INVOKESTATIC, HELPER, name, "(" + SERVICE + ")V", false));
        hook.add(end);
        hook.add(new JumpInsnNode(GOTO, resume));
        hook.add(handler);
        hook.add(new InsnNode(POP));
        hook.add(resume);
        // Even a helper linking/initialization failure must leave stock startup running.
        method.tryCatchBlocks.add(new TryCatchBlockNode(begin, end, handler, "java/lang/Throwable"));
        return hook;
    }

    static void write(ClassNode c, Path output) throws Exception {
        ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        c.accept(writer);
        Path dest = output.resolve(c.name + ".class");
        Files.createDirectories(dest.getParent());
        Files.write(dest, writer.toByteArray());
    }
}
