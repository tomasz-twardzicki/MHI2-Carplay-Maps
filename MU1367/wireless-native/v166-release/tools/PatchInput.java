/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public final class PatchInput implements Opcodes {
    private static ClassNode read(String path) throws Exception {
        ClassNode c = new ClassNode();
        new ClassReader(Files.readAllBytes(Paths.get(path))).accept(c, ClassReader.SKIP_FRAMES);
        return c;
    }
    private static void write(ClassNode c, String path) throws Exception {
        c.version = V1_2;
        ClassWriter w = new ClassWriter(ClassWriter.COMPUTE_MAXS); c.accept(w);
        Files.write(Paths.get(path), w.toByteArray());
    }
    public static void main(String[] a) throws Exception {
        if (a[0].equals("touch")) {
            ClassNode original = read(a[1]), patched = read(a[2]);
            String name = "updateTouchInput", desc = "(IIIIIII)V";
            if (!original.name.equals(patched.name) || !patched.name.equals("de/vw/mib/asl/internal/system/input/TouchInputDeviceImpl")) throw new Exception("Touch class mismatch");
            MethodNode body = null; int replacements = 0;
            for (MethodNode m : original.methods) if (m.name.equals(name) && m.desc.equals(desc)) body = m;
            if (body == null) throw new Exception("Factory touch method missing");
            for (int i = 0; i < patched.methods.size(); i++) {
                MethodNode m = patched.methods.get(i);
                if (m.name.equals(name) && m.desc.equals(desc)) { patched.methods.set(i, body); replacements++; }
            }
            if (replacements != 1) throw new Exception("Touch method count");
            write(patched, a[3]);
        } else if (a[0].equals("cp")) {
            ClassNode c = read(a[1]); String owner = "de/vw/mib/asl/internal/wcpcp/WcpCp";
            if (!c.name.equals(owner)) throw new Exception("CP class mismatch");
            int count = 0;
            for (MethodNode m : c.methods) if (m.name.equals("onServiceCall") && m.desc.equals("(Ljava/lang/String;[Ljava/lang/Object;)V")) {
                LabelNode done = new LabelNode(), inactive = new LabelNode(), ready = new LabelNode();
                InsnList h = new InsnList();
                h.add(new LdcInsnNode("postTouchEvent")); h.add(new VarInsnNode(ALOAD, 0));
                h.add(new MethodInsnNode(INVOKEVIRTUAL, "java/lang/String", "equals", "(Ljava/lang/Object;)Z", false));
                h.add(new JumpInsnNode(IFEQ, done)); h.add(new VarInsnNode(ALOAD, 1));
                h.add(new FieldInsnNode(GETSTATIC, owner, "stage", "I")); h.add(new InsnNode(ICONST_3));
                h.add(new JumpInsnNode(IF_ICMPLT, inactive));
                h.add(new FieldInsnNode(GETSTATIC, owner, "weRegistered", "Z")); h.add(new JumpInsnNode(IFEQ, inactive));
                h.add(new MethodInsnNode(INVOKESTATIC, owner, "sessionFresh", "()Z", false)); h.add(new JumpInsnNode(GOTO, ready));
                h.add(inactive); h.add(new InsnNode(ICONST_0)); h.add(ready);
                h.add(new MethodInsnNode(INVOKESTATIC, "de/vw/mib/asl/internal/wcpcp/RoutedTouch", "forward", "([Ljava/lang/Object;Z)Z", false));
                // All touchscreen requests are handled here, including rejected
                // ones. They never fall back to the global raw-input hook.
                h.add(new InsnNode(POP)); h.add(new InsnNode(RETURN)); h.add(done);
                m.instructions.insert(h); count++;
            }
            if (count != 1) throw new Exception("CP method count");
            write(c, a[2]);
        } else if (a[0].equals("helper")) {
            write(read(a[1]), a[2]);
        } else throw new Exception("Invalid action");
    }
}
