#ifndef BUILD_VERSION_H
#define BUILD_VERSION_H

// Build version macro in hex. The upload helper script updates this value automatically.
// Starts at 0x0000 and increments (mod 0x10000) each time the upload script runs.
#define BUILD_VERSION 0x0001

#endif // BUILD_VERSION_H

