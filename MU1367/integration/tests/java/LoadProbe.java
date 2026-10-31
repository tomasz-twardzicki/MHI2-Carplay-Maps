/* SPDX-License-Identifier: GPL-3.0-or-later
 * Standalone firmware-J9 test, not an HMI startup hook. No output publishing.
 */
public final class LoadProbe {
    public static void main(String[] args) {
        if (args.length>0 && args[0].equals("mailbox")) {
            try {
                Class readerType=Class.forName("com.cpmap.rgi.MailboxReader");
                Object reader=readerType.getConstructor(new Class[]{Class.forName("java.lang.String")})
                    .newInstance(new Object[]{"/ramdisk/rgi-live/latest.bin"});
                java.lang.reflect.Method next=readerType.getMethod("next",new Class[]{Long.TYPE});
                boolean baseline=false, progress=false;
                for (int i=0;i<40;i++) {
                    Object frame=next.invoke(reader,new Object[]{new Long(System.currentTimeMillis())});
                    if (frame!=null) {
                        Class type=frame.getClass();
                        boolean active=type.getField("active").getBoolean(frame);
                        if (!baseline) {
                            if (active) throw new Exception("old mailbox replayed as live");
                            baseline=true;
                        } else if (active) {
                            if (type.getField("remainingMeters").getInt(frame)!=1000 ||
                                type.getField("remainingSeconds").getInt(frame)!=120)
                                throw new Exception("synthetic route totals mismatch");
                            progress=true; break;
                        }
                    }
                    Thread.sleep(100);
                }
                if (!baseline || !progress) throw new Exception("mailbox baseline/progress missing");
                System.out.println("RGI_MAILBOX_PASS baseline_and_fresh_route_totals");
            } catch (Throwable t) { t.printStackTrace(); System.exit(1); }
            return;
        }
        String prefix="de.vw.mib.bap.mqbab2.navsd.functions.";
        String[] names={"ManeuverDescriptor","DistanceToNextManeuver","RGStatus","LaneGuidance","DistanceToDestination","TimeToDestination"};
        int passed=0, failed=0;
        for (int i=0;i<names.length;i++) {
            try {
                Class.forName(prefix.concat(names[i])).newInstance(); passed++;
                System.out.print("RGI_LOAD_OK "); System.out.println(names[i]);
            } catch (Throwable t) { failed++; t.printStackTrace(); }
        }
        if (args.length>0 && !args[0].equals("stock")) {
            try {
                Class helper=Class.forName("com.cpmap.rgi.LiveBridge");
                String base="de.vw.mib.bap.mqbab2.generated.navsd.serializer.";
                String[] types={"ManeuverDescriptor_Status","DistanceToNextManeuver_Status","RG_Status_Status","LaneGuidance_ChangedArray","DistanceToDestination_Status","TimeToDestination_Status"};
                String[] methods={"descriptor","distance","route","lanes","destinationDistance","destinationTime"};
                for (int i=0;i<types.length;i++) {
                    Class type=Class.forName(base.concat(types[i]));
                    Boolean result=(Boolean)helper.getMethod(methods[i],new Class[]{type}).invoke(null,new Object[]{type.newInstance()});
                    if (result.booleanValue()) throw new Exception("unexpected takeover without enable/context");
                    passed++;
                }
                // Exercise Function virtual-method resolution in registration,
                // one stage at a time so no timer or background thread starts.
                Class function=Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.Function");
                java.lang.reflect.Field instance=helper.getDeclaredField("INSTANCE"); instance.setAccessible(true);
                java.lang.reflect.Field failures=helper.getDeclaredField("failures"); failures.setAccessible(true);
                for (int i=0;i<names.length;i++) {
                    Object stage=Class.forName(prefix.concat(names[i])).newInstance();
                    helper.getMethod("attach",new Class[]{function}).invoke(null,new Object[]{stage});
                    helper.getMethod("detach",new Class[]{function}).invoke(null,new Object[]{stage});
                }
                if (failures.getLong(instance.get(null))!=0) throw new Exception("stage registration failure");
                passed++;
            } catch (Throwable t) { failed++; t.printStackTrace(); }
        }
        StringBuffer s=new StringBuffer("RGI_J9_PROBE passed=");s.append(passed).append(" failed=").append(failed);
        System.out.println(s.toString());
        if (failed!=0) System.exit(1);
    }
}
