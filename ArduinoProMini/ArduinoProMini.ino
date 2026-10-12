// -------------------------------------------------------
// Author: Simon Yuen (simonyuen1999@hotmail.com)
// Date:   2026-Oct-10
// AI:     Use VSC IDE (on Windows) -> GitHub (Copilot) -> use GPT-5 mini (Context window: Medium - 264K)
// Copyright: Free to use and modify.  You are welcomed to use my name as reference.
// -------------------------------------------------------

// -------------------------------------------------------
// SixInch Sport Timer - Arduino Pro Mini
// Using FastLED for WS2812B control (282 LED)

// Pin mapping (adjust if needed):
// D3..D6 : jumper binary input (MSB = D3, LSB = D6)
// D7     : WS2812B data
// D8     : Relay output (active HIGH for alarm 2s)
// D9     : Button -1 min
// D10    : Button +1 min
// D11    : Button Start
// D12    : Button Reset

#include <FastLED.h>

// Note: After the initial development, I removed the most DEBUG statements.
#define DEBUG 0

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
  // Using hardware-provided segment definitions (A..G mapped to bits 0..6)
  // 0: A,B,C,D,E,F
  (1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<4)|(1<<5),
  // 1: A,F
  (1<<0)|(1<<5),
  // 2: B,A,G,D,E
  (1<<0)|(1<<1)|(1<<6)|(1<<3)|(1<<4),
  // 3: B,A,G,F,E
  (1<<0)|(1<<1)|(1<<6)|(1<<5)|(1<<4),
  // 4: C,G,A,F
  (1<<0)|(1<<2)|(1<<6)|(1<<5),
  // 5: B,C,G,F,E
  (1<<1)|(1<<2)|(1<<6)|(1<<5)|(1<<4),
  // 6: B,C,G,D,F,E
  (1<<1)|(1<<2)|(1<<6)|(1<<3)|(1<<5)|(1<<4),
  // 7: B,A,F
  (1<<0)|(1<<1)|(1<<5),
  // 8: all segments
  (1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<4)|(1<<5)|(1<<6),
  // 9: B,C,A,G,F,E
  (1<<0)|(1<<1)|(1<<2)|(1<<6)|(1<<5)|(1<<4)
};

// States
volatile bool running = false;
unsigned long lastSecondTick = 0;
unsigned long lastBlink = 0;
bool dotBlinkState = false;
// Idle digit blink timing: ON for 1000 ms, OFF for 250 ms
unsigned long lastDigitToggle = 0;
bool digitOn = true;
const unsigned long DIGIT_ON_MS = 1000UL;
const unsigned long DIGIT_OFF_MS = 250UL;
int jumperDefaultMinutes = 0; // value read from jumpers at startup
int maxMinutes = 1;   // configurable 1..99
int currentSeconds = 0; // remaining seconds while running
int displayMinutes = 1; // value shown in waiting mode (when timer isn't running, this is shown as minutes)
uint8_t idleBrightness = 5;
uint8_t runBrightness = 15;

// Button debouncing
unsigned long lastBtnTimeMinus = 0;
unsigned long lastBtnTimePlus = 0;
unsigned long lastBtnTimeStart = 0;
unsigned long lastBtnTimeReset = 0;
// One-shot reported flags: true while a press has been reported; reset on release
bool lastBtnReportedMinus = false;
bool lastBtnReportedPlus = false;
bool lastBtnReportedStart = false;
bool lastBtnReportedReset = false;
const unsigned long DEBOUNCE_MS = 50;

// Relay alarm control
unsigned long activeBeepEnd = 0; // millis timestamp when active beep should end (0 = inactive)
const unsigned long ALARM_DURATION_MS = 1000;

// Expired-display control: when timer hits 0, show 0:00 in white for EXPIRED_DISPLAY_MS milliseconds
bool inExpiredDisplay = false;
unsigned long expiredDisplayEnd = 0;
const unsigned long EXPIRED_DISPLAY_MS = 5000UL; // 5 seconds

