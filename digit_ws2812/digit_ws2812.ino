/*  2025-Feb-1:
 *  This is soccer 7 MIN count down timer.  Use WS2812b LED as 7 segments display
 *  1. Use TOUCH to reset the Timer.
 *  2. Use RELAY to trigger the sound.
 *  3. This is our very special WS2812b digit setting.
 *  
 *           A
 *       10 11 12
 *    9            13    
 * F  8            14  B 
 *    7      G     15
 *    6  22 21 20  16  
 *    5            17
 * E  4            18  C
 *    3            19
 *        2  1  0
 *           D
 */

 /* 2026-Oct-10:
  * 1. Change the loop sleep period from 250ms (1/4 second) to 100ms (1/10 second)
  * 2. Fix the last second display and alarm turn on behavior.
  * 2. Use non-block method for the beep.
  * 3. Blink the seconds during the last 20 seconds (600ms ON / 400ms OFF).
  */
 
#include <FastLED.h>

#define UINT        unsigned int
#define BUTTON_PIN  4
#define LED_PIN     7
#define RELAY_PIN   9
#define NUM_LEDS    94
#define BRIGHTNESS  25
#define LED_TYPE    WS2812
#define COLOR_ORDER GRB
struct CRGB leds[NUM_LEDS];

byte dg[11][23] = {
/*         0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 */
/* 0 */  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0 },
/* 1 */  { 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
/* 2 */  { 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1 },
/* 3 */  { 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1 },
/* 4 */  { 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },
/* 5 */  { 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1 },
/* 6 */  { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1 },
/* 7 */  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0 },
/* 8 */  { 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1 },
/* 9 */  { 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 },

/* 10*/  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0 }
};

#define MIN  7
 
// Loop and timing tuning
const unsigned int LOOP_DELAY_MS = 100;                   // loop delay (ms)
const unsigned int COUNT_PER_SECOND = 1000 / LOOP_DELAY_MS; // iterations per second
const unsigned int DEBOUNCE_MS = 200;                     // debounce interval for touch (ms)

// Seconds blinking during last 20 seconds: 600ms ON, 400ms OFF
const unsigned int SEC_BLINK_ON_MS = 600;
const unsigned int SEC_BLINK_OFF_MS = 400;
const unsigned long SEC_BLINK_PERIOD = (unsigned long)SEC_BLINK_ON_MS + (unsigned long)SEC_BLINK_OFF_MS;

UINT iMin, iSec, iCount;

// Debounce state
unsigned long lastTouchChange = 0;
byte debouncedTouch = LOW;
byte lastRawTouch = LOW;

// Non-blocking beep state
bool beepActive = false;
unsigned long beepStartMillis = 0;
unsigned long beepDurationMs = 0;

// Blink state for last-20s (state-machine to avoid aliasing)
bool secBlinkState = true;                  // true = ON, false = OFF
unsigned long secBlinkLastToggle = 0;       // last toggle time (ms)
unsigned long secBlinkCurrentDuration = SEC_BLINK_ON_MS; // current duration (ms)
bool wasInLast20 = false;                  // track entry into last-20s

struct touch { 
   byte wasPressed = LOW; 
   byte isPressed  = LOW; 
}; 
touch touch; 

// UINT digpos[ 4 ] = { 0, 23, 48, 71 };
#define dig1pos 0
#define dig2pos 23
#define dig3pos 48
#define dig4pos 71

#define dot1 46
#define dot2 47
bool bDot = 0;
UINT dotcounter = 0;

#define DOT_RED    leds[dot1] = CRGB( 255, 0, 0 ); leds[dot2] = CRGB( 255, 0, 0 );
#define DOT_GREEN  leds[dot1] = CRGB( 0, 255, 0 ); leds[dot2] = CRGB( 0, 255, 0 );
#define DOT_RESET  leds[dot1] = CRGB( 0, 255, 0 ); leds[dot2] = CRGB( 0, 255, 0 );



void setup() {
  delay(200);

 #ifdef DBG 
  Serial.begin(115200);
 #endif
 
  pinMode(BUTTON_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
     
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS).setCorrection( TypicalLEDStrip );
  FastLED.setBrightness( BRIGHTNESS );
  FastLED.clear();
  
  iMin = 0;
  iSec = 0;
  iCount = 0;

  // Initialize debounce state from current raw reading
  lastRawTouch = digitalRead(BUTTON_PIN);
  debouncedTouch = lastRawTouch;
  lastTouchChange = millis();

#ifdef DBG
  Serial.print( "Min " );
  Serial.print( iMin );
  Serial.print( ", Sec " );
  Serial.println( iSec );
#endif

  displayTime( iMin, iSec, true );
}

