import java.io.*;
import java.net.*;
import java.util.*;
import java.nio.charset.StandardCharsets;

import org.dreambot.api.methods.container.impl.Inventory;
import org.dreambot.api.methods.container.impl.bank.Bank;
import org.dreambot.api.methods.widget.Widgets;
import org.dreambot.api.script.AbstractScript;
import org.dreambot.api.script.Category;
import org.dreambot.api.script.ScriptManifest;
import org.dreambot.api.methods.grandexchange.GrandExchange;
import org.dreambot.api.utilities.Logger;
import org.dreambot.api.utilities.Sleep;
import org.dreambot.api.wrappers.items.Item;
import org.dreambot.api.wrappers.widgets.WidgetChild;

@ScriptManifest(name = "Moneyprinter", description = "Its raining cash!", author = "WilliamQM",
        version = 1.0, category = Category.MONEYMAKING, image = "")

public class Moneyprinter extends AbstractScript {
    boolean connected = false;
    int slot_count = 0;
    ArrayList<WidgetChild[]> slot_widgets = new ArrayList<>();
    ArrayList<String[]> queue = new ArrayList<>();

    public Socket s = null;
    public DataInputStream in = null;
    public DataOutputStream out = null;

    public String recieveData() {
        try {
            int length = in.readUnsignedShort();
            byte[] data = new byte[length];
            in.readFully(data);
            return new String(data, StandardCharsets.UTF_8);
        } catch (IOException i) {
            Logger.log(i);
        }
        return null;
    }

    public Socket connectToServer() {
        try {
            s = new Socket("127.0.0.1", 12856);
            in = new DataInputStream(s.getInputStream());
            out = new DataOutputStream(s.getOutputStream());
        }
        catch (IOException i) {
            Logger.log(i);
        }

        return s;
    }

    @Override
    public int onLoop() {
        if (!connected) {
            GrandExchange.open();
//            GrandExchange.cancelAll();
//            sleep(100);
//            GrandExchange.collectToBank();
//            Bank.open();
//            Bank.depositAllItems();
//            Bank.withdrawAll("Coins");

            for (int i = 7; i <= 14; i++) {
                WidgetChild[] slot = {Widgets.getWidgetChild(465, i, 0), Widgets.getWidgetChild(465, i, 1), Widgets.getWidgetChild(465, i)};
                slot_widgets.add(slot);
            }

            s = connectToServer();
            connected = (s != null);
            try {
                int gp = Inventory.get(995).getAmount();
                slot_count = GrandExchange.getOpenSlots();

                out.writeUTF(String.format(" %d %d", gp, slot_count));
            } catch (IOException e) {
                Logger.log("EROR CONNECTING");
            }

            Thread serverListener = new Thread(() -> {
                while (connected) {
                    String command = recieveData();
                    if (command != null) {
                        String[] data = command.split(" ");
                        queue.add(data);
                    }
                }
            });
            serverListener.start();
        }
        else if (GrandExchange.isOpen()) {
            if (GrandExchange.isReadyToCollect()) {
                sleep(100);
                for (int i = 0; i < slot_count; i++) {
                    if (GrandExchange.isReadyToCollect(i)) {
                        try {
                            out.writeUTF(String.format(" collected %d", i));
                        } catch (IOException e) {
                            Logger.log("ERROR OUTPUTTING");
                        }
                    }
                }
                int gp = Inventory.get(995).getAmount();
                try {
                    out.writeUTF(String.format(" gp %d", gp));
                } catch (IOException e) {
                    Logger.log("Errorrrrrr");
                }
                GrandExchange.collect();
            }

            ArrayList<String[]> queue_cache = new ArrayList<>(queue);
            queue.clear();
            for (String[] data : queue_cache) {
                switch (data[0]) {
                    case "buy" -> {
                        int slot = Integer.parseInt(data[4]);
                        int item_id = Integer.parseInt(data[2]);

                        sleep(1000);
                        slot_widgets.get(slot)[0].interact();
                        sleep(2000);
                        if (GrandExchange.isBuyOpen()) {
                            GrandExchange.buyItem(item_id, Integer.parseInt(data[1]), Integer.parseInt(data[3]));
                        } else {
                            Logger.log("BUY NOT OPEN");
                        }
                    }
                    case "sell" -> {
                        int slot = Integer.parseInt(data[4]);
                        int item_id = Integer.parseInt(data[2]);

                        sleep(1000);
                        slot_widgets.get(slot)[1].interact();
                        sleep(2000);
                        if (GrandExchange.isSellOpen()) {
                            GrandExchange.sellItem(item_id, Integer.parseInt(data[1]), Integer.parseInt(data[3]));
                        } else {
                            Logger.log("SELL NOT OPEN");
                        }
                    }
                    case "cancel" -> {
                        String which = data[1];
                        int slot = Integer.parseInt(data[2]);

                        sleep(1000);
                        slot_widgets.get(slot)[2].interact();
                        sleep(2000);
                        Widgets.getWidgetChild(465, 23, 0).interact();
                        sleep(1000);
                        Widgets.getWidgetChild(465, 24, 0).interact();
                        sleep(1000);
                        Widgets.getWidgetChild(465, 24, 1).interact();

                        if (which.equals("sell")) {
                            try {
                                out.writeUTF(String.format(" collected %d", slot));
                            } catch (IOException e) {
                                Logger.log("Error sending");
                            }
                        }

                        sleep(1000);
                        int gp = Inventory.get(995).getAmount();
                        try {
                            out.writeUTF(String.format(" gp %d", gp));
                        } catch (IOException e) {
                            Logger.log("Errorrrrrr");
                        }

                        if (which.equals("buy")) {
                            try {
                                out.writeUTF(String.format(" canceled %d", slot));
                            } catch (IOException e) {
                                Logger.log("Error sending");
                            }
                        }
                    }
                }
            }
        } else {
            GrandExchange.open();
        }
        return 1000;
    }
}