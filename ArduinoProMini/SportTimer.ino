// SixInch Sport Timer - Arduino Pro Mini
// Using FastLED for WS2812B control

// Pin mapping (adjust if needed):
// D3..D6 : jumper binary input (MSB = D3, LSB = D6)
// D7     : WS2812B data
// D8     : Relay output (active HIGH for alarm 2s)
// D9     : Button -1 min
// D10    : Button +1 min
// D11    : Button Start
// D12    : Button Reset

#include <FastLED.h>

#define DEBUG 1

#if DEBUG
// Helper: print time as M:SS with leading zero for seconds
void debugPrintTime(const char* prefix, int totalSec) {
  int m = totalSec / 60;
  int s = totalSec % 60;
  Serial.print(prefix);
  Serial.print(m);
  Serial.print(":");
  if (s < 10) Serial.print('0');
  Serial.println(s);
}
#else
#define debugPrintTime(prefix, totalSec) ((void)0)
#endif


#define LED_PIN     7   // D7
#define RELAY_PIN   8   // D8

// Buttons
#define BTN_MINUS   9   // D9
#define BTN_PLUS    10  // D10
#define BTN_START   11  // D11
#define BTN_RESET   12  // D12

// Jumpers for initial max minute (binary)
// MSB = D3, LSB = D6
#define JUMP_D0     3   // D3 (MSB)
#define JUMP_D1     4   // D4
#define JUMP_D2     5   // D5
#define JUMP_D3     6   // D6 (LSB)

#define NUM_LEDS    282
CRGB leds[NUM_LEDS];

// Layout assumptions:
// Each digit has 7 segments (A..G), each segment has SEG_LEDS LEDs.
// Digit 0 and 1 occupy indices 0..139 (70 leds each).
// Middle two dots at indices DOT_IDX_0=140 and DOT_IDX_1=141
// Digit 2 and 3 occupy indices 142..281 (70 leds each).
const uint8_t SEG_LEDS = 10;
const uint16_t DIGIT_LEDS = 7 * SEG_LEDS; // 70

// Explicit per-segment start indices populated in setup() based on the 7Segment_Design
// segmentStart[digit][segment] gives the first LED index for that segment; each segment covers SEG_LEDS LEDs.
uint16_t segmentStart[4][7];
uint16_t dotIndex[2];

// Segment bit mapping (bit 0 = A, bit1 = B, ... bit6 = G)
const uint8_t SEGMENTS_FOR_DIGIT[10] = {
  // gfedcba bits, but we'll use bit0->A .. bit6->G
  // 0
  (1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<4)|(1<<5),            // 0: A,B,C,D,E,F
  // 1
  (1<<1)|(1<<2),                                         // 1: B,C
  // 2
  (1<<0)|(1<<1)|(1<<6)|(1<<4)|(1<<3),                    // 2: A,B,G,E,D
  // 3
  (1<<0)|(1<<1)|(1<<6)|(1<<2)|(1<<3),                    // 3: A,B,G,C,D
  // 4
  (1<<5)|(1<<6)|(1<<1)|(1<<2),                           // 4: F,G,B,C
  // 5
  (1<<0)|(1<<5)|(1<<6)|(1<<2)|(1<<3),                    // 5: A,F,G,C,D
  // 6
  (1<<0)|(1<<5)|(1<<4)|(1<<3)|(1<<2)|(1<<6),             // 6: A,F,E,D,C,G
  // 7
  (1<<0)|(1<<1)|(1<<2),                                  // 7: A,B,C
  // 8
  (1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<4)|(1<<5)|(1<<6),      // 8: all segments
  // 9
  (1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<5)|(1<<6)              // 9: A,B,C,D,F,G
};

// States
volatile bool running = false;
unsigned long lastSecondTick = 0;
unsigned long lastBlink = 0;
bool dotBlinkState = false;
int maxMinutes = 0;   // configurable 0..99
int currentSeconds = 0; // remaining seconds while running
int displayMinutes = 0; // value shown in waiting mode (when timer isn't running, this is shown as minutes)
uint8_t idleBrightness = 20;
uint8_t runBrightness = 130;

