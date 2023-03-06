#include "parsefloat.h"

/*
Nonblocking implementation of the Serial.ParseFloat() function.

*/

// Receive data vars
const byte numChars = 32;
char receivedChars[numChars];
bool newData = false;
float receivedFloat = -1;

void checkForNewString() {
    static bool recvInProgress = false;
    static byte ndx = 0;
    char startMarker = '<';
    char endMarker = '>';
    char rc;
 
    while (Serial.available() > 0 && newData == false) {
        rc = Serial.read();

        if (recvInProgress == true) {
            if (rc != endMarker) {
                receivedChars[ndx] = rc;
                ndx++;
                if (ndx >= numChars) {
                    ndx = numChars - 1;
                }
            }
            else {
                receivedChars[ndx] = '\0'; // terminate the string
                recvInProgress = false;
                ndx = 0;
                newData = true;
            }
        }

        else if (rc == startMarker) {
            recvInProgress = true;
        }
    }
}

float processInput() {
    if (newData == true) {
        newData = false;
        return atof(receivedChars);
    } else
        return -1;
}