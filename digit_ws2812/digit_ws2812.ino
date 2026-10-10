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
 
UINT iMin, iSec, iCount;
 
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
     
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS).setCorrection( TypicalLEDStrip );
  FastLED.setBrightness( BRIGHTNESS );
  FastLED.clear();
  
  iMin = 0;
  iSec = 0;
  iCount = 0;

#ifdef DBG
  Serial.print( "Min " );
  Serial.print( iMin );
  Serial.print( ", Sec " );
  Serial.println( iSec );
#endif

  displayTime( iMin, iSec );
}

void loop() {
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

   /* Reset the Time to MIN */
   touch.isPressed = isTouchPressed(BUTTON_PIN);
   if (touch.wasPressed != touch.isPressed) { 
      iMin = MIN;  iSec = 0;  iCount = 0;
   } 
   touch.wasPressed = touch.isPressed; 

   /* Every 1/4 second, change Min and Sec */
   if ( iCount > 0 && iCount % 4 == 0 ) {

     /* Counting down one second */
     if ( iSec ) {  iSec--;  } else {   iSec = 59;  iMin--; }
     
     displayTime( iMin, iSec );
     
     if ( iMin == 0 && iSec == 0 ) {
#ifdef DBG      
        Serial.println( "The end of timer" );
#endif
        /* Trigger the Relay ON / OFF */
        digitalWrite( RELAY_PIN, HIGH );
        delay( 250 );
        digitalWrite( RELAY_PIN, LOW );

        /* Reset Counter and MIN & SEC are zero */
        iCount = 0;
     }
  }
  FastLED.show();

  /* Repeat 1/4 sec */
  delay(250); 
}

void displayTime( UINT m, UINT s ) {
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
     displayDigit( dig1pos, s00, 255, 0, 0 );
     
     if ( s10 ) {
        displayDigit( dig2pos, s10, 255, 0, 0 );   
     } else {
        /* Sec less than 10, do not display 10's SEC */
        resetDigit( dig2pos );
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

bool isTouchPressed(int pin) 
{ 
   return digitalRead(pin) == HIGH; 
} 
