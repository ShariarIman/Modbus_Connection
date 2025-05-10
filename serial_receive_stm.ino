void setup() {
  Serial.begin(115200); // Debug Serial (USB)
  Serial1.begin(9600);  // UART1 (pins are fixed: PB7=RX1, PB6=TX1)
}

void loop() {
  if (Serial1.available()) {
    String receivedData = Serial1.readStringUntil('\n');
    Serial.println("Received from ESP32: " + receivedData);

    // Optionally reply
    Serial1.println("ACK: " + receivedData);
  }
}


