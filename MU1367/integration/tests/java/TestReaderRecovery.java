/* Host/QNX probe for the actual unchanged MU1367 bridge. Never installed. */
package com.cpmap.rgi;
import java.io.*;
public final class TestReaderRecovery {
    public static void main(String[] args) throws Exception {
        TestLive.installMocks();
        LiveBridge bridge=TestLive.bridge();
        FeedRecovery feed=new FeedRecovery(args[0]);
        BufferedReader in=new BufferedReader(new InputStreamReader(System.in));
        String line;
        while((line=in.readLine())!=null) {
            long now=Long.parseLong(line); TestLive.clock=now;
            bridge.pollProduction(feed,now,false); bridge.tick(now);
            System.out.println((bridge.owned?1:0)+","+feed.errors+","+feed.reader.instance+","+feed.reader.serial);
            System.out.flush();
        }
    }
}