// Button debouncing
unsigned long lastBtnTimeMinus = 0;
unsigned long lastBtnTimePlus = 0;
unsigned long lastBtnTimeStart = 0;
unsigned long lastBtnTimeReset = 0;
const unsigned long DEBOUNCE_MS = 50;

// Relay alarm control
unsigned long alarmOnAt = 0;
const unsigned long ALARM_DURATION_MS = 2000;

// Helper to read jumpers
int readJumpers() {
  // Pins D3..D6 represent bits MSB..LSB respectively (D3 = bit3, D6 = bit0)
  int v = 0;
  v |= (digitalRead(JUMP_D0) == HIGH) ? (1<<3) : 0; // D3 -> bit 3 (MSB)
  v |= (digitalRead(JUMP_D1) == HIGH) ? (1<<2) : 0; // D4 -> bit 2
  v |= (digitalRead(JUMP_D2) == HIGH) ? (1<<1) : 0; // D5 -> bit 1
  v |= (digitalRead(JUMP_D3) == HIGH) ? (1<<0) : 0; // D6 -> bit 0 (LSB)
  return v;
}

// Set a full segment (SEG_LEDS LEDs) for a given digit index (0..3) and segment index (0..6)
void setSegmentLEDs(uint8_t digitIndex, uint8_t segmentIndex, CRGB color) {
  if (digitIndex > 3 || segmentIndex > 6) return;
  uint16_t start = segmentStart[digitIndex][segmentIndex];
  for (uint8_t i = 0; i < SEG_LEDS; ++i) {
    uint16_t idx = start + i;
    if (idx < NUM_LEDS) leds[idx] = color;
  }
}

// Clears all LEDs
void clearAll() {
  for (int i=0;i<NUM_LEDS;i++) leds[i] = CRGB::Black;
}

// Clears all LEDs
void clearAll() {
  for (int i=0;i<NUM_LEDS;i++) leds[i] = CRGB::Black;
}

void showDigit(uint8_t digitIndex, uint8_t value, CRGB color) {
  uint8_t segMask = SEGMENTS_FOR_DIGIT[value];
  for (uint8_t s=0; s<7; ++s) {
    if (segMask & (1<<s)) {
      setSegmentLEDs(digitIndex, s, color);
    } else {
      setSegmentLEDs(digitIndex, s, CRGB::Black);
    }
  }
}

void setDots(CRGB color, bool on) {
  if (dotIndex[0] < NUM_LEDS) leds[dotIndex[0]] = on ? color : CRGB::Black;
  if (dotIndex[1] < NUM_LEDS) leds[dotIndex[1]] = on ? color : CRGB::Black;
}

void displayTime(int totalSeconds, CRGB digitColor, bool dotsOn) {
  if (totalSeconds < 0) totalSeconds = 0;
  int minutes = totalSeconds / 60;
  int seconds = totalSeconds % 60;

  int d0 = (minutes / 10) % 10;
  int d1 = minutes % 10;
  int d2 = (seconds / 10) % 10;
  int d3 = seconds % 10;

  showDigit(0, d0, digitColor);
  showDigit(1, d1, digitColor);
  showDigit(2, d2, digitColor);
  showDigit(3, d3, digitColor);

  setDots(CRGB::Red, dotsOn); // caller may override color by writing again if needed
}

void applyShow(uint8_t brightness) {
  FastLED.setBrightness(brightness);
  FastLED.show();
}

void setupPins() {
  pinMode(JUMP_D0, INPUT_PULLUP);
  pinMode(JUMP_D1, INPUT_PULLUP);
  pinMode(JUMP_D2, INPUT_PULLUP);
  pinMode(JUMP_D3, INPUT_PULLUP);

  pinMode(BTN_MINUS, INPUT_PULLUP);
  pinMode(BTN_PLUS, INPUT_PULLUP);
  pinMode(BTN_START, INPUT_PULLUP);
  pinMode(BTN_RESET, INPUT_PULLUP);

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // relay off
}