// Helper to read jumpers
/*
D3 D4 D5 D6    Timer Max Minute (value v interpreted from jumpers)
 0  0  0  0     1
 0  0  0  1     2
 0  0  1  0     4
 0  0  1  1     5
 0  1  0  0     7
 0  1  0  1     10
 0  1  1  0     15
 0  1  1  1     20
 1  0  0  0     25
 1  0  0  1     30
 1  0  1  0     35
 1  0  1  1     40
 1  1  0  0     45
 1  1  0  1     50
 1  1  1  0     55
 1  1  1  1     60
*/
int timerMaxMinutes[] = { 1, 2, 4, 5, 7, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60 };

int readJumpers() {
  // Pins D3..D6 represent bits MSB..LSB respectively (D3 = bit3, D6 = bit0)
  // Hardware: each pin has an external 10K pull-up to VCC and a jumper connects it to GND when inserted.
  // With INPUT_PULLUP enabled the pin reads HIGH when the jumper is NOT inserted, and LOW when the jumper IS inserted.
  // We want b0..b3 to be 0 when not inserted and 1 when inserted.

  int raw0 = digitalRead(JUMP_D0); // D3
  int raw1 = digitalRead(JUMP_D1); // D4
  int raw2 = digitalRead(JUMP_D2); // D5
  int raw3 = digitalRead(JUMP_D3); // D6

  int b0 = (raw0 == LOW) ? 1 : 0; // 1 when jumper inserted (pulled to GND)
  int b1 = (raw1 == LOW) ? 1 : 0;
  int b2 = (raw2 == LOW) ? 1 : 0;
  int b3 = (raw3 == LOW) ? 1 : 0;

  int v = 0;
  // Map to bits MSB..LSB as in the table: D3->bit3, D4->bit2, D5->bit1, D6->bit0
  v |= (b0 << 3);
  v |= (b1 << 2);
  v |= (b2 << 1);
  v |= (b3 << 0);

  int maxTime = timerMaxMinutes[v];
  /*
  #if DEBUG
  Serial.print("interpreted D3..D6: "); Serial.print(b0); Serial.print(","); Serial.print(b1); Serial.print(","); Serial.print(b2); Serial.print(","); Serial.println(b3);
  Serial.print("  maxTime: "); Serial.println(maxTime);
  #endif
  */
  return maxTime;
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

  int d0 = (minutes / 10) % 10; // tens minutes
  int d1 = minutes % 10;        // minutes units
  int d2 = (seconds / 10) % 10; // tens seconds
  int d3 = seconds % 10;        // seconds units

  // Physical mapping: segmentStart[0] is the right-most digit (seconds units),
  // segmentStart[1] is tens-seconds, segmentStart[2] is minutes units,
  // segmentStart[3] is left-most (tens-minutes).
  // Suppress leading zero on the left-most tens-minutes digit when minutes < 10.
  if (minutes < 10) {
    // blank left-most digit (physical index 3)
    for (uint8_t s = 0; s < 7; ++s) setSegmentLEDs(3, s, CRGB::Black);
  } else {
    showDigit(3, d0, digitColor);
  }

  // Show minutes units and seconds digits in their physical positions
  showDigit(2, d1, digitColor); // minutes units -> physical index 2
  showDigit(1, d2, digitColor); // tens seconds -> physical index 1
  showDigit(0, d3, digitColor); // seconds units -> physical index 0

  setDots(CRGB::Red, dotsOn); // caller may override color by writing again if needed
}

void displaySecondsOnly(int seconds, CRGB digitColor) {
  if (seconds < 0) seconds = 0;
  // tens and units of seconds
  int s_tens = (seconds / 10) % 10; // 0..5
  int s_units = seconds % 10;
  // blank left two digits (physical indices 3 and 2)
  for (uint8_t seg = 0; seg < 7; ++seg) {
    setSegmentLEDs(3, seg, CRGB::Black);
    setSegmentLEDs(2, seg, CRGB::Black);
  }
  // show tens-seconds at physical index 1 and units at physical index 0
  showDigit(1, s_tens, digitColor);
  showDigit(0, s_units, digitColor);
}

