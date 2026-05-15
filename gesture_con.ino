const int LED1 = 9;
const int LED2 = 10;
const int LED3 = 11;

void setup() {
  Serial.begin(9600);
  pinMode(LED1, OUTPUT);
  pinMode(LED2, OUTPUT);
  pinMode(LED3, OUTPUT);
  digitalWrite(LED1, LOW);
  digitalWrite(LED2, LOW);
  digitalWrite(LED3, LOW);
  
  // Startup confirmation
  delay(100);
  Serial.println("ARDUINO_READY");
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    int fingers = input.toInt();

    digitalWrite(LED1, fingers >= 1 ? HIGH : LOW);
    digitalWrite(LED2, fingers >= 2 ? HIGH : LOW);
    digitalWrite(LED3, fingers >= 3 ? HIGH : LOW);

    Serial.println("OK:" + String(fingers));
  }
}