void loop() {
   bool displayUpdated = false;

   /* Independent DOT refreshing */
   if ( dotcounter++ % 2 == 0 ) {
     if ( bDot ) {
        if ( iMin == 0 && iSec > 0 ) { DOT_GREEN } else { DOT_RED }
        bDot = 0;
     } else {
        DOT_RESET
        bDot = 1;    
     }    
   }

   /* Counter for the Timer */
   if ( iMin || iSec ) { iCount++; }

   /* Reset the Time to MIN (debounced) */
   {
     byte raw = isTouchPressed(BUTTON_PIN) ? HIGH : LOW;
     if ( raw != lastRawTouch ) {
       lastTouchChange = millis();
       lastRawTouch = raw;
     }
     if ( (millis() - lastTouchChange) > DEBOUNCE_MS ) {
       if ( debouncedTouch != raw ) {
         debouncedTouch = raw;
         // Trigger on pressed (rising edge)
         if ( debouncedTouch == HIGH ) {
           iMin = MIN;  iSec = 0;  iCount = 0;
         }
       }
     }
   }

   /* Every 1 second (based on LOOP_DELAY_MS), change Min and Sec */
   if ( iCount > 0 && (iCount % COUNT_PER_SECOND) == 0 ) {

     /* Counting down one second */
     if ( iSec ) {  iSec--;  } else {   iSec = 59;  iMin--; }
     
     displayTime( iMin, iSec, true );
     displayUpdated = true;
     
     if ( iMin == 0 && iSec == 0 ) {
        FastLED.show();
        displayUpdated = false; // avoid duplicate show later in this loop
#ifdef DBG      
        Serial.println( "The end of timer" );
#endif
        /* Trigger the Relay ON / OFF (non-blocking) */
        startBeep(1500);

        /* Reset Counter and MIN & SEC are zero */
        iCount = 0;
      }
  }
  // If in last 20 seconds, update the seconds blinking every loop (state-machine)
  {
    bool inLast20 = (iMin == 0 && iSec > 0 && iSec <= 20);
    if (inLast20 && !wasInLast20) {
      // Just entered last-20s window: initialize blink state
      secBlinkState = true;
      secBlinkLastToggle = millis();
      secBlinkCurrentDuration = SEC_BLINK_ON_MS;
    }
    if (inLast20) {
      unsigned long now = millis();
      if (now - secBlinkLastToggle >= secBlinkCurrentDuration) {
        secBlinkState = !secBlinkState;
        // Advance the toggle timestamp to avoid drift
        secBlinkLastToggle = now;
        secBlinkCurrentDuration = secBlinkState ? SEC_BLINK_ON_MS : SEC_BLINK_OFF_MS;
      }
      displayTime(iMin, iSec, secBlinkState);
      displayUpdated = true;
    }
    wasInLast20 = inLast20;
  }

  // Handle non-blocking beep (turn relay off when duration elapsed)
  if (beepActive) {
    if (millis() - beepStartMillis >= beepDurationMs) {
      digitalWrite(RELAY_PIN, LOW);
      beepActive = false;
    }
  }

  // Show display once per loop if it was updated
  if (displayUpdated) {
    FastLED.show();
  }

  /* Loop delay (tunable) */
  delay(LOOP_DELAY_MS); 
}

void displayTime( UINT m, UINT s, bool secBlinkOn ) {
  /* If MIN and SEC are zero, just display '0' */
  if ( m == 0 && s == 0 ) {
     displayDigit( dig1pos, 0, 0, 255, 0 );
     displayDigit( dig2pos, 0, 0, 255, 0 );
     displayDigit( dig3pos, 0, 0, 255, 0 );
     return;
  }

  /* Calculate the integer value of Min and Sec */
  UINT s10 = int( s / 10 );
  UINT s00 = s % 10;
  UINT m10 = int( m / 10 );
  UINT m00 = m % 10;

  /* Is last min ? */
  if ( m == 0 ) {
     /* display Sec in Red */
     if ( s <= 20 ) {
       // During last 20 seconds, blink the seconds digits based on secBlinkOn
       if ( secBlinkOn ) {
         displayDigit( dig1pos, s00, 255, 0, 0 );
         if ( s10 ) { displayDigit( dig2pos, s10, 255, 0, 0 ); } else { resetDigit( dig2pos ); }
       } else {
         // blink OFF: hide seconds digits but keep minutes off
         resetDigit( dig1pos );
         resetDigit( dig2pos );
       }
     } else {
       // Not in blinking window: display seconds normally
       displayDigit( dig1pos, s00, 255, 0, 0 );
       if ( s10 ) { displayDigit( dig2pos, s10, 255, 0, 0 ); } else { resetDigit( dig2pos ); }
     }
     /* Do not display MIN */
     resetDigit( dig3pos );
     resetDigit( dig4pos );
     
  } else {
     /* display Min and Sec in Green */
     displayDigit( dig1pos, s00, 0, 255, 0 );
     displayDigit( dig2pos, s10, 0, 255, 0 );

     /* Display MIN */
     displayDigit( dig3pos, m00, 0, 255, 0 );

     /* Need to display 10's MIN */
     if ( m10 ) { displayDigit( dig4pos, m10, 0, 255, 0 ); }
  }
}

void resetDigit( UINT offset ) {
  /* Reset all 7 segements to 0, 0, 0 */
  for( UINT x = 0; x <= 22; x++ ) {
     leds[offset + x ] = CRGB( 0, 0, 0 );
  }
}
  
void displayDigit( UINT offset, UINT d, UINT R, UINT G, UINT B ) {

  /* Special case for SEC digit and value '1', use special pattern: use d as the access index  */
  if ( offset == 0 && d == 1 ) { d = 10; }

  /* Set the 7 segments based on the defines array */
  for( UINT x = 0; x <= 22; x++ ) {
     leds[offset + x ] = ( dg[ d ][ x ] == 1 ? CRGB( R, G, B) : CRGB( 0, 0, 0) );
  }
}

// Start a non-blocking beep (relay ON for ms milliseconds)
// If a beep is already active, ignore new requests instead of restarting
void startBeep(unsigned long ms) {
  if (beepActive) return; // ignore repeated requests while active
  digitalWrite(RELAY_PIN, HIGH);
  beepStartMillis = millis();
  beepDurationMs = ms;
  beepActive = true;
}

bool isTouchPressed(int pin) 
{ 
   return digitalRead(pin) == HIGH; 
} 