// Display only the units digit (last second) using physical index 0
void displaySingleDigit(int seconds, CRGB digitColor) {
  if (seconds < 0) seconds = 0;
  int s_units = seconds % 10;
  // blank digits 3,2,1
  for (uint8_t seg = 0; seg < 7; ++seg) {
    setSegmentLEDs(3, seg, CRGB::Black);
    setSegmentLEDs(2, seg, CRGB::Black);
    setSegmentLEDs(1, seg, CRGB::Black);
  }
  // show only units at physical index 0
  showDigit(0, s_units, digitColor);
}

void applyShow(uint8_t brightness) {
  FastLED.setBrightness(brightness);
  FastLED.show();
}

// Non-blocking beep: activate relay for `ms` milliseconds then turn it off automatically
void activeBeep(unsigned long ms) {
  digitalWrite(RELAY_PIN, HIGH);
  // set an absolute millis deadline for ending the beep
  activeBeepEnd = millis() + ms;
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
  jumperDefaultMinutes = jumperValue;
  if (jumperDefaultMinutes < 1) jumperDefaultMinutes = 1;
  if (jumperDefaultMinutes > 99) jumperDefaultMinutes = 99;
  maxMinutes = jumperDefaultMinutes;

  /*
  #if DEBUG
  Serial.print("Jumper default Timer Max (minutes): ");
  Serial.println(jumperDefaultMinutes);
  #endif
  */
  // Initial waiting display shows the current maxMinutes
  displayMinutes = maxMinutes;
  currentSeconds = 0;
  running = false;
  lastSecondTick = millis();
  lastBlink = millis();
  lastDigitToggle = millis();
  digitOn = true;

  // Idle startup display: 0:00 in blue, brightness idleBrightness, middle dots solid yellow
  clearAll();
  displayTime(0, CRGB::Blue, false);
  setDots(CRGB::Yellow, true);
  applyShow(idleBrightness);
}

