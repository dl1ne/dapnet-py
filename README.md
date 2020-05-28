# dapnet-py

## cli.py
Die zusammenführung der einzelnen Scripte.
Als Konfiguration die notwendigen Zugangsdaten und AX25UDP Parameter definieren:

- Nodecall:   AX25 Node Call
- Nodessid:   AX25 Node SSID

- ax25udp_addr:   Bind vom AX25UDP Helper auf eine IP-Adresse, falls der Digi auf selbigen Host läuft, 
                  reicht hier localhost bzw. 127.0.0.1 aus
- ax25udp_port:   Bind vom AX25UDP Helper auf einem Port

Das Socket ax25udp_addr:ax25udp_port kann später vom Digi oder einem PR-Programm via UDP angesprochen werden.
Zum testen funktioniert hier FlexNet und Paxon ausgezeichnet (für Tests i.d.R. kein 127.0.0.1 nehmen, sondern
ggf. die echte IP-Adresse oder 0.0.0.0).

## ax25udp.py
Komplette Klasse für AX25 via UDP, zur Anbindung von Digipeatern oder Benutzern.
Die Klasse bietet über ".listen" eine Möglichkeit zum Callback, sodass mit Interaktion gearbeitet werden kann.

Die Funktion listen(callback) erwartet von der Callback Funktion die Rückgabewerte: (requestDisconnect/bool, output/string).
- Mit requestDisconnect kann aus der Benutzersitzung die vorhandene AX25 Verbindung getrennt werden
- Mit output kann dem Benutzer eine Ausgabe zugesendet werden (Bsp. nach Eingabe eines Kommandos)

Als Parameter werden an die Callback Funktion die Werte (usercall/string, input/string) übergeben.
- Usercall ist der Verbundene Benutzer aus der AX25 Sitzung
- Input ist eine mögliche Eingabe vom Benutzer

## dapnet.py
Die Klasse vereint einige API-Aufrufe gegen die eigentliche DAPNET-API.
Um Fehlern vorzubeugen, erstellt die Klasse beim ersten Connect eine INI-Datei mit gecachten Informationen (z.B. welche Master-Server es gibt).

## dapnet-cli.py
Gedacht, als reine Helper Klasse für die API, ist die Datei erweitert um die gesamte Interaktion mit dem Benutzer während der AX25 Sitzung. In dieser Klasse werden die Befehle/Kommandos geprüft und ausgeführt und an die dapnet.py übergeben.