void setup() {
  setupPins();
  FastLED.addLeds<NEOPIXEL, LED_PIN>(leds, NUM_LEDS);

  // Serial debug init when enabled
  #if DEBUG
  Serial.begin(115200);
  delay(50);
  Serial.println("SportTimer starting");
  #endif

  // Build explicit per-segment mapping based on 7Segment_Design.txt
  // New layout: dots are the last two LEDs; digits 2 & 3 moved earlier.
  // Digit0 segments A..G: indices 0 .. 69
  // Digit1 segments A..G: indices 70 .. 139
  // Digit2 segments A..G: indices 140 .. 209
  // Digit3 segments A..G: indices 210 .. 279
  // Dot0: 280, Dot1: 281
  uint16_t base0 = 0;
  uint16_t base1 = base0 + DIGIT_LEDS; // 70
  uint16_t base2 = base1 + DIGIT_LEDS; // 140
  uint16_t base3 = base2 + DIGIT_LEDS; // 210
  uint16_t baseDot0 = base3 + DIGIT_LEDS; // 280
  uint16_t baseDot1 = baseDot0 + 1; // 281

  // populate segmentStart[digit][segment]
  for (uint8_t s = 0; s < 7; ++s) {
    segmentStart[0][s] = base0 + s * SEG_LEDS;
    segmentStart[1][s] = base1 + s * SEG_LEDS;
    segmentStart[2][s] = base2 + s * SEG_LEDS;
    segmentStart[3][s] = base3 + s * SEG_LEDS;
  }
  dotIndex[0] = baseDot0;
  dotIndex[1] = baseDot1;

  FastLED.clear(true);

  // Read jumpers (active HIGH = present)
  int jumperValue = readJumpers();
  // Use jumperValue as initial max minutes; allow up to at least 15 by 4 jumpers
  maxMinutes = jumperValue;
  if (maxMinutes < 0) maxMinutes = 0;
  if (maxMinutes > 99) maxMinutes = 99;

  #if DEBUG
  Serial.print("Selected Timer Max (minutes): ");
  Serial.println(maxMinutes);
  #endif

  displayMinutes = 0;
  currentSeconds = 0;
  running = false;
  lastSecondTick = millis();
  lastBlink = millis();

  // Idle startup display: 0:00 in green, brightness 20, middle dots flash red every 500ms
  clearAll();
  displayTime(0, CRGB::Green, false);
  setDots(CRGB::Red, true);
  applyShow(idleBrightness);
}

bool readButtonDebounced(uint8_t pin, unsigned long &lastTimeRef) {
  bool pressed = (digitalRead(pin) == LOW);
  unsigned long now = millis();
  if (pressed) {
    if (now - lastTimeRef > DEBOUNCE_MS) {
      lastTimeRef = now;
      return true;
    }
  }
  return false;
}

void doPlus() {
  if (running) {
    // increase remaining time by 60 seconds
    currentSeconds += 60;
    if (currentSeconds > 99 * 60 + 59) currentSeconds = 99 * 60 + 59;
  } else {
    // increase max minutes
    if (maxMinutes < 99) maxMinutes++;
    displayMinutes = maxMinutes;
  }
}

void doMinus() {
  if (running) {
    // decrease remaining time by 60s, not below 0
    currentSeconds -= 60;
    if (currentSeconds < 0) currentSeconds = 0;
  } else {
    if (maxMinutes > 0) maxMinutes--;
    displayMinutes = maxMinutes;
  }
}

void startTimer() {
  // Start countdown from current max
  running = true;
  currentSeconds = maxMinutes * 60;
  lastSecondTick = millis();
}

void resetTimer() {
  running = false;
  currentSeconds = 0;
  displayMinutes = 0;
  // ensure relay off
  digitalWrite(RELAY_PIN, LOW);
}

void setAllDigitsColor(CRGB color) {
  // Utility: redraw digits in color using last known time values
  int totalSeconds = running ? currentSeconds : (displayMinutes * 60);
  displayTime(totalSeconds, color, dotBlinkState);
}