// Read a button and report a single press event per physical press (requires release to re-arm).
// pin: button pin (INPUT_PULLUP, pressed==LOW)
// lastTimeRef: per-button timestamp used for debounce
// reportedFlag: per-button flag that is true while the current press has been reported and remains true until button release
bool readButtonPressed(uint8_t pin, unsigned long &lastTimeRef, bool &reportedFlag) {
  bool pressed = (digitalRead(pin) == LOW);
  unsigned long now = millis();
  if (pressed) {
    // Button is currently pressed. If it hasn't been reported yet and debounce elapsed, report it once.
    if (!reportedFlag && (now - lastTimeRef > DEBOUNCE_MS)) {
      reportedFlag = true;
      lastTimeRef = now;
      return true;
    }
  } else {
    // Button released: clear the reported flag and update the timestamp so the next press is debounced
    reportedFlag = false;
    lastTimeRef = now;
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
    // ensure minimum allowed is 1 minute
    if (maxMinutes > 1) maxMinutes--;
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
  // Stop timer and restore max minutes to jumper default
  running = false;
  currentSeconds = 0;
  maxMinutes = jumperDefaultMinutes;
  if (maxMinutes < 1) maxMinutes = 1;
  if (maxMinutes > 99) maxMinutes = 99;
  displayMinutes = maxMinutes;
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
  if (readButtonPressed(BTN_PLUS, lastBtnTimePlus, lastBtnReportedPlus)) {
    doPlus();
  }
  if (readButtonPressed(BTN_MINUS, lastBtnTimeMinus, lastBtnReportedMinus)) {
    doMinus();
  }
  if (readButtonPressed(BTN_START, lastBtnTimeStart, lastBtnReportedStart)) {
    // Start or restart the timer from the currently selected maxMinutes
    startTimer();
  }
  if (readButtonPressed(BTN_RESET, lastBtnTimeReset, lastBtnReportedReset)) {
    resetTimer();
  }

  // Update countdown based on elapsed full seconds
  if (running) {
    unsigned long elapsedMs = now - lastSecondTick;
    if (elapsedMs >= 1000) {
      unsigned long elapsedSec = elapsedMs / 1000UL;
      // Advance the reference tick to account for the elapsed seconds
      lastSecondTick += elapsedSec * 1000UL;

      // Subtract elapsed seconds (but don't go negative)
      if (elapsedSec >= (unsigned long)currentSeconds) {
        currentSeconds = 0;
      } else {
        currentSeconds -= (int)elapsedSec;
      }

      if (currentSeconds <= 0) {
        // Timer expired
        currentSeconds = 0;
        running = false;

        // Activate relay for ALARM_DURATION_MS using non-blocking activeBeep
        activeBeep(ALARM_DURATION_MS);

        // Enter expired-display state: show 0:00 in white for EXPIRED_DISPLAY_MS
        inExpiredDisplay = true;
        expiredDisplayEnd = now + EXPIRED_DISPLAY_MS;
      }
    }
  }

  // Turn off relay when activeBeep deadline reached
  if (activeBeepEnd != 0 && now >= activeBeepEnd) {
    digitalWrite(RELAY_PIN, LOW);
    activeBeepEnd = 0;
  }

  // Dots blink handling (blink at 1Hz i.e., toggle every 500ms)
  if (now - lastBlink >= 500) {
    lastBlink = now;
    dotBlinkState = !dotBlinkState;
  }

  // Prepare display based on state
  // Dots blink handling (idle dots blink at 1Hz via dotBlinkState)
  if (inExpiredDisplay) {
    // Show 0:00 in white for the configured period
    clearAll();
    // Show 0:00 in white and show the middle dots in white as well
    displayTime(0, CRGB::White, true);
    setDots(CRGB::White, true);
    // Use half of runBrightness for the expired display
    applyShow(runBrightness / 2);

    // When expired-display period finishes, return to waiting mode and reload jumper default
    if (now >= expiredDisplayEnd) {
      inExpiredDisplay = false;
      // Re-read jumpers to restore default
      jumperDefaultMinutes = readJumpers();
      if (jumperDefaultMinutes < 1) jumperDefaultMinutes = 1;
      if (jumperDefaultMinutes > 99) jumperDefaultMinutes = 99;
      maxMinutes = jumperDefaultMinutes;
      displayMinutes = maxMinutes;
    }
  } else if (!running) {
    // Idle/waiting display: show maxMinutes (displayMinutes) constantly; dots blink at 1Hz
    clearAll();
    int totalSec = displayMinutes * 60;
    // Show digits steady in blue
    displayTime(totalSec, CRGB::Blue, false);
    // Blink dots in yellow at 1Hz
    setDots(CRGB::Yellow, dotBlinkState);
    applyShow(idleBrightness);
  } else {
    // Running display
    bool lastMinute = (currentSeconds <= 60);
    clearAll();
    if (!lastMinute) {
      // digits green, brightness runBrightness, dots blink red at 1Hz
      displayTime(currentSeconds, CRGB::Green, dotBlinkState);
      // override dots color to red as blinked
      setDots(CRGB::Red, dotBlinkState);
      applyShow(runBrightness);
    } else {
      // last minute: show seconds only. For the last 9 seconds show only the units digit.
      if (currentSeconds <= 9) {
        displaySingleDigit(currentSeconds, CRGB::Red);
      } else {
        displaySecondsOnly(currentSeconds, CRGB::Red);
      }
      setDots(CRGB::Green, dotBlinkState);
      applyShow(runBrightness);
    }
  }

  // Small delay to avoid hammering CPU
  delay(10);
}