void loop() {
  unsigned long now = millis();

  // Buttons handling
  if (readButtonDebounced(BTN_PLUS, lastBtnTimePlus)) {
    #if DEBUG
    Serial.println("Button + pressed");
    #endif
    doPlus();
    #if DEBUG
    if (running) debugPrintTime("Remaining after +: ", currentSeconds);
    else Serial.print("Max minutes after +: "), Serial.println(maxMinutes);
    #endif
  }
  if (readButtonDebounced(BTN_MINUS, lastBtnTimeMinus)) {
    #if DEBUG
    Serial.println("Button - pressed");
    #endif
    doMinus();
    #if DEBUG
    if (running) debugPrintTime("Remaining after -: ", currentSeconds);
    else Serial.print("Max minutes after -: "), Serial.println(maxMinutes);
    #endif
  }
  if (readButtonDebounced(BTN_START, lastBtnTimeStart)) {
    #if DEBUG
    Serial.println("Button Start pressed");
    #endif
    if (!running) {
      startTimer();
      #if DEBUG
      debugPrintTime("Timer started: ", currentSeconds);
      #endif
    } else {
      // If already running, treat as pause? The user didn't request pause; ignore or restart.
      // Here we'll ignore repeated starts when running.
      #if DEBUG
      Serial.println("Start pressed while running - ignored");
      #endif
    }
  }
  if (readButtonDebounced(BTN_RESET, lastBtnTimeReset)) {
    #if DEBUG
    Serial.println("Button Reset pressed");
    #endif
    resetTimer();
    #if DEBUG
    Serial.println("Timer reset to 0:00");
    #endif
  }

  // Update countdown every 1000ms when running
  if (running && (now - lastSecondTick >= 1000)) {
    lastSecondTick += 1000;
    if (currentSeconds > 0) {
      currentSeconds--;
    }
    #if DEBUG
    debugPrintTime("Time left: ", currentSeconds);
    #endif
    if (currentSeconds <= 0) {
      // Timer expired
      currentSeconds = 0;
      running = false;

      // Activate relay for ALARM_DURATION_MS
      digitalWrite(RELAY_PIN, HIGH);
      alarmOnAt = now;
      #if DEBUG
      Serial.println("Timer expired - activating relay");
      #endif
    }
  }

  // Turn off relay after alarm duration
  if (alarmOnAt != 0 && (now - alarmOnAt >= ALARM_DURATION_MS)) {
    digitalWrite(RELAY_PIN, LOW);
    alarmOnAt = 0;
    #if DEBUG
    Serial.println("Alarm off (relay deactivated)");
    #endif
  }

  // Dots blink handling (idle blink every 500ms)
  if (!running) {
    if (now - lastBlink >= 500) {
      lastBlink = now;
      dotBlinkState = !dotBlinkState;
    }
  } else {
    // when running: In last minute, dots are solid green; otherwise solid red? Requirement:
    // "During running show digits in green bright 130. In the last min digits change to red bright and the 2 dots change to green."
    // We'll implement:
    // - Running and > 60s: digits green, dots solid red
    // - Running and <= 60s: digits red, dots solid green
    dotBlinkState = true; // leave them on; color will change depending on time remaining
  }

  // Prepare display based on state
  if (!running) {
    // Idle/waiting display: show 0:00 in green (but show displayMinutes as minutes), brightness 20, dots blinking red
    clearAll();
    int totalSec = displayMinutes * 60;
    displayTime(totalSec, CRGB::Green, dotBlinkState);
    // If dotBlinkState true, dots were set to Red by displayTime. If false, they were set off
    applyShow(idleBrightness);
  } else {
    // Running display
    bool lastMinute = (currentSeconds <= 60);
    clearAll();
    if (!lastMinute) {
      // digits green, brightness 130, dots red (solid)
      displayTime(currentSeconds, CRGB::Green, true);
      // override dots color to red
      setDots(CRGB::Red, true);
      applyShow(runBrightness);
    } else {
      // last minute: digits red, dots green, brightness 130
      displayTime(currentSeconds, CRGB::Red, true);
      setDots(CRGB::Green, true);
      applyShow(runBrightness);
    }
  }

  // Small delay to avoid hammering CPU
  delay(10);
}
